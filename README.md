# Multi-Service Credit & Entitlement Anomaly Detection

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

That's it. Migrations run automatically, synthetic data seeds itself, 
and the AI service is live at `http://localhost:8000`.

Try it:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/debug/events
```

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
explainability layer, full Docker deployment.





