from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

def evaluate_model(df):
    y_true = df["is_anomaly"]
    y_pred = df["model_flag"] == -1  # True if model flagged it

    precision = precision_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred)

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