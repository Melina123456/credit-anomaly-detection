import pandas as pd

from app.features import add_zscore_features, add_duplicate_features, add_lag_feature


def test_zscore_is_zero_at_the_median():
    # 4 normal-ish values plus one big outlier for the same tenant/feature.
    df = pd.DataFrame({
        "tenant_id": ["t1"] * 5,
        "feature_id": ["f1"] * 5,
        "quantity": [10, 10, 10, 10, 50],
    })

    out = add_zscore_features(df)

    # every value equal to the group median gets z_score == 0 exactly,
    # regardless of what MAD came out to.
    median_rows = out[out["quantity"] == 10]
    assert (median_rows["z_score"] == 0).all()


def test_zscore_handles_zero_mad_without_dividing_by_zero():
    # all values identical -> median absolute deviation is 0. The function
    # is supposed to replace that 0 with 1 so this doesn't raise or produce
    # inf/NaN.
    df = pd.DataFrame({
        "tenant_id": ["t1"] * 4,
        "feature_id": ["f1"] * 4,
        "quantity": [7, 7, 7, 7],
    })

    out = add_zscore_features(df)

    assert (out["z_score"] == 0).all()
    assert out["z_score"].notna().all()


def test_zscore_is_computed_per_tenant_and_feature_group():
    # two independent groups with different baselines shouldn't leak into
    # each other's median/MAD.
    df = pd.DataFrame({
        "tenant_id": ["t1", "t1", "t1", "t2", "t2", "t2"],
        "feature_id": ["f1"] * 3 + ["f1"] * 3,
        "quantity": [10, 10, 10, 1000, 1000, 1000],
    })

    out = add_zscore_features(df)

    assert (out["z_score"] == 0).all()  # every row sits exactly on its own group's median


def test_duplicate_count_flags_exact_repeats():
    ts = pd.Timestamp("2026-01-01T00:00:00Z")
    df = pd.DataFrame({
        "tenant_id": ["t1", "t1", "t1"],
        "feature_id": ["f1", "f1", "f1"],
        "quantity": [5, 5, 9],
        "occurred_at": [ts, ts, ts],
    })

    out = add_duplicate_features(df)

    duplicated_rows = out[out["quantity"] == 5]
    unique_row = out[out["quantity"] == 9]

    assert (duplicated_rows["duplicate_count"] == 2).all()
    assert (unique_row["duplicate_count"] == 1).all()


def test_lag_feature_computes_days_between_ingested_and_occurred():
    df = pd.DataFrame({
        "occurred_at": pd.to_datetime(["2026-01-01T00:00:00Z"]),
        "ingested_at": pd.to_datetime(["2026-01-05T00:00:00Z"]),
    })

    out = add_lag_feature(df)

    assert out["ingestion_lag_days"].iloc[0] == 4.0


def test_lag_feature_is_negative_when_ingested_before_occurred():
    # this shouldn't normally happen in production data, but the function
    # doesn't guard against it — pin down that it degrades to a negative
    # number rather than raising, since /analyze reports it as a raw feature.
    df = pd.DataFrame({
        "occurred_at": pd.to_datetime(["2026-01-05T00:00:00Z"]),
        "ingested_at": pd.to_datetime(["2026-01-01T00:00:00Z"]),
    })

    out = add_lag_feature(df)

    assert out["ingestion_lag_days"].iloc[0] == -4.0
