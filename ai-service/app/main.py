from fastapi import FastAPI
from app.db import fetch_usage_events
from app.features import add_zscore_features


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
    top = df.sort_values("z_score", ascending=False).head(5)
    return top[["tenant_id", "feature_id", "quantity", "z_score"]].to_dict(orient="records")