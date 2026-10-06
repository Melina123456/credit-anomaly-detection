import numpy as np

from app.threshold import largest_gap_cut, knee_cut, flags_from_cut


def test_largest_gap_cut_finds_the_single_big_jump():
    scores = [0.0, 0.1, 0.2, 5.0, 5.1, 5.2]
    # sorted, the jump from 0.2 to 5.0 dwarfs every neighbouring 0.1 step

    cut = largest_gap_cut(scores, search_fraction=1.0)

    assert cut == 3  # flag the 3 lowest scores: 0.0, 0.1, 0.2


def test_largest_gap_cut_search_fraction_can_hide_the_real_gap():
    # same data as above, but the window is too narrow to reach the jump at
    # position 3 — this is the exact failure search_fraction exists to avoid
    # (one freak score creating a "gap" of 1), and also its cost: a real gap
    # just past the window is invisible to the method.
    scores = [0.0, 0.1, 0.2, 5.0, 5.1, 5.2]

    cut = largest_gap_cut(scores, search_fraction=0.5)

    assert cut == 1


def test_largest_gap_cut_always_searches_at_least_two_points():
    # search_fraction=0.01 on 10 points would ask for a window of 0, which
    # can't be diffed at all — this is the max(2, ...) floor being exercised.
    scores = list(range(10))

    cut = largest_gap_cut(scores, search_fraction=0.01)

    assert cut >= 1


def test_knee_cut_finds_the_corner_of_a_steep_then_flat_curve():
    scores = [-10, -9.5, -9, -2, -1.5, -1, -0.8, -0.6, -0.5, -0.4]
    # steep drop for the first 4 points, then flattens out

    cut = knee_cut(scores)

    assert cut == 4


def test_knee_cut_fewer_than_three_points_returns_one():
    # the chord-distance formula needs at least 3 points to mean anything —
    # this is the guard against dividing by (n - 1) = 1 or 0.
    assert knee_cut([1.0, 2.0]) == 1
    assert knee_cut([1.0]) == 1
    assert knee_cut([]) == 1


def test_knee_cut_all_identical_scores_returns_one_not_a_division_by_zero():
    # spread = max - min = 0 here; without the explicit guard this divides
    # by zero when normalizing the curve to 0..1.
    assert knee_cut([3.0] * 10) == 1


def test_flags_from_cut_flags_exactly_k_when_scores_are_unique():
    scores = [5, 1, 3, 2, 4]

    flags = flags_from_cut(scores, k=2)

    assert list(flags) == [1, -1, 1, -1, 1]  # the two lowest: 1 and 2


def test_flags_from_cut_zero_or_negative_k_flags_nothing():
    scores = [5, 1, 3, 2, 4]

    assert list(flags_from_cut(scores, k=0)) == [1, 1, 1, 1, 1]
    assert list(flags_from_cut(scores, k=-3)) == [1, 1, 1, 1, 1]


def test_flags_from_cut_flags_exactly_k_even_when_scores_tie_at_the_cutoff():
    # three scores tie for 2nd-lowest. Cutting by score value would flag all
    # of them (4 total); Isolation Forest scores really do tie, so this once
    # inflated results on a third of runs. Exactly k must be flagged, with the
    # tie broken by position.
    scores = [1, 2, 2, 2, 5]

    flags = flags_from_cut(scores, k=2)

    assert (flags == -1).sum() == 2
    assert list(flags) == [-1, -1, 1, 1, 1]
