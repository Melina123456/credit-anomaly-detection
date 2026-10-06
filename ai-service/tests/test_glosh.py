import numpy as np

from app.glosh import _elbow_index, glosh_parameter_free, ord_profile, polar_cut


def test_polar_cut_flags_exactly_the_jump_on_a_single_bend_curve():
    # the shape POLAR is designed for: inlier scores rising in a straight
    # line, then a clear jump to 5 outliers
    scores = np.concatenate([np.linspace(0.0, 0.3, 100), [0.9, 0.92, 0.95, 0.97, 1.0]])

    assert polar_cut(scores) == 5


def test_polar_cut_flags_nothing_when_there_is_no_curve_to_read():
    assert polar_cut([0.1, 0.9]) == 0  # too few points for a knee
    assert polar_cut([0.5] * 50) == 0  # every score identical


def test_polar_cut_known_limitation_on_a_curve_with_several_bends():
    # sorted GLOSH scores on real data often look like this: a run of exact
    # zeros (densest core points), a steep rise, a slow climb, then the jump
    # to the true outliers. The paper's unsigned knee distance picks a bend
    # inside the inliers, so POLAR flags far more than the 5 real outliers.
    # Pinned so a future change to the knee step shows up here.
    scores = np.concatenate([
        np.zeros(24),
        np.linspace(0.0, 0.35, 26),
        np.linspace(0.35, 0.88, 150),
        [0.98] * 5,
    ])

    assert polar_cut(scores) > 100


def test_ord_profile_is_zero_when_scores_do_not_change_between_settings():
    a = np.array([0.1, 0.5, 0.9, 0.2])

    ms, dissim = ord_profile({2: a, 3: a.copy()})

    assert list(ms) == [2]
    assert dissim[0] == 0.0


def test_ord_profile_treats_a_constant_score_vector_as_maximally_different():
    # correlation is undefined when one side has zero variance; guarded to
    # 1.0 instead of letting a NaN poison the elbow search
    a = np.array([0.1, 0.5, 0.9, 0.2])

    _, dissim = ord_profile({2: a, 3: np.zeros(4)})

    assert dissim[0] == 1.0


def test_elbow_index_finds_where_a_falling_curve_flattens():
    # the ORD-profile shape: large changes at small min_pts, then settling
    curve = np.array([10, 5, 1, 0.9, 0.8, 0.7, 0.6, 0.5])

    assert _elbow_index(curve) == 2


def test_parameter_free_glosh_ranks_obvious_outliers_highest():
    # even where the threshold step struggles, the ranking itself should
    # put 5 far-away points above a gaussian blob of 200
    rng = np.random.RandomState(0)
    far = np.array([[8, 8], [-8, 8], [8, -8], [-8, -8], [10, 0]])
    X = np.vstack([rng.randn(200, 2), far])

    result = glosh_parameter_free(X, m_max=20)

    assert 2 <= result["min_pts"] <= 20
    assert len(result["scores"]) == len(X)
    assert 0 <= result["k"] <= len(X)
    assert set(np.argsort(-result["scores"])[:5]) == set(range(200, 205))
