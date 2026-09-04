from fastapi import FastAPI
from app.db import fetch_usage_events
from app.features import add_duplicate_features, add_lag_feature, add_zscore_features
from app.model import train_isolation_forest, train_lof, explain_with_shap
from app.db import fetch_usage_events_with_labels
from app.evaluate import evaluate_model, evaluate_by_type
from app.analyze import build_analysis


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


@app.get("/analyze/{event_id}")
def analyze_event(event_id: str):
    df = fetch_usage_events_with_labels()
    df = add_zscore_features(df)
    df = add_duplicate_features(df)
    df = add_lag_feature(df)
    df, model = train_isolation_forest(df)

    shap_values = explain_with_shap(model, df)
    result = build_analysis(df, shap_values, event_id)

    if result is None:
        return {"error": "event not found"}
    return result