from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

def evaluate_model(df, pred_col="model_flag", anomaly_value=-1):
    y_true = df["is_anomaly"]
    y_pred = df[pred_col] == anomaly_value

    # zero_division=0: if the model flags nothing (or nothing it flags is
    # correct), precision/recall would otherwise raise a sklearn warning and
    # silently fall back to 0 anyway — this makes that fallback explicit.
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    # labels=[False, True] pins the matrix to 2x2 even if one class is
    # entirely absent from a given batch (e.g. a dataset with zero labeled
    # anomalies) — without it, confusion_matrix shrinks to 1x1 and the
    # indexing below throws IndexError.
    cm = confusion_matrix(y_true, y_pred, labels=[False, True])

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1, 3),
        "confusion_matrix": {
            "true_negative": int(cm[0][0]),
            "false_positive": int(cm[0][1]),
            "false_negative": int(cm[1][0]),
            "true_positive": int(cm[1][1]),
        }
    }


def evaluate_by_type(df, pred_col="model_flag", anomaly_value=-1):
    """Detection rate (recall) broken down by injected anomaly type.

    Only meaningful for rows with a non-null anomaly_type — normal rows
    aren't typed, so precision isn't computed per type here: a false
    positive isn't "the wrong type", it's a normal event flagged at all,
    which is already captured by the aggregate confusion matrix in
    evaluate_model().
    """
    labeled = df[df["anomaly_type"].notna()]

    results = {}
    for anomaly_type, group in labeled.groupby("anomaly_type"):
        flagged = group[pred_col] == anomaly_value
        total = len(group)
        detected = int(flagged.sum())
        results[anomaly_type] = {
            "total": total,
            "detected": detected,
            "recall": round(detected / total, 3),
        }
    return results