import pandas as pd
import pytest

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.metrics import macro_auc, per_label_auc


def _constant_frame(value: float) -> pd.DataFrame:
    return pd.DataFrame({label: [value] * 4 for label in LABEL_COLUMNS})


def test_macro_auc_is_one_for_perfect_predictions():
    y_true = pd.DataFrame({label: [0, 0, 1, 1] for label in LABEL_COLUMNS})
    y_pred = pd.DataFrame(
        {label: [0.1, 0.2, 0.8, 0.9] for label in LABEL_COLUMNS}
    )

    assert macro_auc(y_true, y_pred) == pytest.approx(1.0)


def test_macro_auc_is_half_for_random_predictions_tied_at_midpoint():
    y_true = pd.DataFrame({label: [0, 0, 1, 1] for label in LABEL_COLUMNS})
    y_pred = _constant_frame(0.5)

    assert macro_auc(y_true, y_pred) == pytest.approx(0.5)


def test_per_label_auc_returns_one_score_per_label_column():
    y_true = pd.DataFrame({label: [0, 1, 0, 1] for label in LABEL_COLUMNS})
    y_pred = pd.DataFrame(
        {label: [0.2, 0.7, 0.3, 0.6] for label in LABEL_COLUMNS}
    )

    scores = per_label_auc(y_true, y_pred)

    assert set(scores.keys()) == set(LABEL_COLUMNS)
    # Both positives (0.7, 0.6) outrank both negatives (0.2, 0.3) in every
    # (identical) column, so every label's AUC is exactly 1.0.
    assert all(score == pytest.approx(1.0) for score in scores.values())


def test_macro_auc_raises_on_single_class_column():
    y_true = pd.DataFrame({label: [0, 0, 0, 0] for label in LABEL_COLUMNS})
    y_pred = _constant_frame(0.5)

    with pytest.raises(ValueError, match="only one class"):
        macro_auc(y_true, y_pred)


def _distinct_auc_frames() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Build a case where every label has a DIFFERENT, known AUC.

    Every other fixture here gives all 12 columns identical values, which
    makes three separate defects invisible at once: column identity (y
    scored against the wrong prediction column), and whether the macro is a
    mean, a max, or simply the first score. Distinct per-label AUCs pin all
    three.
    """
    truth = [0, 0, 1, 1]
    # Four prediction shapes with hand-checkable AUCs against `truth`.
    shapes = {
        1.0: [0.1, 0.2, 0.8, 0.9],  # perfectly ranked
        0.75: [0.1, 0.5, 0.4, 0.9],  # one inversion of four pairs
        0.5: [0.5, 0.5, 0.5, 0.5],  # no information
        0.0: [0.9, 0.8, 0.2, 0.1],  # perfectly anti-ranked
    }
    cycle = list(shapes.items())
    y_true, y_pred, expected = {}, {}, {}
    for position, label in enumerate(LABEL_COLUMNS):
        auc, prediction = cycle[position % len(cycle)]
        y_true[label] = truth
        y_pred[label] = prediction
        expected[label] = auc
    return pd.DataFrame(y_true), pd.DataFrame(y_pred), expected


def test_per_label_auc_scores_each_label_against_its_own_column():
    y_true, y_pred, expected = _distinct_auc_frames()

    scores = per_label_auc(y_true, y_pred)

    # Pins column identity: scoring every label against one shared column
    # (e.g. LABEL_COLUMNS[0]) would make these all equal.
    assert scores == pytest.approx(expected)
    assert len(set(scores.values())) > 1


def test_macro_auc_is_the_mean_not_the_max_or_the_first():
    y_true, y_pred, expected = _distinct_auc_frames()
    values = list(expected.values())

    result = macro_auc(y_true, y_pred)

    assert result == pytest.approx(sum(values) / len(values))
    # The mean must be distinguishable from the two plausible wrong
    # aggregations, otherwise this assertion proves nothing.
    assert result != pytest.approx(max(values))
    assert result != pytest.approx(values[0])


def test_per_label_auc_rejects_misaligned_indices():
    """`roc_auc_score` drops the index and pairs rows positionally, so a
    prediction frame whose index disagrees with `y_true` is scored silently
    against the wrong rows rather than raising. The in-repo caller builds the
    OOF frame with `index=y.index`, so this guards a trap rather than a live
    bug -- but a silently wrong AUC is exactly the failure this project
    treats as worse than a crash.
    """
    y_true = pd.DataFrame({label: [0, 0, 1, 1] for label in LABEL_COLUMNS}, index=[0, 1, 2, 3])
    y_pred = pd.DataFrame(
        {label: [0.1, 0.2, 0.8, 0.9] for label in LABEL_COLUMNS}, index=[3, 2, 1, 0]
    )

    with pytest.raises(ValueError, match="index"):
        per_label_auc(y_true, y_pred)


def test_a_single_label_frame_is_rejected_with_a_message_that_names_the_cause():
    """Both metrics score the full panel. Indexing a one-column frame raises
    a bare KeyError naming some unrelated label, which reads as a missing row
    and sends the reader to the wrong place.
    """
    truth = pd.DataFrame({label: [0, 1] for label in LABEL_COLUMNS})
    predictions = pd.DataFrame({label: [0.2, 0.8] for label in LABEL_COLUMNS})

    with pytest.raises(ValueError, match="missing label columns"):
        macro_auc(truth[[LABEL_COLUMNS[0]]], predictions[[LABEL_COLUMNS[0]]])

    with pytest.raises(ValueError, match="missing label columns"):
        per_label_auc(truth, predictions[[LABEL_COLUMNS[0]]])
