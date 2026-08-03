import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

def fetch_usage_events() -> pd.DataFrame:
    query = "SELECT * FROM usage_event"
    return pd.read_sql(query, engine)