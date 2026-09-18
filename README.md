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
},
"model_id": "234c8d62-a013-46a9-bf35-a0ce9abd38f6"
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
- Every `/analyze` response includes `model_id`, the `model_run` row that produced it — so a result can always be traced back to exactly which trained model made the call, and cross-checked against `GET /model/current` or the run history in `model_run`. This doesn't add pinning or rollback (see Known limitations) — it just makes "which model said this" answerable instead of assumed.
- The model file lives in a named Docker volume (`ai_models`, mounted at `/app/models`), so it survives a container restart or even the container being removed and recreated — verified by actually doing that and re-checking `/model/current`, not assumed.

The `/debug/*` endpoints are unchanged — they still fit a fresh, throwaway model on every call, deliberately. They exist for exploring the data and the model live, not for serving; `/train` and `/analyze` are the only path that reads and writes the persisted model.

## Baseline caching (Redis)

`GET /analyze/{event_id}` used to pull the *entire* `usage_event` table just to score one event, because computing a tenant's "normal" baseline (median/MAD, see Explainability below) requires looking at their whole history. That cost didn't go away when the model itself got persisted — every `/analyze` call was still re-deriving every tenant's baseline from scratch.

Now `POST /train` — which already computes every tenant/feature's baseline as a step in fitting the model — also writes each one to Redis (`baseline:{tenant_id}:{feature_id}` → `{median, mad}`). `/analyze` then does three cheap, targeted lookups instead of one expensive full-table scan: fetch just the one event by id, look up its tenant/feature's baseline in Redis, count exact duplicates of just that event. If a tenant/feature was never part of a training run, `/analyze` returns a clear `503` rather than silently falling back to a full recompute — same philosophy as "no model trained yet."

This is Redis's first real job in this project — previously it was connected and never used (see the old entry in Known limitations, now removed). The Go ingestion service no longer touches Redis at all; caching baselines is specifically an AI-service concern, so keeping an unused connection on the Go side just to look busy would have been its own small piece of dishonesty.

Honest performance note: on this project's small synthetic dataset (a few thousand rows), `/analyze` measured at ~0.3s either way — not a dramatic speedup yet. The real point isn't today's dataset, it's that the old approach got slower as `usage_event` grew (more rows to scan every single call), while this approach doesn't — a single Redis lookup costs the same whether there are a thousand events or a hundred million.

## Protecting internal endpoints

Every `/debug/*` route and `POST /train` now require an `X-API-Key` header matching the server's `ADMIN_API_KEY` environment variable — `app/auth.py`, applied via one shared FastAPI dependency rather than repeated on each route. `/train` is included even though it isn't under `/debug/`: it's arguably the single most sensitive endpoint in the service, since whoever can call it can replace the model every other request scores against.

It fails **closed**: if `ADMIN_API_KEY` isn't set on the server at all, those routes return `503` for everyone rather than silently becoming open — a missing config should never be indistinguishable from "no auth needed." `GET /health`, `GET /model/current`, and `GET /analyze/{event_id}` stay open; they're the service's actual public surface, not internals.

This is a shared static key, not real user-level auth — appropriate for gating "internal/dev-only" endpoints at this project's stage, not for a multi-tenant system where different callers need different permissions. That's a deliberately bigger feature for later, not an oversight here.

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

# /debug/* and /train require the X-API-Key header — docker-compose.yml
# sets a fixed local-dev key so this works out of the box; see "Protecting
# internal endpoints" below.
curl -H "X-API-Key: local-dev-only-key" http://localhost:8000/debug/events

# train and persist a model, then ask it about a real event
curl -X POST -H "X-API-Key: local-dev-only-key" http://localhost:8000/train
curl http://localhost:8000/model/current
curl http://localhost:8000/analyze/{event_id}   # id from /debug/events above

# confirm the balance cache still matches the ledger
curl -H "X-API-Key: local-dev-only-key" http://localhost:8000/debug/consistency-check
```

## Testing & CI

There's a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs on every push and pull request:

- **Go** — `go vet` + `go test ./...` for the ingestion module. Tests cover the synthetic-data generator (`internal/generator`): event counts, the documented value ranges for each anomaly type (e.g. spikes are 10x-20x baseline), and edge cases like an empty event list or an unrecognized plan tier.
- **Python** — `pytest` for the AI service. Tests cover the pure feature-engineering and evaluation logic (`features.py`, `evaluate.py`, `analyze.py`, `registry.py`, `consistency.py`, `scoring.py`, `auth.py`): the robust z-score math (both the bulk/training version and the single-event version used by `/analyze` — pinned to agree with each other), duplicate detection, SHAP-reason selection, per-anomaly-type recall, ledger/cache mismatch detection, and edge cases like a tenant whose usage never varies (zero MAD), a model that flags nothing at all (zero-division in precision/recall), training being called with no data, or the API key being missing/wrong/unconfigured (fail-closed, verified by test). All database access for the AI service is centralized in `db.py`, and all Redis access in `cache.py` — other modules describe *what* they need ("the latest model run," "this tenant's cached baseline") without knowing *how* it's fetched, which is what keeps this pure-logic layer testable without either infrastructure running at all.

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

**What's *not* covered yet:** anything that touches Postgres or Redis directly — the ledger writer, the cache-rebuild functions, the DB-backed seeding, every function in `db.py` and `cache.py`, plus the FastAPI endpoints. Those are exercised manually via `docker-compose up` today — including several claims specifically verified this way rather than assumed: the model registry's persistence (trained a model, fully removed and recreated the `ai-service` container, confirmed `/model/current` still resolved it), the consistency check's ability to actually catch drift (corrupted a real cached balance by hand, confirmed the endpoint flagged the exact pool and amount), and the baseline cache actually being read from, not just written to (checked Redis directly with `redis-cli KEYS`/`GET` after training, confirmed real median/MAD values were there, then confirmed `/analyze` correctly scored both normal and labeled-anomaly events using them). Testing this properly in CI would mean either spinning up real Postgres and Redis instances (`services:` in the workflow, or a library like `testcontainers`) or introducing an interface to mock them — both reasonable next steps, not yet done.

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
ledger/cache consistency verification, 
Redis-backed baseline caching for single-event scoring, 
API-key protection on internal endpoints.

## Known limitations

Being upfront about what this is *not* yet, since that matters more than the parts that already work:

- **Nothing triggers `/train` automatically.** There's no scheduled retraining and no auto-train-on-first-boot — you have to call `POST /train` yourself after data exists. That's intentional for now (an accidental training run on empty or partial data is worse than an explicit `503`), but a real deployment would want a scheduled job or a "retrain if data has grown by X%" trigger.
- **No model versioning beyond "latest."** Every `/train` call adds a new row to `model_run` and a new file on disk (nothing is overwritten), and `/analyze` now reports which run's model (`model_id`) produced each result — but `/analyze` still only ever *scores against* the single most recent one, and there's no way to pin, compare, or roll back to an older model. The history is there in the table; nothing but the last row is ever served.
- **The baseline cache has no invalidation beyond the next `/train`.** If a brand-new tenant or feature gets seeded after the last training run, `/analyze` will correctly refuse with a 503 for it (no cached baseline) rather than guess — but that means it's stale-by-construction between training runs, same as the model itself. This is the same "nothing triggers `/train` automatically" limitation above, just visible in a second place now.
- **`ADMIN_API_KEY` is one shared static key**, not per-user auth — fine for gating dev-only endpoints today, not a substitute for real access control if this ever served more than one trusted operator. See [Protecting internal endpoints](#protecting-internal-endpoints) above.
- **Test coverage stops at the database boundary** — see [Testing & CI](#testing--ci) above.
