from fastapi import FastAPI
from app.db import fetch_usage_events
from app.features import add_duplicate_features, add_zscore_features


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

    dupes = df[df["duplicate_count"] > 1]
    return {
        "duplicate_rows_found": len(dupes),
        "sample": dupes[["tenant_id", "feature_id", "quantity", "occurred_at", "duplicate_count"]].head(5).to_dict(orient="records")
    }