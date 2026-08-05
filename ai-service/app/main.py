from fastapi import FastAPI
from app.db import fetch_usage_events
from app.features import add_duplicate_features, add_lag_feature, add_zscore_features
from app.model import train_isolation_forest


app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug/events")
def debug_events():
    df = fetch_usage_events()
    return {
        "row_count": len(df),
        "columns": list(df.columns),
        "sample": df.head(3).to_dict(orient="records")
    }


@app.get("/debug/features")
def debug_features():
    df = fetch_usage_events()
    df = add_zscore_features(df)
    df = add_duplicate_features(df)
    df = add_lag_feature(df)

    top_lag = df.sort_values("ingestion_lag_days", ascending=False).head(5)
    return top_lag[["tenant_id", "feature_id", "occurred_at", "ingested_at", "ingestion_lag_days"]].to_dict(orient="records")


@app.get("/debug/model")
def debug_model():
    df = fetch_usage_events()
    df = add_zscore_features(df)
    df = add_duplicate_features(df)
    df = add_lag_feature(df)
    df = train_isolation_forest(df)

    flagged = df[df["model_flag"] == -1]
    return {
        "total_events": len(df),
        "flagged_count": len(flagged),
        "sample_flagged": flagged[["tenant_id", "quantity", "z_score", "duplicate_count", "ingestion_lag_days", "anomaly_score"]].head(5).to_dict(orient="records")
    }