import pandas as pd

# credit_pool_balance.balance and the ledger sum are both NUMERIC in
# Postgres (exact decimals), so they should match exactly. This tolerance
# only exists to absorb float rounding introduced once pandas/Python takes
# the numbers over — it is not meant to hide a real discrepancy.
TOLERANCE = 0.01


def check_pool_consistency(df: pd.DataFrame) -> dict:
    """df must have one row per pool with cached_balance and ledger_balance
    columns (see app.db.fetch_pool_balance_consistency) computed by two
    independent paths. Flags any pool where they disagree by more than
    floating-point noise.
    """
    df = df.copy()
    df["cached_balance"] = df["cached_balance"].astype(float)
    df["ledger_balance"] = df["ledger_balance"].astype(float)
    df["difference"] = df["cached_balance"] - df["ledger_balance"]

    mismatches = df[df["difference"].abs() > TOLERANCE]

    return {
        "pools_checked": len(df),
        "consistent": len(mismatches) == 0,
        "mismatches": mismatches[
            ["pool_id", "tenant_name", "cached_balance", "ledger_balance", "difference"]
        ].to_dict(orient="records"),
    }
