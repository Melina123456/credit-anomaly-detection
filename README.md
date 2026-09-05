# Multi-Service Credit & Entitlement Anomaly Detection

![CI](https://github.com/Melina123456/credit-anomaly-detection/actions/workflows/ci.yml/badge.svg)

Detects anomalous usage patterns in a multi-tenant SaaS billing system, 
with explainable AI (SHAP) showing *why* each anomaly was flagged.

Built on a ledger + materialized-cache architecture pattern used in 
production billing systems — extended here with an ML anomaly detection 
layer.

## Why this exists

Most anomaly detectors are black boxes. This one explains itself:

GET /analyze/{event_id}

{
"is_anomaly": true,
"top_reason": "usage quantity is unusually far from this tenant's normal baseline",
"feature_contributions": {
"z_score": -6.9,
"duplicate_count": 0.11,
"ingestion_lag_days": -0.75
}
}


## Architecture

┌─────────────┐ ┌──────────────┐ ┌────────────┐
│ Go │────▶│ PostgreSQL │◀────│ Python │
│ Ingestion │ │ (ledger + │ │ AI Service │
│ Pipeline │ │ caches) │ │ (FastAPI) │
└─────────────┘ └──────────────┘ └────────────┘
│ │
▼ ▼
Generates synthetic Isolation Forest +
events, writes ledger, SHAP explainability
updates read caches


**Ledger-vs-cache pattern:** `credit_transaction` is the append-only 
source of truth. `credit_pool_balance` and `entitlement_usage` are 
materialized read caches, rebuilt from the ledger — never edited directly.

**Proving the cache hasn't drifted:** `GET /debug/consistency-check` independently re-sums every pool's transactions from the ledger and compares that against what `credit_pool_balance` currently caches — instead of just trusting that the cache-rebuild code is bug-free. Verified by deliberately corrupting a cached balance by hand and confirming the endpoint caught the exact pool and the exact discrepancy, then confirming it went quiet again once restored.

## Model lifecycle (train/serve split)

`/analyze` does **not** train a model per request. Instead:

- `POST /train` fits `IsolationForest` on the current data, evaluates it, saves the fitted model to disk (`joblib`), and records the run — when, on how much data, with what precision/recall/F1 — as a row in the `model_run` table.
- `GET /model/current` returns that record: a minimal "model card" for whatever's currently being served.
- `GET /analyze/{event_id}` loads the most recently trained model and scores against it. If nothing has been trained yet, it returns `503` rather than silently training one — the point of separating train from serve is that scoring is never allowed to accidentally trigger training.
- The model file lives in a named Docker volume (`ai_models`, mounted at `/app/models`), so it survives a container restart or even the container being removed and recreated — verified by actually doing that and re-checking `/model/current`, not assumed.

The `/debug/*` endpoints are unchanged — they still fit a fresh, throwaway model on every call, deliberately. They exist for exploring the data and the model live, not for serving; `/train` and `/analyze` are the only path that reads and writes the persisted model.

## Quick start

```bash

git clone https://github.com/Melina123456/credit-anomaly-detection.git
cd credit-anomaly-detection
docker-compose up --build
```

Migrations run automatically, synthetic data seeds itself, 
and the AI service is live at `http://localhost:8000`.

Try it:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/debug/events

# train and persist a model, then ask it about a real event
curl -X POST http://localhost:8000/train
curl http://localhost:8000/model/current
curl http://localhost:8000/analyze/{event_id}   # id from /debug/events above

# confirm the balance cache still matches the ledger
curl http://localhost:8000/debug/consistency-check
```

## Testing & CI

There's a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs on every push and pull request:

- **Go** — `go vet` + `go test ./...` for the ingestion module. Tests cover the synthetic-data generator (`internal/generator`): event counts, the documented value ranges for each anomaly type (e.g. spikes are 10x-20x baseline), and edge cases like an empty event list or an unrecognized plan tier.
- **Python** — `pytest` for the AI service. Tests cover the pure feature-engineering and evaluation logic (`features.py`, `evaluate.py`, `analyze.py`, `registry.py`, `consistency.py`): the robust z-score math, duplicate detection, SHAP-reason selection, per-anomaly-type recall, ledger/cache mismatch detection, and edge cases like a tenant whose usage never varies (zero MAD), a model that flags nothing at all (zero-division in precision/recall), or training being called with no data. All database access for the AI service is centralized in `db.py` — the other modules describe *what* they need ("the latest model run," "each pool's cached vs. ledger balance") without knowing *how* it's fetched, which is what keeps this pure-logic layer testable without a database at all.

Run them locally:

```bash
# Go
cd ingestion
go test ./... -v

# Python
cd ai-service
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/pytest -v
```

**What's *not* covered yet:** anything that touches Postgres or Redis directly — the ledger writer, the cache-rebuild functions, the DB-backed seeding, and every function in `db.py` itself (`fetch_pool_balance_consistency`, `insert_model_run`, `fetch_latest_model_run`), plus the FastAPI endpoints. Those are exercised manually via `docker-compose up` today — including two claims specifically verified this way rather than assumed: the model registry's persistence (trained a model, fully removed and recreated the `ai-service` container, confirmed `/model/current` still resolved it) and the consistency check's ability to actually catch drift (corrupted a real cached balance by hand, confirmed the endpoint flagged the exact pool and amount, then confirmed it went quiet once restored). Testing this properly in CI would mean either spinning up a real Postgres (`services:` in the workflow, or a library like `testcontainers`) or introducing an interface to mock the database — both reasonable next steps, not yet done.

## Anomaly types detected

| Type | Signal | Example |
|---|---|---|
| Spike | `z_score` | Usage 10-20x normal baseline |
| Replay | `duplicate_count` | Same event submitted twice |
| Negative-balance attempt | `z_score` | Usage exceeding available credits |
| Out-of-order | `ingestion_lag_days` | Event backdated 20-40 days |

## Model performance

| Model | Precision | Recall | F1 |
|---|---|---|---|
| **Isolation Forest** | 0.753 | 1.0 | 0.859 |
| Local Outlier Factor | 0.740 | 0.982 | 0.844 |

Isolation Forest chosen — caught 100% of labeled anomalies.

**Recall broken down by anomaly type** (`GET /debug/evaluate`, via `evaluate_by_type`), so the aggregate 100% recall figure isn't hiding a weak category:

| Anomaly Type | Injected | Detected | Recall |
|---|---|---|---|
| spike | 30 | 30 | 1.0 |
| replay | 30 | 30 | 1.0 |
| negative_balance_attempt | 20 | 20 | 1.0 |
| out_of_order | 30 | 30 | 1.0 |

All 36 false positives (precision's cost: 110 true positives out of 146 total flags) came from normal events that happened to look anomalous — not from a specific anomaly type being under-detected.

## Explainability

Every anomaly type is explained by its intended feature — verified with 
average |SHAP value| per type:

| Anomaly Type | Dominant Feature |
|---|---|
| spike | z_score (8.21) |
| negative_balance_attempt | z_score (7.42) |
| replay | duplicate_count (8.07) |
| out_of_order | ingestion_lag_days (8.98) |

## Tech stack

Go · Python (FastAPI, scikit-learn, SHAP) · PostgreSQL · Redis · Docker

## Data

All data is synthetically generated. No proprietary schemas, data, or 
code from any employer are used — only general architectural patterns.

## Status

Weeks 1-4 complete: ingestion pipeline, anomaly injection, ML model, 
explainability layer, full Docker deployment, unit tests + CI, 
persisted model registry with train/serve split, 
ledger/cache consistency verification.

## Known limitations

Being upfront about what this is *not* yet, since that matters more than the parts that already work:

- **Nothing triggers `/train` automatically.** There's no scheduled retraining and no auto-train-on-first-boot — you have to call `POST /train` yourself after data exists. That's intentional for now (an accidental training run on empty or partial data is worse than an explicit `503`), but a real deployment would want a scheduled job or a "retrain if data has grown by X%" trigger.
- **No model versioning beyond "latest."** Every `/train` call adds a new row to `model_run` and a new file on disk (nothing is overwritten), but `/analyze` only ever reads the single most recent one — there's no way to pin, compare, or roll back to an older model yet. The history is there in the table; nothing reads it but the last row.
- **Redis is connected but unused.** The ingestion service opens a Redis client at startup and never touches it again — it's in the `docker-compose.yml` stack and the tech list below, but isn't doing real work yet. Either it needs a real job (e.g. caching per-tenant baselines) or it should come out of the stack description.
- **The `/debug/*` endpoints are unauthenticated** and return internals (raw feature values, per-type SHAP breakdowns). They're genuinely useful for development, but they'd need to be gated or removed before this ran anywhere with a real audience.
- **Test coverage stops at the database boundary** — see [Testing & CI](#testing--ci) above.
