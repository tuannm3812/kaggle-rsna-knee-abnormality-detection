from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from knee_mri.image_model import CONTINUOUS_DIMENSIONS
from knee_mri.labels import LABEL_COLUMNS
from knee_mri.study_features import STUDY_VECTOR_DIM
from knee_mri.weak_supervision import (
    ABSTAIN_PROBABILITY,
    WEAK_MIN_CLASS_COUNT,
    WEAK_MIN_SUPPORT,
    fit_weak_label_heads,
    weak_label_frame,
)

FLAGS = STUDY_VECTOR_DIM - CONTINUOUS_DIMENSIONS


def _features(rows: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    embedding = rng.normal(size=(rows, CONTINUOUS_DIMENSIONS))
    return pd.DataFrame(np.hstack([embedding, np.ones((rows, FLAGS))]))


def _weak(rows: int, resolved: int, positives: int) -> pd.DataFrame:
    frame = pd.DataFrame(np.nan, index=range(rows), columns=LABEL_COLUMNS)
    for label in LABEL_COLUMNS:
        values = [1.0] * positives + [0.0] * (resolved - positives)
        frame.loc[: resolved - 1, label] = values
    return frame


# -- abstention is excluded, never coerced --


def test_abstained_rows_are_excluded_from_a_label_fit():
    """Coercing no-mention to 0 would fabricate negatives at scale. Support
    must count only the rows where the report actually spoke to the label.
    """
    rows, resolved = 120, 60
    fit = fit_weak_label_heads(_features(rows), _weak(rows, resolved, 30), _features(9, seed=1))

    for label in LABEL_COLUMNS:
        assert fit.support[label] == resolved
        assert fit.positives[label] == 30


def test_each_label_may_train_on_a_different_row_set():
    rows = 140
    weak = pd.DataFrame(np.nan, index=range(rows), columns=LABEL_COLUMNS)
    weak.loc[:79, LABEL_COLUMNS[0]] = [1.0] * 40 + [0.0] * 40
    weak.loc[:39, LABEL_COLUMNS[1]] = [1.0] * 20 + [0.0] * 20

    fit = fit_weak_label_heads(_features(rows), weak, _features(6, seed=2))

    assert fit.support[LABEL_COLUMNS[0]] == 80
    assert fit.support[LABEL_COLUMNS[1]] == 40
    assert fit.support[LABEL_COLUMNS[2]] == 0


# -- a label that cannot be fitted abstains at chance --


def test_a_label_below_the_support_floor_abstains_at_chance():
    rows = 60
    weak = pd.DataFrame(np.nan, index=range(rows), columns=LABEL_COLUMNS)
    thin = WEAK_MIN_SUPPORT - 1
    weak.loc[: thin - 1, LABEL_COLUMNS[0]] = [1.0] * (thin // 2) + [0.0] * (thin - thin // 2)

    fit = fit_weak_label_heads(_features(rows), weak, _features(7, seed=3))

    assert LABEL_COLUMNS[0] in fit.abstained
    assert (fit.probabilities[LABEL_COLUMNS[0]] == ABSTAIN_PROBABILITY).all()


def test_a_single_class_label_abstains_rather_than_fitting():
    rows = 100
    weak = pd.DataFrame(np.nan, index=range(rows), columns=LABEL_COLUMNS)
    weak.loc[:59, LABEL_COLUMNS[0]] = 1.0

    fit = fit_weak_label_heads(_features(rows), weak, _features(5, seed=4))

    assert LABEL_COLUMNS[0] in fit.abstained


def test_a_label_with_too_few_of_one_class_abstains():
    rows = 100
    weak = pd.DataFrame(np.nan, index=range(rows), columns=LABEL_COLUMNS)
    scarce = WEAK_MIN_CLASS_COUNT - 1
    weak.loc[:59, LABEL_COLUMNS[0]] = [1.0] * scarce + [0.0] * (60 - scarce)

    fit = fit_weak_label_heads(_features(rows), weak, _features(5, seed=5))

    assert LABEL_COLUMNS[0] in fit.abstained


def test_an_abstaining_label_scores_exactly_chance():
    """A constant column must not be able to help or hurt the macro."""
    from knee_mri.metrics import macro_auc

    rows = 40
    truth = pd.DataFrame(
        {label: [index % 2 for index in range(rows)] for label in LABEL_COLUMNS}
    )
    constant = pd.DataFrame(ABSTAIN_PROBABILITY, index=truth.index, columns=LABEL_COLUMNS)

    assert macro_auc(truth, constant) == 0.5


# -- the evaluation set is never fitted on --


def test_predictions_are_produced_for_every_evaluation_row():
    fit = fit_weak_label_heads(_features(120), _weak(120, 60, 30), _features(11, seed=6))

    assert list(fit.probabilities.columns) == LABEL_COLUMNS
    assert len(fit.probabilities) == 11
    assert fit.probabilities.to_numpy().min() >= 0.0
    assert fit.probabilities.to_numpy().max() <= 1.0


def test_evaluation_rows_do_not_influence_the_fitted_scaler():
    """The scaler is fitted on training rows only. Shifting the evaluation
    set must not change what the training rows were standardized by, so the
    predictions for a fixed evaluation row are unchanged by its neighbours.
    """
    train, weak = _features(120), _weak(120, 60, 30)
    evaluation = _features(8, seed=7)

    alone = fit_weak_label_heads(train, weak, evaluation.iloc[:1])
    with_others = fit_weak_label_heads(train, weak, evaluation)

    assert alone.probabilities.iloc[0].to_numpy() == pytest.approx(
        with_others.probabilities.iloc[0].to_numpy()
    )


# -- input validation --


def test_mismatched_row_counts_are_rejected():
    with pytest.raises(ValueError, match="same row count"):
        fit_weak_label_heads(_features(10), _weak(9, 8, 4), _features(3))


def test_mismatched_feature_widths_are_rejected():
    with pytest.raises(ValueError, match="same width"):
        fit_weak_label_heads(_features(120), _weak(120, 60, 30), _features(4).iloc[:, :10])


# -- report resolution --


def test_weak_label_frame_maps_abstain_to_nan():
    frame = weak_label_frame(["", "acl tear"])

    assert list(frame.columns) == LABEL_COLUMNS
    assert frame.iloc[0].isna().all()


def test_weak_label_frame_tolerates_a_missing_report():
    frame = weak_label_frame([None, float("nan")])

    assert len(frame) == 2
    assert frame.isna().all().all()
