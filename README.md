# Multi-Service Credit & Entitlement Anomaly Detection

Applied ML system for detecting anomalous usage/credit patterns in a 
multi-tenant SaaS billing architecture. Extends a ledger-vs-cache 
design pattern (append-only transaction ledger + materialized read 
caches) with an ML anomaly detection layer and SHAP-based explainability.

## Status: Week 1 — Infrastructure 

## Architecture
- `/ingestion` — Go service: event ingestion, ledger writes, cache updates
- `/ai-service` — Python: anomaly detection models, SHAP explainability, API

## Stack
Go · Python (scikit-learn, PyOD, PyTorch, SHAP, FastAPI) · PostgreSQL · Redis · Docker

## Note on data
All data in this project is synthetically generated. No proprietary 
schemas, data, or code from any employer are used.

## Week 2 — Anomaly Detection Model

### Features engineered
- `z_score` — deviation from tenant+feature baseline (median/MAD, robust to outliers)
- `duplicate_count` — flags replayed/duplicate events
- `ingestion_lag_days` — flags backdated/out-of-order events

### Models tried
| Model | Precision | Recall | F1 |
|---|---|---|---|
| Isolation Forest | 0.753 | 1.0 | 0.859 |
| Local Outlier Factor (LOF) | 0.740 | 0.982 | 0.844 |

**Isolation Forest chosen** — caught 100% of labeled anomalies with fewer false positives.

### Key finding
Initial z-score used mean/std, which was skewed by extreme anomalies 
(masking effect) — missed 6 real spikes. Fixed by switching to median/MAD 
(robust statistics), improving recall from 0.891 → 1.0.


## Week 3 — Explainability (SHAP)

### Why
An anomaly score alone isn't enough — a real system needs to explain 
*why* something was flagged, both for trust and for debugging.

### What was built
- SHAP TreeExplainer wired into the Isolation Forest model
- Verified each anomaly type is explained by its correct feature:

| Anomaly Type | Dominant Feature | Avg |SHAP| |
|---|---|---|
| spike | z_score | 8.21 |
| negative_balance_attempt | z_score | 7.42 |
| replay | duplicate_count | 8.07 |
| out_of_order | ingestion_lag_days | 8.98 |

- `/analyze/{event_id}` — real endpoint returning prediction + plain-language reason

### Example

GET /analyze/1a8936a9-c691-4b37-9152-7305167ea98f

{
"is_anomaly": true,
"top_reason": "usage quantity is unusually far from this tenant's normal baseline",
"feature_contributions": {"z_score": -6.9, "duplicate_count": 0.11, "ingestion_lag_days": -0.75}
}

### Status
Week 3 complete. Next: deployment + polish (Week 4)