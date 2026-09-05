import pandas as pd

from app.consistency import check_pool_consistency


def test_all_pools_matching_reports_consistent():
    df = pd.DataFrame({
        "pool_id": ["p1", "p2"],
        "tenant_name": ["Acme", "Tiny"],
        "cached_balance": [1000.0, 50.0],
        "ledger_balance": [1000.0, 50.0],
    })

    result = check_pool_consistency(df)

    assert result["pools_checked"] == 2
    assert result["consistent"] is True
    assert result["mismatches"] == []


def test_mismatched_pool_is_flagged_with_the_actual_difference():
    df = pd.DataFrame({
        "pool_id": ["p1", "p2"],
        "tenant_name": ["Acme", "Tiny"],
        "cached_balance": [1000.0, 999.0],   # p2's cache is wrong
        "ledger_balance": [1000.0, 50.0],    # ledger says 50, cache says 999
    })

    result = check_pool_consistency(df)

    assert result["consistent"] is False
    assert len(result["mismatches"]) == 1
    mismatch = result["mismatches"][0]
    assert mismatch["pool_id"] == "p2"
    assert mismatch["difference"] == 949.0


def test_tiny_floating_point_noise_does_not_count_as_a_mismatch():
    # e.g. 1000.0 vs 999.999999998 from float rounding somewhere upstream —
    # should not be reported as drift.
    df = pd.DataFrame({
        "pool_id": ["p1"],
        "tenant_name": ["Acme"],
        "cached_balance": [1000.0],
        "ledger_balance": [999.999999998],
    })

    result = check_pool_consistency(df)

    assert result["consistent"] is True


def test_empty_input_is_trivially_consistent():
    df = pd.DataFrame({
        "pool_id": [], "tenant_name": [], "cached_balance": [], "ledger_balance": [],
    })

    result = check_pool_consistency(df)

    assert result == {"pools_checked": 0, "consistent": True, "mismatches": []}
