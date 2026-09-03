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
```

## Testing & CI

There's a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs on every push and pull request:

- **Go** — `go vet` + `go test ./...` for the ingestion module. Tests cover the synthetic-data generator (`internal/generator`): event counts, the documented value ranges for each anomaly type (e.g. spikes are 10x-20x baseline), and edge cases like an empty event list or an unrecognized plan tier.
- **Python** — `pytest` for the AI service. Tests cover the pure feature-engineering and evaluation logic (`features.py`, `evaluate.py`, `analyze.py`): the robust z-score math, duplicate detection, SHAP-reason selection, and edge cases like a tenant whose usage never varies (zero MAD) or a model that flags nothing at all (zero-division in precision/recall).

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

**What's *not* covered yet:** anything that touches Postgres or Redis directly — the ledger writer, the cache-rebuild functions, the DB-backed seeding, and the FastAPI endpoints themselves. Those are exercised manually via `docker-compose up` today. Testing them properly would mean either spinning up a real Postgres in CI (`services:` in the workflow, or a library like `testcontainers`) or introducing an interface to mock the database — both reasonable next steps, not yet done.

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
explainability layer, full Docker deployment, unit tests + CI.

## Known limitations

Being upfront about what this is *not* yet, since that matters more than the parts that already work:

- **The model retrains on every `/analyze` request** — it pulls the full `usage_event` table, refits `IsolationForest` from scratch, then predicts. That's fine for a demo-sized dataset, but it means no train/serve split, no persisted model file, and results can shift slightly as new synthetic data accumulates. A real next step: train once, persist with `joblib`, serve from the saved model, retrain on a schedule.
- **Redis is connected but unused.** The ingestion service opens a Redis client at startup and never touches it again — it's in the `docker-compose.yml` stack and the tech list below, but isn't doing real work yet. Either it needs a real job (e.g. caching per-tenant baselines) or it should come out of the stack description.
- **The `/debug/*` endpoints are unauthenticated** and return internals (raw feature values, per-type SHAP breakdowns). They're genuinely useful for development, but they'd need to be gated or removed before this ran anywhere with a real audience.
- **Test coverage stops at the database boundary** — see [Testing & CI](#testing--ci) above.
- **Evaluation is only reported in aggregate**, not broken down per anomaly type — so a 100% recall figure doesn't yet show whether "out-of-order" events are individually as well caught as "spikes."
