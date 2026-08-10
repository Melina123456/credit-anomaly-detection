import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

def fetch_usage_events() -> pd.DataFrame:
    query = "SELECT * FROM usage_event"
    return pd.read_sql(query, engine)

def fetch_usage_events_with_labels() -> pd.DataFrame:
    query = """
        SELECT ue.*, al.anomaly_type
        FROM usage_event ue
        LEFT JOIN anomaly_label al ON al.usage_event_id = ue.id
    """
    df = pd.read_sql(query, engine)
    df["is_anomaly"] = df["anomaly_type"].notna()
    return df