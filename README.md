# Multi-Service Credit & Entitlement Anomaly Detection

Applied ML system for detecting anomalous usage/credit patterns in a 
multi-tenant SaaS billing architecture. Extends a ledger-vs-cache 
design pattern (append-only transaction ledger + materialized read 
caches) with an ML anomaly detection layer and SHAP-based explainability.

## Status: Week 1 — Infrastructure (in progress)

## Architecture
- `/ingestion` — Go service: event ingestion, ledger writes, cache updates
- `/ai-service` — Python: anomaly detection models, SHAP explainability, API

## Stack
Go · Python (scikit-learn, PyOD, PyTorch, SHAP, FastAPI) · PostgreSQL · Redis · Docker

## Note on data
All data in this project is synthetically generated. No proprietary 
schemas, data, or code from any employer are used.
