import numpy as np
import pandas as pd
import pytest

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.model_selection import select_multilabel_folds


def _alternating_targets(row_count: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            label: [(row_index + label_index) % 2 for row_index in range(row_count)]
            for label_index, label in enumerate(LABEL_COLUMNS)
        }
    )


def _assert_validation_folds_have_both_classes(
    y: pd.DataFrame,
    folds: tuple[tuple[np.ndarray, np.ndarray], ...],
) -> None:
    for _, validation_indices in folds:
        assert y.iloc[validation_indices].nunique().eq(2).all()


def test_select_multilabel_folds_is_repeatable_and_prefers_five() -> None:
    y = _alternating_targets(60)

    first_count, first_folds = select_multilabel_folds(y)
    second_count, second_folds = select_multilabel_folds(y)

    assert first_count == second_count == 5
    assert len(first_folds) == len(second_folds) == 5
    for first, second in zip(first_folds, second_folds, strict=True):
        np.testing.assert_array_equal(first[0], second[0])
        np.testing.assert_array_equal(first[1], second[1])
    _assert_validation_folds_have_both_classes(y, first_folds)


def test_select_multilabel_folds_falls_back_when_five_is_impossible() -> None:
    y = pd.DataFrame(
        {
            label: [
                int((row_index + label_index) % 3 == 0) for row_index in range(12)
            ]
            for label_index, label in enumerate(LABEL_COLUMNS)
        }
    )

    selected_count, folds = select_multilabel_folds(y)

    assert selected_count == 4
    assert len(folds) == 4
    _assert_validation_folds_have_both_classes(y, folds)


def test_select_multilabel_folds_raises_when_every_candidate_fails() -> None:
    y = _alternating_targets(12)
    y["ACL"] = 0
    y.loc[0, "ACL"] = 1

    with pytest.raises(ValueError, match="No candidate fold count"):
        select_multilabel_folds(y)


def test_select_multilabel_folds_rejects_noncanonical_columns() -> None:
    y = _alternating_targets(12).rename(columns={"ACL": "acl"})

    with pytest.raises(ValueError, match="canonical order"):
        select_multilabel_folds(y)


def test_select_multilabel_folds_rejects_non_binary_targets() -> None:
    y = _alternating_targets(12)
    y.loc[0, "ACL"] = 2

    with pytest.raises(ValueError, match="binary target frame"):
        select_multilabel_folds(y)
