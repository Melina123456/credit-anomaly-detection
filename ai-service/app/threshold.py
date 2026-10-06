"""Choosing how many events to flag by looking only at the score
distribution, instead of being handed an assumed anomaly rate.

Every function here takes anomaly scores and returns how many events to
flag. None of them are told, or allowed to infer, the true rate — that is
the entire point. sklearn's scores are lower = more anomalous, so the
arrays are sorted ascending and "the first k" means "the k most anomalous".
"""

import numpy as np


def _most_anomalous_first(scores) -> np.ndarray:
    return np.sort(np.asarray(scores, dtype=float))


def largest_gap_cut(scores, search_fraction: float = 0.20) -> int:
    """Cut at the biggest jump between neighbouring scores.

    The hope is that genuine anomalies sit in a clump separated from normal
    events by a visible cliff, and the cliff is findable without knowing how
    many anomalies there are.

    `search_fraction` bounds how deep to look. Without it, a single
    extraordinarily extreme event produces the largest gap all by itself and
    the answer is always "flag 1". That bound is a weaker assumption than
    naming an exact rate, but it is still an assumption, and it is the main
    thing keeping this method from being truly parameter-free.
    """
    s = _most_anomalous_first(scores)
    limit = max(2, int(len(s) * search_fraction))
    gaps = np.diff(s[:limit])
    return int(np.argmax(gaps)) + 1


def knee_cut(scores) -> int:
    """Cut at the knee of the sorted score curve.

    Draw a straight line from the most anomalous score to the least
    anomalous one, then find the score sitting furthest from that line. On a
    curve that drops steeply and then flattens, that point is the corner
    where "unusual" stops and "ordinary" begins.

    Needs no search window, so unlike largest_gap_cut it takes no parameter
    at all.
    """
    s = _most_anomalous_first(scores)
    n = len(s)
    if n < 3:
        return 1

    spread = s[-1] - s[0]
    if spread == 0:
        return 1

    x = np.arange(n, dtype=float) / (n - 1)
    y = (s - s[0]) / spread
    chord = y[0] + x * (y[-1] - y[0])
    return int(np.argmax(np.abs(y - chord))) + 1


def flags_from_cut(scores, k: int) -> np.ndarray:
    """Turn "flag the k most anomalous" into sklearn's -1/1 labels, so the
    existing evaluation code can grade it unchanged.

    Flags exactly k by rank. Cutting at a score value instead would flag every
    event tied with the k-th — and Isolation Forest scores do tie (dozens per
    dataset here), which silently flagged more than k on a third of runs.
    Ties at the boundary are broken by position, deterministically.
    """
    scores = np.asarray(scores, dtype=float)
    flags = np.ones(len(scores), dtype=int)
    if k > 0:
        flags[np.argsort(scores, kind="stable")[:k]] = -1
    return flags
