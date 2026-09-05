from fastapi import FastAPI, HTTPException
from app.db import fetch_usage_events, fetch_pool_balance_consistency
from app.features import add_duplicate_features, add_lag_feature, add_zscore_features
from app.model import train_isolation_forest, train_lof, predict_with_model, explain_with_shap
from app.db import fetch_usage_events_with_labels
from app.evaluate import evaluate_model, evaluate_by_type
from app.analyze import build_analysis
from app.registry import train_and_register, load_latest_model, add_all_features
from app.consistency import check_pool_consistency


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
    df, model = train_isolation_forest(df)

    flagged = df[df["model_flag"] == -1]
    return {
        "total_events": len(df),
        "flagged_count": len(flagged),
        "sample_flagged": flagged[["tenant_id", "quantity", "z_score", "duplicate_count", "ingestion_lag_days", "anomaly_score"]].head(5).to_dict(orient="records")
    }


@app.get("/debug/evaluate")
def debug_evaluate():
    df = fetch_usage_events_with_labels()
    df = add_zscore_features(df)
    df = add_duplicate_features(df)
    df = add_lag_feature(df)
    df, model = train_isolation_forest(df)

    return {
        "aggregate": evaluate_model(df),
        "by_type": evaluate_by_type(df),
    }


@app.get("/debug/missed")
def debug_missed():
    df = fetch_usage_events_with_labels()
    df = add_zscore_features(df)
    df = add_duplicate_features(df)
    df = add_lag_feature(df)
    df, model = train_isolation_forest(df)

    missed = df[(df["is_anomaly"] == True) & (df["model_flag"] != -1)]
    return missed[["tenant_id", "anomaly_type", "quantity", "z_score", "duplicate_count", "ingestion_lag_days", "anomaly_score"]].to_dict(orient="records")

@app.get("/debug/compare")
def debug_compare():
    df = fetch_usage_events_with_labels()
    df = add_zscore_features(df)
    df = add_duplicate_features(df)
    df = add_lag_feature(df)

    df, model = train_isolation_forest(df)
    df = train_lof(df)

    iso_results = evaluate_model(df, pred_col="model_flag", anomaly_value=-1)
    lof_results = evaluate_model(df, pred_col="lof_flag", anomaly_value=1)

    return {
        "isolation_forest": iso_results,
        "lof": lof_results
    }


@app.get("/debug/explain")
def debug_explain():
    df = fetch_usage_events_with_labels()
    df = add_zscore_features(df)
    df = add_duplicate_features(df)
    df = add_lag_feature(df)
    df, model = train_isolation_forest(df)


    shap_values = explain_with_shap(model, df)

    # pick one flagged anomaly to explain
    flagged_idx = df[df["model_flag"] == -1].index[0]

    return {
        "tenant_id": str(df.loc[flagged_idx, "tenant_id"]),
        "anomaly_type": str(df.loc[flagged_idx, "anomaly_type"]),
        "quantity": float(df.loc[flagged_idx, "quantity"]),
        "z_score": float(df.loc[flagged_idx, "z_score"]),
        "duplicate_count": int(df.loc[flagged_idx, "duplicate_count"]),
        "ingestion_lag_days": float(df.loc[flagged_idx, "ingestion_lag_days"]),
        "shap_values": {
            "z_score": float(shap_values[flagged_idx][0]),
            "duplicate_count": float(shap_values[flagged_idx][1]),
            "ingestion_lag_days": float(shap_values[flagged_idx][2]),
        }
    }


@app.get("/debug/explain-all")
def debug_explain_all():
    df = fetch_usage_events_with_labels()
    df = add_zscore_features(df)
    df = add_duplicate_features(df)
    df = add_lag_feature(df)
    df, model = train_isolation_forest(df)

    shap_values = explain_with_shap(model, df)

    flagged = df[df["model_flag"] == -1].copy()
    flagged["shap_zscore"] = [shap_values[i][0] for i in flagged.index]
    flagged["shap_duplicate"] = [shap_values[i][1] for i in flagged.index]
    flagged["shap_lag"] = [shap_values[i][2] for i in flagged.index]

    # average |SHAP value| per known anomaly type
    summary = flagged.groupby("anomaly_type")[["shap_zscore", "shap_duplicate", "shap_lag"]].apply(
        lambda x: x.abs().mean()
    )

    return summary.reset_index().to_dict(orient="records")


@app.get("/debug/consistency-check")
def consistency_check():
    """Independently re-sums the ledger per pool and compares it against the
    cached balance credit_pool_balance currently holds — proof the cache
    hasn't drifted from its source of truth, rather than an assumption that
    it hasn't."""
    df = fetch_pool_balance_consistency()
    return check_pool_consistency(df)


@app.post("/train")
def train():
    """Fit a fresh model on the current data, persist it, and record the run.

    This is the only endpoint allowed to fit a model — everything else
    (/analyze, /model/current) reads whatever this last produced. Call it
    once after ingestion has run, and again whenever you want the served
    model refreshed against new data.
    """
    df = fetch_usage_events_with_labels()
    try:
        return train_and_register(df)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/model/current")
def model_current():
    """Metadata for whichever model /analyze is currently serving from —
    a minimal model card: when it was trained, on how much data, and how
    it scored. Read-only; does not train anything."""
    _, metadata = load_latest_model()
    if metadata is None:
        return {"trained": False, "message": "no model trained yet — call POST /train first"}
    return {"trained": True, **metadata}


@app.get("/analyze/{event_id}")
def analyze_event(event_id: str):
    model, _ = load_latest_model()
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="no trained model available yet — call POST /train first",
        )

    df = fetch_usage_events_with_labels()
    df = add_all_features(df)
    df = predict_with_model(model, df)

    shap_values = explain_with_shap(model, df)
    result = build_analysis(df, shap_values, event_id)

    if result is None:
        return {"error": "event not found"}
    return result