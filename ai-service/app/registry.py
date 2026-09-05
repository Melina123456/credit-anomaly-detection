import os
import time

import joblib
import pandas as pd

from app.db import insert_model_run, fetch_latest_model_run
from app.features import add_zscore_features, add_duplicate_features, add_lag_feature
from app.model import train_isolation_forest, FEATURE_COLUMNS
from app.evaluate import evaluate_model, evaluate_by_type

MODEL_DIR = os.getenv("MODEL_DIR", "models")


def add_all_features(df: pd.DataFrame) -> pd.DataFrame:
    df = add_zscore_features(df)
    df = add_duplicate_features(df)
    df = add_lag_feature(df)
    return df


def train_and_register(df_labeled: pd.DataFrame, contamination: float = 0.05) -> dict:
    """Fit a fresh model, evaluate it, persist the fitted model to disk, and
    record the run in model_run. Returns the metrics for this run so a
    caller (e.g. POST /train) can report them immediately.

    df_labeled must include an `is_anomaly` column (see
    app.db.fetch_usage_events_with_labels) since evaluation needs it.
    """
    if len(df_labeled) == 0:
        raise ValueError("no usage events to train on")

    df = add_all_features(df_labeled)
    df, model = train_isolation_forest(df, contamination=contamination)

    metrics = evaluate_model(df)
    by_type = evaluate_by_type(df)

    os.makedirs(MODEL_DIR, exist_ok=True)
    # timestamp in the filename keeps every trained model around instead of
    # overwriting the last one — cheap insurance if a bad training run needs
    # to be traced back to, at the cost of disk space nothing currently prunes.
    filename = f"isolation_forest_{int(time.time())}.joblib"
    model_path = os.path.join(MODEL_DIR, filename)
    joblib.dump(model, model_path)

    row = insert_model_run(
        model_path=model_path,
        feature_set=",".join(FEATURE_COLUMNS),
        training_row_count=len(df),
        contamination=contamination,
        precision_score=metrics["precision"],
        recall_score=metrics["recall"],
        f1_score=metrics["f1_score"],
    )

    return {
        "id": str(row.id),
        "trained_at": row.trained_at.isoformat(),
        "model_path": model_path,
        "training_row_count": len(df),
        "metrics": metrics,
        "by_type": by_type,
    }


def _row_to_metadata(row) -> dict:
    return {
        "id": str(row.id),
        "trained_at": row.trained_at.isoformat(),
        "model_path": row.model_path,
        "feature_set": row.feature_set,
        "training_row_count": row.training_row_count,
        "precision": float(row.precision_score) if row.precision_score is not None else None,
        "recall": float(row.recall_score) if row.recall_score is not None else None,
        "f1_score": float(row.f1_score) if row.f1_score is not None else None,
    }


def load_latest_model():
    """Return (model, metadata) for the most recently trained model, or
    (None, None) if nothing has been trained yet, or if the DB has a record
    of a run whose model file is missing from disk (e.g. the model volume
    was wiped without the DB being wiped too) — treated the same as "no
    model" rather than crashing the caller.
    """
    row = fetch_latest_model_run()

    if row is None:
        return None, None

    if not os.path.exists(row.model_path):
        return None, None

    model = joblib.load(row.model_path)
    return model, _row_to_metadata(row)
