from __future__ import annotations

import inspect
import warnings

import numpy as np
import pandas as pd
import pytest

from knee_mri import image_model
from knee_mri.image_model import (
    CONTINUOUS_DIMENSIONS,
    IMAGE_CLASSIFIER_C,
    PartialStandardScaler,
    build_image_classifier,
    cross_validate_image_model,
    fit_image_model,
    fold_signature,
)
from knee_mri.labels import LABEL_COLUMNS
from knee_mri.study_features import STUDY_VECTOR_DIM

ROW_COUNT = 24
SEED_FOR_TESTS = 11


def _features(row_count: int = ROW_COUNT) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    embedding = rng.normal(size=(row_count, CONTINUOUS_DIMENSIONS))
    flags = np.ones((row_count, STUDY_VECTOR_DIM - CONTINUOUS_DIMENSIONS))
    return pd.DataFrame(np.hstack([embedding, flags]))


def _targets(row_count: int = ROW_COUNT) -> pd.DataFrame:
    return pd.DataFrame(
        {label: [(index + position) % 2 for index in range(row_count)]
         for position, label in enumerate(LABEL_COLUMNS)}
    )


def _folds(row_count: int = ROW_COUNT):
    positions = np.arange(row_count)
    validation_folds = np.array_split(positions, 4)
    return tuple(
        (np.setdiff1d(positions, validation), validation) for validation in validation_folds
    )


# -- frozen configuration --


def test_regularization_is_frozen_at_the_reviewed_value():
    assert IMAGE_CLASSIFIER_C == 0.1

    estimator = build_image_classifier().estimator

    assert estimator.C == IMAGE_CLASSIFIER_C
    assert estimator.penalty == "l2"
    assert estimator.solver == "liblinear"
    assert estimator.class_weight == "balanced"
    assert estimator.max_iter == 2_000
    assert estimator.random_state == 42


def test_no_code_path_selects_c_from_scores():
    """Section 9 forbids choosing C on the same OOF predictions it reports.

    The response to overfitting is pre-registered nested CV, never post-hoc
    re-tuning, so nothing here may search over C.
    """
    source = inspect.getsource(image_model)

    for forbidden in ("GridSearchCV", "RandomizedSearchCV", "param_grid", "best_score_"):
        assert forbidden not in source


# -- scaling: continuous dimensions only, fold-local --


def test_scaler_touches_only_the_continuous_dimensions():
    features = _features()
    scaler = PartialStandardScaler().fit(features.to_numpy())

    transformed = scaler.transform(features.to_numpy())

    scaled = transformed[:, :CONTINUOUS_DIMENSIONS]
    assert np.allclose(scaled.mean(axis=0), 0.0, atol=1e-9)
    assert np.allclose(scaled.std(axis=0), 1.0, atol=1e-6)
    # The four binary flags pass through untouched.
    assert np.array_equal(
        transformed[:, CONTINUOUS_DIMENSIONS:],
        features.to_numpy()[:, CONTINUOUS_DIMENSIONS:],
    )


def test_a_constant_flag_column_is_not_amplified():
    """Standardizing a near-constant column divides by a near-zero standard
    deviation and manufactures a high-leverage outlier -- which is precisely
    why section 8 leaves the flags unscaled.
    """
    features = _features()
    transformed = PartialStandardScaler().fit(features.to_numpy()).transform(features.to_numpy())

    assert np.all(np.isfinite(transformed))
    assert transformed[:, CONTINUOUS_DIMENSIONS:].max() == 1.0


def test_the_scaler_is_fitted_inside_each_training_fold(monkeypatch):
    """Fitting the scaler on all rows leaks validation statistics into the
    model that scores them.
    """
    recorded_row_counts: list[int] = []
    real_fit = PartialStandardScaler.fit

    def recording_fit(self, matrix):
        recorded_row_counts.append(matrix.shape[0])
        return real_fit(self, matrix)

    monkeypatch.setattr(PartialStandardScaler, "fit", recording_fit)

    folds = _folds()
    cross_validate_image_model(_features(), _targets(), folds)

    expected = [len(training_indices) for training_indices, _ in folds]
    assert recorded_row_counts == expected
    assert all(count < ROW_COUNT for count in recorded_row_counts)


def test_the_classifier_is_fitted_inside_each_training_fold(monkeypatch):
    """Round 80 found the report harness had no such test at all: fitting on
    every row left the suite green while inflating pooled OOF AUC.
    """
    recorded_row_counts: list[int] = []
    real_fit = image_model._fit_classifier

    def recording_fit(classifier, matrix, targets):
        recorded_row_counts.append(matrix.shape[0])
        return real_fit(classifier, matrix, targets)

    monkeypatch.setattr(image_model, "_fit_classifier", recording_fit)

    folds = _folds()
    cross_validate_image_model(_features(), _targets(), folds)

    assert recorded_row_counts == [len(training) for training, _ in folds]
    assert all(count < ROW_COUNT for count in recorded_row_counts)


# -- fold identity --


def test_fold_signature_is_stable_for_identical_inputs():
    study_ids = [f"study-{index}" for index in range(ROW_COUNT)]
    folds = _folds()

    assert fold_signature(study_ids, folds) == fold_signature(study_ids, folds)


def test_fold_signature_changes_when_study_order_changes():
    """`select_multilabel_folds` is row-order-sensitive, so identical labels
    in a different row order give different fold membership. The signature
    must detect that rather than assume it away.
    """
    study_ids = [f"study-{index}" for index in range(ROW_COUNT)]
    reordered = list(reversed(study_ids))
    folds = _folds()

    assert fold_signature(study_ids, folds) != fold_signature(reordered, folds)


def test_fold_signature_changes_when_membership_changes():
    study_ids = [f"study-{index}" for index in range(ROW_COUNT)]
    folds = _folds()
    swapped = ((folds[0][0], folds[1][1]), *folds[1:])

    assert fold_signature(study_ids, folds) != fold_signature(study_ids, swapped)


# -- evaluation --


def test_cross_validation_returns_pooled_and_diagnostic_scores():
    result = cross_validate_image_model(_features(), _targets(), _folds())

    assert 0.0 <= result.pooled_macro_auc <= 1.0
    assert set(result.pooled_per_label_auc) == set(LABEL_COLUMNS)
    assert len(result.fold_macro_auc) == 4
    assert result.oof_probabilities.shape == (ROW_COUNT, len(LABEL_COLUMNS))
    assert result.oof_probabilities.notna().all().all()


def test_a_constant_prediction_frame_scores_exactly_one_half():
    """Phase 3A's wiring check, carried forward: this catches metric
    miswiring in a way a real score cannot.
    """
    from knee_mri.metrics import macro_auc

    y = _targets()
    constant = pd.DataFrame(0.5, index=y.index, columns=LABEL_COLUMNS)

    assert macro_auc(y, constant) == 0.5


def test_incomplete_fold_coverage_is_rejected():
    positions = np.arange(ROW_COUNT)
    incomplete = ((positions[6:], positions[:6]),)

    with pytest.raises(ValueError, match="covered exactly once"):
        cross_validate_image_model(_features(), _targets(), incomplete)


def test_feature_and_target_row_mismatch_is_rejected():
    with pytest.raises(ValueError, match="same number of rows"):
        cross_validate_image_model(_features(ROW_COUNT - 1), _targets(), _folds())


def test_features_must_have_the_full_study_vector_width():
    with pytest.raises(ValueError, match="dimensional"):
        cross_validate_image_model(
            _features().iloc[:, :-1], _targets(), _folds()
        )


# -- refit --


def test_refit_uses_every_labelled_row():
    features, y = _features(), _targets()

    scaler, classifier = fit_image_model(features, y)

    transformed = scaler.transform(features.to_numpy())
    probabilities = classifier.predict_proba(transformed)

    assert probabilities.shape == (ROW_COUNT, len(LABEL_COLUMNS))
    assert np.isfinite(probabilities).all()
    assert ((probabilities >= 0.0) & (probabilities <= 1.0)).all()


def test_non_convergence_is_fatal():
    """A ConvergenceWarning means the coefficients are wherever the solver
    stopped, so any score from them is not the frozen contract's score.
    """
    from sklearn.exceptions import ConvergenceWarning

    class NonConvergingClassifier:
        def fit(self, matrix, targets):
            warnings.warn("did not converge", ConvergenceWarning, stacklevel=2)

    with pytest.raises(ConvergenceWarning):
        image_model._fit_classifier(NonConvergingClassifier(), np.zeros((2, 2)), None)


def test_the_penalty_deprecation_notice_is_silenced_not_fatal():
    features, y = _features(), _targets()

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        fit_image_model(features, y)


# -- uncertainty diagnostics --


def test_bootstrap_interval_brackets_the_point_estimate():
    from knee_mri.image_model import bootstrap_macro_auc

    y = _targets()
    rng = np.random.default_rng(3)
    probabilities = pd.DataFrame(
        rng.random((ROW_COUNT, len(LABEL_COLUMNS))), index=y.index, columns=LABEL_COLUMNS
    )

    result = bootstrap_macro_auc(y, probabilities, iterations=200, seed=SEED_FOR_TESTS)

    assert result.lower <= result.point <= result.upper
    assert 0.0 <= result.lower and result.upper <= 1.0
    assert result.iterations == 200
    assert 0.0 <= result.complete_label_fraction <= 1.0


def test_bootstrap_is_deterministic_for_a_given_seed():
    from knee_mri.image_model import bootstrap_macro_auc

    y = _targets()
    rng = np.random.default_rng(4)
    probabilities = pd.DataFrame(
        rng.random((ROW_COUNT, len(LABEL_COLUMNS))), index=y.index, columns=LABEL_COLUMNS
    )

    first = bootstrap_macro_auc(y, probabilities, iterations=100, seed=7)
    second = bootstrap_macro_auc(y, probabilities, iterations=100, seed=7)

    assert first == second


def test_bootstrap_reports_when_labels_became_degenerate():
    """Resampling 58 studies with replacement can lose every positive for a
    rare label. Those labels are excluded from that resample's macro, and the
    fraction of fully-estimable resamples is reported rather than hidden.
    """
    from knee_mri.image_model import bootstrap_macro_auc

    y = _targets()
    # One label with a single positive is very likely to vanish in a resample.
    y = y.copy()
    y[LABEL_COLUMNS[0]] = [1] + [0] * (ROW_COUNT - 1)
    rng = np.random.default_rng(5)
    probabilities = pd.DataFrame(
        rng.random((ROW_COUNT, len(LABEL_COLUMNS))), index=y.index, columns=LABEL_COLUMNS
    )

    result = bootstrap_macro_auc(y, probabilities, iterations=200, seed=SEED_FOR_TESTS)

    assert result.complete_label_fraction < 1.0


def test_repeated_fold_scores_include_the_frozen_seed_result():
    from knee_mri.image_model import repeated_fold_macro_auc

    features, y = _features(), _targets()

    scores = repeated_fold_macro_auc(features, y, seeds=(42, 43))

    assert len(scores) == 2
    assert all(0.0 <= score <= 1.0 for score in scores)


def test_repeated_fold_scores_are_reproducible():
    from knee_mri.image_model import repeated_fold_macro_auc

    features, y = _features(), _targets()

    assert repeated_fold_macro_auc(features, y, seeds=(42,)) == repeated_fold_macro_auc(
        features, y, seeds=(42,)
    )


def test_paired_delta_is_tighter_than_comparing_marginal_intervals():
    """Two variants scored on the same studies share per-study difficulty.

    Comparing their marginal intervals discards that pairing and is far too
    blunt to resolve a real difference at this sample size; bootstrapping the
    difference on the same resampled studies keeps it.
    """
    from knee_mri.image_model import bootstrap_macro_auc, paired_bootstrap_delta

    y = _targets()
    rng = np.random.default_rng(9)
    base = rng.random((ROW_COUNT, len(LABEL_COLUMNS)))
    a = pd.DataFrame(base, index=y.index, columns=LABEL_COLUMNS)
    # b differs only slightly, as competing variants of one pipeline would.
    b = pd.DataFrame(
        np.clip(base + rng.normal(0, 0.02, base.shape), 0, 1),
        index=y.index,
        columns=LABEL_COLUMNS,
    )

    delta = paired_bootstrap_delta(y, a, b, iterations=400, seed=1)
    marginal_a = bootstrap_macro_auc(y, a, iterations=400, seed=1)

    paired_width = delta.upper - delta.lower
    marginal_width = marginal_a.upper - marginal_a.lower

    assert paired_width < marginal_width


def test_paired_delta_reports_direction_and_significance():
    from knee_mri.image_model import paired_bootstrap_delta

    y = _targets()
    rng = np.random.default_rng(10)
    weak = pd.DataFrame(
        rng.random((ROW_COUNT, len(LABEL_COLUMNS))), index=y.index, columns=LABEL_COLUMNS
    )
    # Strong predictions: the truth itself, slightly noised.
    strong = pd.DataFrame(
        np.clip(y.to_numpy() * 0.8 + rng.normal(0, 0.05, weak.shape), 0, 1),
        index=y.index,
        columns=LABEL_COLUMNS,
    )

    delta = paired_bootstrap_delta(y, strong, weak, iterations=400, seed=2)

    assert delta.delta > 0
    assert delta.lower > 0
    assert delta.excludes_zero is True


def test_paired_delta_on_identical_predictions_is_exactly_zero():
    from knee_mri.image_model import paired_bootstrap_delta

    y = _targets()
    rng = np.random.default_rng(11)
    probabilities = pd.DataFrame(
        rng.random((ROW_COUNT, len(LABEL_COLUMNS))), index=y.index, columns=LABEL_COLUMNS
    )

    delta = paired_bootstrap_delta(y, probabilities, probabilities, iterations=100, seed=3)

    assert delta.delta == 0.0
    assert delta.excludes_zero is False


# -- the harness supports a wider representation without a hand-rolled loop --


def test_the_default_continuous_width_is_unchanged():
    features, y, folds = _features(), _targets(), _folds()

    default = cross_validate_image_model(features, y, folds)
    explicit = cross_validate_image_model(
        features, y, folds, continuous_dimensions=CONTINUOUS_DIMENSIONS
    )

    assert default.pooled_macro_auc == explicit.pooled_macro_auc


def test_a_wider_frame_is_rejected_at_the_default_width():
    """The round-97 failure mode: widening the features while leaving the
    scaler width alone standardizes only part of the block and silently
    redefines the variant. It must fail loudly instead.
    """
    features, y, folds = _features(), _targets(), _folds()
    wider = pd.concat([features, features.iloc[:, :10]], axis=1)
    wider.columns = range(wider.shape[1])

    with pytest.raises(ValueError, match="dimensional"):
        cross_validate_image_model(wider, y, folds)


def test_a_wider_frame_scales_its_whole_embedding_block():
    features, y, folds = _features(), _targets(), _folds()
    embedding = features.iloc[:, :CONTINUOUS_DIMENSIONS]
    flags = features.iloc[:, CONTINUOUS_DIMENSIONS:]
    wider = pd.concat([embedding, embedding * 1000.0, flags], axis=1)
    wider.columns = range(wider.shape[1])

    result = cross_validate_image_model(
        wider, y, folds, continuous_dimensions=2 * CONTINUOUS_DIMENSIONS
    )

    # A duplicated-then-rescaled block carries no new information, so scaling
    # the whole block must leave the score where the narrow frame put it. If
    # only the first half were scaled, the unscaled half would dominate the
    # L2 penalty and move it.
    narrow = cross_validate_image_model(features, y, folds)
    assert result.pooled_macro_auc == pytest.approx(narrow.pooled_macro_auc, abs=1e-9)
