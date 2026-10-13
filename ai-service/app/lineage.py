import hashlib
import os

import pandas as pd

# The columns that define an event's content. Database ids are left out on
# purpose: they are random UUIDs, so the same seed regenerated on a fresh
# database gets new ids — a hash over them could never match across machines.
FINGERPRINT_COLUMNS = ["tenant_name", "feature_key", "quantity", "occurred_at", "ingested_at", "anomaly_type"]


class ModelIntegrityError(Exception):
    """The model file on disk is not the one its model_run row recorded."""


def data_fingerprint(df: pd.DataFrame) -> str:
    """sha256 of the training data's content. Rows are sorted first, so the
    hash depends only on which events exist, not on the order they arrived in.
    Two databases produce the same fingerprint exactly when they hold the
    same events with the same labels."""
    content = df[FINGERPRINT_COLUMNS].astype(str).sort_values(FINGERPRINT_COLUMNS)
    return hashlib.sha256(content.to_csv(index=False).encode()).hexdigest()


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str | None:
    """The commit the running image was built from. Containers have no .git,
    so this is passed in at build time; None when it wasn't."""
    return os.getenv("GIT_COMMIT") or None
