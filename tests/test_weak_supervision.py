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


def test_a_shuffled_label_frame_is_rejected_rather_than_paired_positionally():
    """Equal row counts do not establish correspondence. A frame reordered on
    the way in keeps its length and loses which study each row describes,
    which would silently train every head on the wrong targets.
    """
    weak = _weak(120, 60, 30)
    shuffled = weak.sample(frac=1.0, random_state=0)

    with pytest.raises(ValueError, match="same index"):
        fit_weak_label_heads(_features(120), shuffled, _features(5))


def test_features_of_the_wrong_registered_width_are_rejected():
    narrow = _features(120).iloc[:, :-1]

    with pytest.raises(ValueError, match="dimensional"):
        fit_weak_label_heads(narrow, _weak(120, 60, 30), narrow.iloc[:5])


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_non_finite_features_are_rejected(bad: float):
    train = _features(120)
    train.iloc[0, 0] = bad

    with pytest.raises(ValueError, match="non-empty and finite"):
        fit_weak_label_heads(train, _weak(120, 60, 30), _features(5))


def test_non_finite_evaluation_features_are_rejected():
    evaluation = _features(5)
    evaluation.iloc[0, 0] = np.inf

    with pytest.raises(ValueError, match="non-empty and finite"):
        fit_weak_label_heads(_features(120), _weak(120, 60, 30), evaluation)


def test_string_valued_weak_labels_are_rejected_rather_than_coerced():
    """`astype(float)` would accept "1", but the fitting loop reads the
    column without a dtype and compares `"1" == 1` as False -- so every label
    would count zero positives and abstain, producing a macro of exactly 0.5
    that looks like a clean null result. Round 109's API note, which
    reproduced as silent wrongness rather than a cosmetic gap.
    """
    weak = _weak(120, 60, 30).astype(object)
    for label in LABEL_COLUMNS:
        weak[label] = weak[label].map(lambda v: v if pd.isna(v) else str(int(v)))

    with pytest.raises(ValueError, match="must be numeric"):
        fit_weak_label_heads(_features(120), weak, _features(5))


def test_complex_weak_labels_are_rejected_rather_than_truncated():
    """`is_numeric_dtype` admits complex, and casting it to float drops the
    imaginary part behind a mere `ComplexWarning` -- so `1+1j` validated as a
    clean 1 while the fitting loop found `1+1j == 1` false, counted zero
    positives, and abstained all twelve labels into a macro of exactly 0.5.
    Round 111 reproduced it; this pins the rejection.
    """
    weak = _weak(120, 60, 30).astype(complex)

    with pytest.raises(ValueError, match="must be real"):
        fit_weak_label_heads(_features(120), weak, _features(5))


def test_the_fitted_labels_are_the_validated_labels():
    """Two silent-wrongness bugs came from validation coercing a frame while
    the fitting loop read the original. The validator returns one normalized
    representation and the loop must consume *that*, so an integer frame --
    valid, but a different dtype from what the loop once assumed -- must
    produce exactly the float frame's counts and predictions.
    """
    weak = _weak(120, 60, 30)
    integers = weak.fillna(0.0).astype(int)

    fit = fit_weak_label_heads(_features(120), integers, _features(5))
    reference = fit_weak_label_heads(_features(120), integers.astype(float), _features(5))

    assert fit.support == reference.support
    assert fit.positives == reference.positives
    assert fit.abstained == reference.abstained
    assert fit.probabilities.to_numpy() == pytest.approx(reference.probabilities.to_numpy())


def test_boolean_weak_labels_remain_acceptable():
    """A bool column is numeric, compares correctly against 1, and casts to
    int cleanly. The guard above must not reject it.
    """
    weak = _weak(120, 60, 30)
    booleans = weak.copy()
    for label in LABEL_COLUMNS:
        booleans[label] = weak[label].fillna(0.0).astype(bool)

    fit = fit_weak_label_heads(_features(120), booleans, _features(5))

    assert fit.support[LABEL_COLUMNS[0]] == 120
    assert fit.positives[LABEL_COLUMNS[0]] == 30


def test_a_weak_label_outside_one_zero_or_abstain_is_rejected():
    """0.5 is this module's abstain *probability*, not a label. Accepting it
    here would train a head on a target that means nothing.
    """
    weak = _weak(120, 60, 30)
    weak.iloc[0, 0] = 0.5

    with pytest.raises(ValueError, match="1, 0, or NaN"):
        fit_weak_label_heads(_features(120), weak, _features(5))


def test_a_non_positive_continuous_split_is_rejected():
    """Reported as the split it is, not as the derived feature width it
    would otherwise masquerade as.
    """
    with pytest.raises(ValueError, match="continuous_dimensions must be positive"):
        fit_weak_label_heads(
            _features(120), _weak(120, 60, 30), _features(5), continuous_dimensions=0
        )


# -- non-convergence is fatal, as it is for the image head --


def test_a_non_converging_head_raises_rather_than_scoring():
    """An unconverged head reports whatever the solver reached when it ran
    out of iterations. Round 107 found this path fitted directly, so a
    warning could have fed the decision statistic instead of stopping it.
    """
    from sklearn.exceptions import ConvergenceWarning

    import knee_mri.weak_supervision as weak_supervision

    original = weak_supervision._binary_head

    def _one_iteration_head():
        head = original()
        head.set_params(max_iter=1, solver="saga")
        return head

    weak_supervision._binary_head = _one_iteration_head
    try:
        with pytest.raises(ConvergenceWarning):
            fit_weak_label_heads(_features(120), _weak(120, 60, 30), _features(5))
    finally:
        weak_supervision._binary_head = original


# -- report resolution --


def test_weak_label_frame_maps_abstain_to_nan():
    frame = weak_label_frame(["", "acl tear"])

    assert list(frame.columns) == LABEL_COLUMNS
    assert frame.iloc[0].isna().all()


def test_weak_label_frame_tolerates_a_missing_report():
    frame = weak_label_frame([None, float("nan")])

    assert len(frame) == 2
    assert frame.isna().all().all()
