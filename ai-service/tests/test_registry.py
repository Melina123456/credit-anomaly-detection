from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest

from app.registry import train_and_register, _row_to_metadata


def test_train_and_register_rejects_empty_dataframe():
    # guards against ever fitting IsolationForest on zero rows, which
    # sklearn would otherwise fail on less clearly (or not at all, and
    # silently persist a useless model). This path never reaches the
    # database, so it's safe to unit test without Postgres running.
    with pytest.raises(ValueError):
        train_and_register(pd.DataFrame())


def test_row_to_metadata_converts_db_row_into_plain_dict():
    # simulates what SQLAlchemy hands back from the model_run SELECT:
    # NUMERIC columns come back as Decimal, not float.
    row = SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        trained_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        model_path="models/isolation_forest_123.joblib",
        feature_set="z_score,duplicate_count,ingestion_lag_days",
        training_row_count=2910,
        precision_score=Decimal("0.753"),
        recall_score=Decimal("1.0"),
        f1_score=Decimal("0.859"),
    )

    metadata = _row_to_metadata(row)

    assert metadata["id"] == "11111111-1111-1111-1111-111111111111"
    assert metadata["training_row_count"] == 2910
    assert metadata["precision"] == 0.753
    assert isinstance(metadata["precision"], float)


def test_row_to_metadata_handles_null_metrics():
    # precision/recall/f1 are nullable columns — a training run could in
    # principle be recorded before evaluation runs. Make sure that doesn't
    # crash with "float() argument must be ... not 'NoneType'".
    row = SimpleNamespace(
        id="22222222-2222-2222-2222-222222222222",
        trained_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        model_path="models/isolation_forest_456.joblib",
        feature_set="z_score,duplicate_count,ingestion_lag_days",
        training_row_count=0,
        precision_score=None,
        recall_score=None,
        f1_score=None,
    )

    metadata = _row_to_metadata(row)

    assert metadata["precision"] is None
    assert metadata["recall"] is None
    assert metadata["f1_score"] is None
