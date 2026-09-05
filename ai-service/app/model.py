from sklearn.ensemble import IsolationForest
import pandas as pd
from pyod.models.lof import LOF
import shap

# single source of truth for which columns feed the model — training,
# scoring, and SHAP explanation all read from here so they can never
# quietly drift out of sync with each other.
FEATURE_COLUMNS = ["z_score", "duplicate_count", "ingestion_lag_days"]


def train_isolation_forest(df: pd.DataFrame, contamination: float = 0.05) -> pd.DataFrame:
    features = df[FEATURE_COLUMNS].fillna(0)

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


def predict_with_model(model, df: pd.DataFrame) -> pd.DataFrame:
    """Score df with an already-fitted model, instead of training a new one.

    This is what lets /analyze serve from a persisted model (see
    app/registry.py) rather than refitting IsolationForest on every request.
    """
    features = df[FEATURE_COLUMNS].fillna(0)
    df["model_flag"] = model.predict(features)
    df["anomaly_score"] = model.decision_function(features)
    return df


def train_lof(df: pd.DataFrame) -> pd.DataFrame:
    features = df[FEATURE_COLUMNS].fillna(0)

    model = LOF(contamination=0.05)
    model.fit(features)

    # pyod convention: 1 = anomaly, 0 = normal
    df["lof_flag"] = model.labels_
    df["lof_score"] = model.decision_scores_

    return df


def explain_with_shap(model, df):
    features = df[FEATURE_COLUMNS].fillna(0)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(features)
    return shap_values