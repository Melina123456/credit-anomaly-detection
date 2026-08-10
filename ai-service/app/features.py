import pandas as pd

# def add_zscore_features(df: pd.DataFrame) -> pd.DataFrame:
#     stats = df.groupby(["tenant_id", "feature_id"])["quantity"].agg(["mean", "std"]).reset_index()
#     stats.columns = ["tenant_id", "feature_id", "baseline_mean", "baseline_std"]

#     df = df.merge(stats, on=["tenant_id", "feature_id"], how="left")

#     # avoid divide-by-zero if std is 0
#     df["baseline_std"] = df["baseline_std"].replace(0, 1)

#     df["z_score"] = (df["quantity"] - df["baseline_mean"]) / df["baseline_std"]
#     return df

def add_zscore_features(df: pd.DataFrame) -> pd.DataFrame:
    def robust_stats(group):
        median = group.median()
        mad = (group - median).abs().median()
        return pd.Series({"baseline_median": median, "baseline_mad": mad})

    stats = df.groupby(["tenant_id", "feature_id"])["quantity"].apply(robust_stats).unstack().reset_index()

    df = df.merge(stats, on=["tenant_id", "feature_id"], how="left")

    # avoid divide-by-zero if MAD is 0
    df["baseline_mad"] = df["baseline_mad"].replace(0, 1)

    # modified z-score (standard robust statistics formula)
    df["z_score"] = 0.6745 * (df["quantity"] - df["baseline_median"]) / df["baseline_mad"]
    return df

def add_duplicate_features(df: pd.DataFrame) -> pd.DataFrame:
    dup_counts = df.groupby(
        ["tenant_id", "feature_id", "quantity", "occurred_at"]
    ).size().reset_index(name="duplicate_count")

    df = df.merge(dup_counts, on=["tenant_id", "feature_id", "quantity", "occurred_at"], how="left")
    return df


def add_lag_feature(df: pd.DataFrame) -> pd.DataFrame:
    df["ingestion_lag_days"] = (df["ingested_at"] - df["occurred_at"]).dt.total_seconds() / 86400
    return df