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
