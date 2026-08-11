def build_analysis(df, shap_values, event_id: str):
    row = df[df["id"].astype(str) == event_id]
    if row.empty:
        return None

    idx = row.index[0]
    is_flagged = df.loc[idx, "model_flag"] == -1

    shap_scores = {
        "z_score": float(shap_values[idx][0]),
        "duplicate_count": float(shap_values[idx][1]),
        "ingestion_lag_days": float(shap_values[idx][2]),
    }

    # find the dominant reason (largest absolute SHAP value)
    top_reason = max(shap_scores, key=lambda k: abs(shap_scores[k]))

    reason_text = {
        "z_score": "usage quantity is unusually far from this tenant's normal baseline",
        "duplicate_count": "this event appears to be a duplicate of another event",
        "ingestion_lag_days": "this event was recorded long after it supposedly occurred",
    }

    return {
        "event_id": event_id,
        "tenant_id": str(df.loc[idx, "tenant_id"]),
        "is_anomaly": bool(is_flagged),
        "anomaly_score": float(df.loc[idx, "anomaly_score"]),
        "top_reason": reason_text[top_reason] if is_flagged else None,
        "feature_contributions": shap_scores,
    }