from app.scoring import _compute_zscore


def test_zscore_is_zero_at_the_median():
    assert _compute_zscore(quantity=50, median=50, mad=10) == 0


def test_zscore_matches_the_bulk_formula_in_features_py():
    # same numbers as tests/test_features.py's spike case: median=10, and a
    # value of 50 against that baseline. Both implementations must agree.
    assert _compute_zscore(quantity=50, median=10, mad=1) == 0.6745 * (50 - 10) / 1


def test_zscore_handles_zero_mad_without_dividing_by_zero():
    # every observed value identical -> MAD is 0 -> treated as 1, same rule
    # as the bulk version in features.py.
    result = _compute_zscore(quantity=7, median=7, mad=0)
    assert result == 0

    result = _compute_zscore(quantity=10, median=7, mad=0)
    assert result == 0.6745 * (10 - 7) / 1


def test_zscore_is_negative_below_the_median():
    assert _compute_zscore(quantity=1, median=10, mad=2) < 0
