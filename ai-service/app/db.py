import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Created lazily, on first actual use, instead of the moment this module is
# imported. Importing app.db (directly, or transitively through app.registry
# or app.consistency) used to require DATABASE_URL to already be set, even
# for tests that never touch the database — that broke CI, which has no
# .env file by design. Now merely importing this module is always safe;
# only calling one of the functions below requires a real DATABASE_URL.
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(os.getenv("DATABASE_URL"))
    return _engine


def fetch_usage_events() -> pd.DataFrame:
    query = "SELECT * FROM usage_event"
    return pd.read_sql(query, get_engine())

def fetch_usage_events_with_labels() -> pd.DataFrame:
    query = """
        SELECT ue.*, al.anomaly_type
        FROM usage_event ue
        LEFT JOIN anomaly_label al ON al.usage_event_id = ue.id
    """
    df = pd.read_sql(query, get_engine())
    df["is_anomaly"] = df["anomaly_type"].notna()
    return df


def fetch_pool_balance_consistency() -> pd.DataFrame:
    """One row per credit pool: what the cache currently says the balance is
    (cached_balance) vs. what independently summing every transaction in the
    ledger produces (ledger_balance). The two are computed by entirely
    separate paths on purpose — this is what lets app.consistency prove the
    cache hasn't drifted from its source of truth, rather than just asserting
    it hasn't.
    """
    query = """
        SELECT
            cp.id AS pool_id,
            t.name AS tenant_name,
            COALESCE(cpb.balance, 0) AS cached_balance,
            COALESCE(ledger_sum.total, 0) AS ledger_balance
        FROM credit_pool cp
        JOIN tenant t ON t.id = cp.tenant_id
        LEFT JOIN credit_pool_balance cpb ON cpb.pool_id = cp.id
        LEFT JOIN (
            SELECT pool_id, SUM(amount) AS total
            FROM credit_transaction
            GROUP BY pool_id
        ) ledger_sum ON ledger_sum.pool_id = cp.id
    """
    return pd.read_sql(query, get_engine())


def insert_model_run(model_path, feature_set, training_row_count, contamination,
                      precision_score, recall_score, f1_score):
    """Persist one training run and return the inserted row (id, trained_at)."""
    with get_engine().begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO model_run
                    (model_path, feature_set, training_row_count, contamination,
                     precision_score, recall_score, f1_score)
                VALUES
                    (:model_path, :feature_set, :training_row_count, :contamination,
                     :precision_score, :recall_score, :f1_score)
                RETURNING id, trained_at
            """),
            {
                "model_path": model_path,
                "feature_set": feature_set,
                "training_row_count": training_row_count,
                "contamination": contamination,
                "precision_score": precision_score,
                "recall_score": recall_score,
                "f1_score": f1_score,
            },
        )
        return result.fetchone()


def fetch_latest_model_run():
    """Return the most recently trained model_run row, or None if the table
    is empty (i.e. /train has never been called)."""
    with get_engine().connect() as conn:
        result = conn.execute(
            text("""
                SELECT id, trained_at, model_path, feature_set, training_row_count,
                       precision_score, recall_score, f1_score
                FROM model_run
                ORDER BY trained_at DESC
                LIMIT 1
            """)
        )
        return result.fetchone()