from fastapi import FastAPI
from app.db import fetch_usage_events

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