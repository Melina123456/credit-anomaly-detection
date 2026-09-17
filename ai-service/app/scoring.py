import pandas as pd

from app.db import fetch_event_by_id, fetch_duplicate_count
from app.cache import get_baseline
from app.model import predict_with_model, explain_with_shap
from app.analyze import build_analysis


def _compute_zscore(quantity: float, median: float, mad: float) -> float:
    """Same modified z-score formula as add_zscore_features in features.py.
    Kept as a separate copy rather than a shared function: that one operates
    on a whole pandas Series at once (vectorized, for training), this one
    scores a single event (plain Python floats) — forcing both shapes
    through one function would obscure more than a two-line formula is
    worth duplicating. If the formula changes, update both."""
    safe_mad = mad if mad != 0 else 1
    return 0.6745 * (quantity - median) / safe_mad


def score_event(model, event_id: str):
    """Score exactly one event using its tenant/feature's cached baseline
    (written by the last POST /train), instead of recomputing baselines
    from the entire usage_event table just to look at one row.

    Returns None if the event doesn't exist. Raises LookupError if the
    event's tenant/feature was never part of a training run, so nothing is
    cached for it yet — treated the same as "no model trained" by the
    caller: a clear failure, not a silent guess.
    """
    row = fetch_event_by_id(event_id)
    if row is None:
        return None

    baseline = get_baseline(row.tenant_id, row.feature_id)
    if baseline is None:
        raise LookupError(
            f"no cached baseline for tenant={row.tenant_id} feature={row.feature_id} "
            "— this tenant/feature wasn't part of the last training run, call POST /train"
        )
    median, mad = baseline

    z_score = _compute_zscore(float(row.quantity), median, mad)
    duplicate_count = fetch_duplicate_count(row.tenant_id, row.feature_id, row.quantity, row.occurred_at)
    ingestion_lag_days = (row.ingested_at - row.occurred_at).total_seconds() / 86400

    df = pd.DataFrame([{
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "z_score": z_score,
        "duplicate_count": duplicate_count,
        "ingestion_lag_days": ingestion_lag_days,
    }])

    df = predict_with_model(model, df)
    shap_values = explain_with_shap(model, df)

    return build_analysis(df, shap_values, event_id)
