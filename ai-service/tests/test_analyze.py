import pandas as pd

from app.analyze import build_analysis


def _df():
    return pd.DataFrame({
        "id": ["evt-1", "evt-2"],
        "tenant_id": ["t1", "t2"],
        "model_flag": [-1, 1],           # evt-1 flagged, evt-2 not
        "anomaly_score": [-0.42, 0.10],
    })


def test_flagged_event_reports_the_dominant_shap_feature():
    df = _df()
    # shap_values indexed by row position: [z_score, duplicate_count, lag]
    shap_values = {
        0: [-6.9, 0.11, -0.75],  # z_score dominates by absolute value
        1: [0.01, 0.02, 0.01],
    }

    result = build_analysis(df, shap_values, "evt-1")

    assert result["is_anomaly"] is True
    assert result["top_reason"] == "usage quantity is unusually far from this tenant's normal baseline"
    assert result["feature_contributions"]["z_score"] == -6.9


def test_unflagged_event_has_no_top_reason():
    df = _df()
    shap_values = {
        0: [-6.9, 0.11, -0.75],
        1: [0.01, 0.02, 0.01],
    }

    result = build_analysis(df, shap_values, "evt-2")

    assert result["is_anomaly"] is False
    assert result["top_reason"] is None
    # feature_contributions is still populated even when not flagged —
    # callers may want the raw numbers regardless.
    assert "z_score" in result["feature_contributions"]


def test_unknown_event_id_returns_none():
    df = _df()
    shap_values = {0: [-6.9, 0.11, -0.75], 1: [0.01, 0.02, 0.01]}

    result = build_analysis(df, shap_values, "does-not-exist")

    assert result is None


def test_duplicate_dominant_reason_picks_duplicate_count():
    df = _df()
    shap_values = {
        0: [0.2, 8.07, -0.1],  # duplicate_count dominates
        1: [0.01, 0.02, 0.01],
    }

    result = build_analysis(df, shap_values, "evt-1")

    assert result["top_reason"] == "this event appears to be a duplicate of another event"
