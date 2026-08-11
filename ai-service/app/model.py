from sklearn.ensemble import IsolationForest
import pandas as pd
from pyod.models.lof import LOF
import shap

def train_isolation_forest(df: pd.DataFrame,contamination: float = 0.05) -> pd.DataFrame:
    features = df[["z_score", "duplicate_count", "ingestion_lag_days"]].fillna(0)

    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,  
        random_state=42
    )
    model.fit(features)

    # -1 = anomaly, 1 = normal (sklearn convention)
    df["model_flag"] = model.predict(features)
    df["anomaly_score"] = model.decision_function(features)

    return df, model

def train_lof(df: pd.DataFrame) -> pd.DataFrame:
    features = df[["z_score", "duplicate_count", "ingestion_lag_days"]].fillna(0)

    model = LOF(contamination=0.05)
    model.fit(features)

    # pyod convention: 1 = anomaly, 0 = normal
    df["lof_flag"] = model.labels_
    df["lof_score"] = model.decision_scores_

    return df


def explain_with_shap(model, df):
    features = df[["z_score", "duplicate_count", "ingestion_lag_days"]].fillna(0)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(features)
    return shap_values