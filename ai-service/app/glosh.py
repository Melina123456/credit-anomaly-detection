"""GLOSH outlier scores with both of its settings chosen from the data.

GLOSH (the outlier score inside HDBSCAN*) needs two things a user normally
has to supply: min_pts, which controls how density is estimated, and a
threshold, which decides how many points count as outliers. Following
Ghosh, Naldi, Sander & Choo (2024, arXiv:2411.08867), both are derived here:

1. Score every point at every min_pts in [2, m_max]. Measure how much the
   scores change between consecutive min_pts values (the ORD-profile), and
   pick the min_pts where that change settles down — the elbow.
2. At that min_pts, find the knee of the sorted scores, then correct it
   (POLAR): fit a line to the scores before the knee, extrapolate it to the
   last point, and cut at the observed score closest to that projection.

GLOSH scores run 0..1 with HIGHER meaning more outlying — the opposite of
sklearn's convention used elsewhere in this project.
"""

import warnings

import hdbscan
import numpy as np


def glosh_scores(X: np.ndarray, min_pts: int) -> np.ndarray:
    with warnings.catch_warnings():
        # hdbscan emits a sklearn deprecation warning on every fit
        warnings.simplefilter("ignore")
        model = hdbscan.HDBSCAN(min_samples=min_pts, min_cluster_size=min_pts).fit(X)
    return np.nan_to_num(model.outlier_scores_, nan=0.0)


def glosh_profiles(X: np.ndarray, m_max: int = 100) -> dict:
    """{min_pts: scores} for every min_pts in [2, m_max]."""
    m_max = min(m_max, len(X) - 1)
    return {m: glosh_scores(X, m) for m in range(2, m_max + 1)}


def ord_profile(profiles: dict) -> tuple[np.ndarray, np.ndarray]:
    """Dissimilarity between the scores at each pair of consecutive min_pts.

    Uses 1 - |Pearson correlation|, with each point's score at min_pts k
    compared against the same point's score at k+1. The paper describes this
    as a dissimilarity between "sorted sequences" of scores; comparing the
    same points across the two settings is the reading under which the
    measure detects a ranking change at all (two vectors sorted
    independently correlate near 1 regardless), so that is the one used.

    Returns (min_pts values, dissimilarities), where entry i is the change
    going from min_pts[i] to min_pts[i] + 1.
    """
    ms = sorted(profiles)
    dissim = []
    for a, b in zip(ms, ms[1:]):
        sa, sb = profiles[a], profiles[b]
        if sa.std() == 0 or sb.std() == 0:
            dissim.append(1.0)
            continue
        dissim.append(1.0 - abs(np.corrcoef(sa, sb)[0, 1]))
    return np.array(ms[:-1]), np.array(dissim)


def _elbow_index(y: np.ndarray, start: int = 0) -> int:
    """Index (>= start) of the point furthest from the straight line joining
    y[start] to y[-1], using the paper's orthogonal distance
    ||AD x AB|| / ||AB||.

    That distance is unsigned, so it assumes the curve has one dominant
    bend. Sorted GLOSH scores can have several — a run of exact zeros in the
    densest core, a steep rise, a slow climb, then the jump to the outliers
    — and the furthest point can then sit on a bend inside the inliers.
    Restricting to one side of the line was tried and fails differently
    (it latches onto the zero run), so the literal formula is kept.
    """
    seg = y[start:]
    n = len(seg)
    if n < 3:
        return start
    x = np.arange(n, dtype=float)
    ab_x, ab_y = n - 1.0, seg[-1] - seg[0]
    norm = np.hypot(ab_x, ab_y)
    if norm == 0:
        return start
    dist = np.abs(ab_x * (seg - seg[0]) - ab_y * x) / norm
    return start + int(np.argmax(dist))


def select_min_pts(profiles: dict) -> int:
    """The min_pts where the ORD-profile stops falling steeply.

    The search starts at the largest dissimilarity rather than at min_pts=2:
    the very smallest values are noisy, and the elbow of interest is where
    the change settles after its peak.
    """
    ms, dissim = ord_profile(profiles)
    if len(dissim) == 0:
        return min(profiles)
    peak = int(np.argmax(dissim))
    return int(ms[_elbow_index(dissim, start=peak)])


def polar_cut(scores: np.ndarray) -> int:
    """How many points to flag, from the score distribution alone.

    Sorted ascending, inlier scores tend to rise roughly linearly and the
    outliers bend sharply upward at the end. The knee finds that bend, but
    tends to land too early. So: fit a line to everything before the knee
    (assumed inliers), extrapolate it to the final position — the score the
    last point "would" have had if it were an inlier — and cut at the
    observed score after the knee that is closest to that projection.
    Everything strictly above it is flagged.
    """
    s = np.sort(np.asarray(scores, dtype=float))
    n = len(s)
    if n < 3 or s[-1] == s[0]:
        return 0

    knee = _elbow_index(s)
    if knee < 2:
        return n - knee - 1

    slope, intercept = np.polyfit(np.arange(knee), s[:knee], 1)
    projected_last = intercept + slope * (n - 1)

    after = s[knee:]
    threshold = after[int(np.argmin(np.abs(after - projected_last)))]
    return int((s > threshold).sum())


def glosh_parameter_free(X: np.ndarray, m_max: int = 100) -> dict:
    """Both stages end to end. Returns the chosen min_pts, the scores at
    that setting, and how many points to flag — nothing supplied but X."""
    profiles = glosh_profiles(X, m_max)
    m_star = select_min_pts(profiles)
    scores = profiles[m_star]
    return {"min_pts": m_star, "scores": scores, "k": polar_cut(scores), "profiles": profiles}
