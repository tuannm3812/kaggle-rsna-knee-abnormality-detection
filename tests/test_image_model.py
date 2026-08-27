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
