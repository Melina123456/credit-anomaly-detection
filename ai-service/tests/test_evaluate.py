import pandas as pd

from app.evaluate import evaluate_model


def test_perfect_predictions_score_1_across_the_board():
    df = pd.DataFrame({
        "is_anomaly": [True, False, True, False],
        "model_flag": [-1, 1, -1, 1],
    })

    result = evaluate_model(df)

    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1_score"] == 1.0
    assert result["confusion_matrix"] == {
        "true_negative": 2,
        "false_positive": 0,
        "false_negative": 0,
        "true_positive": 2,
    }


def test_model_that_flags_nothing_does_not_crash_or_warn():
    # this is the case the zero_division=0 fix guards: some real anomalies
    # exist, but the model predicted "normal" for everything.
    df = pd.DataFrame({
        "is_anomaly": [True, False, True, False],
        "model_flag": [1, 1, 1, 1],
    })

    result = evaluate_model(df)

    assert result["precision"] == 0.0
    assert result["recall"] == 0.0
    assert result["f1_score"] == 0.0
    assert result["confusion_matrix"]["true_positive"] == 0
    assert result["confusion_matrix"]["false_negative"] == 2


def test_dataset_with_zero_labeled_anomalies_still_returns_a_2x2_matrix():
    # before the labels=[False, True] fix, confusion_matrix would collapse
    # to 1x1 here (only one class present in y_true) and cm[1][0] would
    # raise IndexError.
    df = pd.DataFrame({
        "is_anomaly": [False, False, False],
        "model_flag": [1, 1, -1],
    })

    result = evaluate_model(df)

    assert result["confusion_matrix"]["false_positive"] == 1
    assert result["confusion_matrix"]["true_positive"] == 0
    assert result["confusion_matrix"]["false_negative"] == 0


def test_alternate_pred_col_and_anomaly_value_for_lof_convention():
    # pyod's LOF uses the opposite convention from IsolationForest:
    # 1 = anomaly, 0 = normal. evaluate_model is called with different
    # pred_col/anomaly_value args for that model in /debug/compare.
    df = pd.DataFrame({
        "is_anomaly": [True, False],
        "lof_flag": [1, 0],
    })

    result = evaluate_model(df, pred_col="lof_flag", anomaly_value=1)

    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
