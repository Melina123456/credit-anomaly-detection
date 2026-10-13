from types import SimpleNamespace

import joblib
import pandas as pd
import pytest

from app import registry
from app.lineage import ModelIntegrityError, data_fingerprint, file_sha256


def _events():
    return pd.DataFrame({
        "id": ["a1", "a2", "a3"],
        "tenant_id": ["t-uuid-1", "t-uuid-1", "t-uuid-2"],
        "tenant_name": ["Acme Corp", "Acme Corp", "Tiny Startup"],
        "feature_key": ["api_calls", "storage_gb", "api_calls"],
        "quantity": [12.5, 3.0, 2653.0],
        "occurred_at": pd.to_datetime(["2025-12-30T10:00Z", "2025-12-30T11:00Z", "2025-12-31T09:00Z"]),
        "ingested_at": pd.to_datetime(["2026-01-01T00:00Z", "2026-01-01T00:00Z", "2026-01-01T00:01Z"]),
        "anomaly_type": [None, None, "spike"],
    })


def test_fingerprint_ignores_database_ids():
    # the same seed regenerated on a fresh database gets new random UUIDs;
    # the fingerprint must still match, or it can't show two runs saw the same data
    other_db = _events().assign(id=["b1", "b2", "b3"], tenant_id=["x", "x", "y"])
    assert data_fingerprint(other_db) == data_fingerprint(_events())


def test_fingerprint_ignores_row_order():
    shuffled = _events().iloc[[2, 0, 1]].reset_index(drop=True)
    assert data_fingerprint(shuffled) == data_fingerprint(_events())


def test_fingerprint_changes_when_one_quantity_changes():
    changed = _events()
    changed.loc[0, "quantity"] = 12.6
    assert data_fingerprint(changed) != data_fingerprint(_events())


def test_fingerprint_changes_when_a_label_changes():
    # same events, different answer key: a model graded against different
    # labels must not look like it was evaluated on the same data
    relabeled = _events()
    relabeled.loc[2, "anomaly_type"] = None
    assert data_fingerprint(relabeled) != data_fingerprint(_events())


def _run_row(model_path, model_sha256):
    return SimpleNamespace(
        id="run-1", trained_at=pd.Timestamp("2026-01-01", tz="UTC"), model_path=model_path,
        feature_set="z_score", training_row_count=3, precision_score=None, recall_score=None,
        f1_score=None, data_sha256="d", model_sha256=model_sha256, git_commit=None,
        seed=5, reference_time=pd.Timestamp("2026-01-01", tz="UTC"), anomaly_counts="spike=15",
    )


def test_load_latest_model_refuses_a_file_that_does_not_match_its_record(tmp_path, monkeypatch):
    path = tmp_path / "model.joblib"
    joblib.dump({"weights": 1}, path)
    recorded = file_sha256(str(path))
    joblib.dump({"weights": 2}, path)  # replaced after the run was recorded

    monkeypatch.setattr(registry, "fetch_latest_model_run", lambda: _run_row(str(path), recorded))
    with pytest.raises(ModelIntegrityError):
        registry.load_latest_model()


def test_load_latest_model_returns_lineage_when_the_file_matches(tmp_path, monkeypatch):
    path = tmp_path / "model.joblib"
    joblib.dump({"weights": 1}, path)

    monkeypatch.setattr(registry, "fetch_latest_model_run", lambda: _run_row(str(path), file_sha256(str(path))))
    model, metadata = registry.load_latest_model()

    assert model == {"weights": 1}
    assert metadata["lineage"]["seed"] == 5
    assert metadata["lineage"]["anomaly_counts"] == "spike=15"


def test_load_latest_model_skips_the_check_for_runs_recorded_before_hashing(tmp_path, monkeypatch):
    path = tmp_path / "model.joblib"
    joblib.dump({"weights": 1}, path)

    monkeypatch.setattr(registry, "fetch_latest_model_run", lambda: _run_row(str(path), None))
    model, _ = registry.load_latest_model()
    assert model == {"weights": 1}
