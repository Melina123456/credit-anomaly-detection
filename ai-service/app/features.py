import pandas as pd

def add_zscore_features(df: pd.DataFrame) -> pd.DataFrame:
    stats = df.groupby(["tenant_id", "feature_id"])["quantity"].agg(["mean", "std"]).reset_index()
    stats.columns = ["tenant_id", "feature_id", "baseline_mean", "baseline_std"]

    df = df.merge(stats, on=["tenant_id", "feature_id"], how="left")

    # avoid divide-by-zero if std is 0
    df["baseline_std"] = df["baseline_std"].replace(0, 1)

    df["z_score"] = (df["quantity"] - df["baseline_mean"]) / df["baseline_std"]
    return df

def add_duplicate_features(df: pd.DataFrame) -> pd.DataFrame:
    dup_counts = df.groupby(
        ["tenant_id", "feature_id", "quantity", "occurred_at"]
    ).size().reset_index(name="duplicate_count")

    df = df.merge(dup_counts, on=["tenant_id", "feature_id", "quantity", "occurred_at"], how="left")
    return df