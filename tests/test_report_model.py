from __future__ import annotations

import tomllib
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.metrics import macro_auc, per_label_auc
from knee_mri.report_model import (
    build_report_classifier,
    build_report_vectorizer,
    cross_validate_report_model,
    fit_report_model,
)


def _targets(row_count: int = 24) -> pd.DataFrame:
    return pd.DataFrame(
        {
            label: [(row_index + label_index) % 2 for row_index in range(row_count)]
            for label_index, label in enumerate(LABEL_COLUMNS)
        }
    )


def _reports(row_count: int = 24) -> pd.Series:
    return pd.Series(
        [
            "common report stable " + ("even finding" if row_index % 2 == 0 else "odd finding")
            for row_index in range(row_count)
        ],
        dtype=str,
    )


def _four_folds(row_count: int = 24) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    positions = np.arange(row_count)
    validation_folds = np.array_split(positions, 4)
    return tuple(
        (np.setdiff1d(positions, validation), validation) for validation in validation_folds
    )


def test_report_model_factories_are_frozen() -> None:
    vectorizer = build_report_vectorizer()
    classifier = build_report_classifier()
    estimator = classifier.estimator

    assert vectorizer.analyzer == "char_wb"
    assert vectorizer.ngram_range == (3, 5)
    assert vectorizer.min_df == 2
    assert vectorizer.max_features == 50_000
    assert vectorizer.sublinear_tf is True
    assert vectorizer.lowercase is True
    assert vectorizer.strip_accents is None
    assert classifier.n_jobs == 1
    assert estimator.penalty == "l2"
    assert estimator.solver == "liblinear"
    assert estimator.C == 1.0
    assert estimator.class_weight == "balanced"
    assert estimator.max_iter == 2_000
    assert estimator.random_state == 42


def test_project_bounds_sklearn_before_penalty_keyword_removal() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    requirement = next(
        dependency
        for dependency in project["dependencies"]
        if dependency.startswith("scikit-learn")
    )

    assert ">=1.4" in requirement
    assert "<1.10" in requirement


def test_cross_validate_report_model_returns_complete_oof_metrics() -> None:
    reports = _reports()
    y = _targets()
    folds = _four_folds()

    result = cross_validate_report_model(reports, y, folds)

    assert result.oof_probabilities.shape == (24, len(LABEL_COLUMNS))
    assert list(result.oof_probabilities.columns) == LABEL_COLUMNS
    assert result.oof_probabilities.index.equals(y.index)
    assert np.isfinite(result.oof_probabilities.to_numpy()).all()
    assert result.oof_probabilities.to_numpy().min() >= 0.0
    assert result.oof_probabilities.to_numpy().max() <= 1.0
    assert result.pooled_macro_auc == pytest.approx(macro_auc(y, result.oof_probabilities))
    assert result.pooled_per_label_auc == per_label_auc(y, result.oof_probabilities)
    assert len(result.fold_macro_auc) == len(folds)
    assert len(result.fold_per_label_auc) == len(folds)
    assert len(result.vocabulary_sizes) == len(folds)
    assert all(size > 0 for size in result.vocabulary_sizes)


def test_cross_validation_vectorizer_never_fits_validation_only_token(monkeypatch) -> None:
    reports = _reports()
    reports.iloc[:6] = reports.iloc[:6] + " validationexclusive"
    recorded_vocabularies = []

    class RecordingVectorizer(TfidfVectorizer):
        def fit_transform(self, raw_documents, y=None):
            matrix = super().fit_transform(raw_documents, y)
            recorded_vocabularies.append(set(self.vocabulary_))
            return matrix

    def recording_factory() -> TfidfVectorizer:
        return RecordingVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=2,
            max_features=50_000,
            sublinear_tf=True,
            lowercase=True,
            strip_accents=None,
        )

    monkeypatch.setattr("knee_mri.report_model.build_report_vectorizer", recording_factory)

    cross_validate_report_model(reports, _targets(), _four_folds())

    assert len(recorded_vocabularies) == 4
    assert "valid" not in recorded_vocabularies[0]
    assert all("valid" in vocabulary for vocabulary in recorded_vocabularies[1:])


def test_cross_validation_rejects_incomplete_or_duplicate_oof_coverage() -> None:
    reports = _reports()
    y = _targets()
    folds = _four_folds()
    invalid_folds = (folds[0], folds[0], folds[2], folds[3])

    with pytest.raises(ValueError, match="exactly once"):
        cross_validate_report_model(reports, y, invalid_folds)


def test_cross_validation_rejects_mismatched_report_count() -> None:
    with pytest.raises(ValueError, match="same row count"):
        cross_validate_report_model(_reports().iloc[:-1], _targets(), _four_folds())


def test_constant_half_predictions_have_macro_auc_one_half() -> None:
    y = _targets()
    predictions = pd.DataFrame(0.5, index=y.index, columns=LABEL_COLUMNS)

    assert macro_auc(y, predictions) == pytest.approx(0.5)


def test_cross_validation_turns_convergence_warning_into_error(monkeypatch) -> None:
    def fit_that_warns(self, features, targets):
        warnings.warn("did not converge", ConvergenceWarning, stacklevel=2)
        return self

    monkeypatch.setattr("knee_mri.report_model.OneVsRestClassifier.fit", fit_that_warns)

    with pytest.raises(ConvergenceWarning, match="did not converge"):
        cross_validate_report_model(_reports(), _targets(), _four_folds())


def test_cross_validation_propagates_empty_vocabulary_error() -> None:
    reports = pd.Series(["a", "b", "c", "d"], dtype=str)
    y = _targets(4)
    folds = (
        (np.array([2, 3]), np.array([0, 1])),
        (np.array([0, 1]), np.array([2, 3])),
    )

    with pytest.raises(ValueError, match=r"empty vocabulary|no terms remain"):
        cross_validate_report_model(reports, y, folds)


def test_fit_report_model_refits_and_predicts_all_labels() -> None:
    reports = _reports()
    y = _targets()

    vectorizer, classifier = fit_report_model(reports, y)
    probabilities = classifier.predict_proba(vectorizer.transform(reports))

    assert probabilities.shape == (len(reports), len(LABEL_COLUMNS))
    assert np.isfinite(probabilities).all()
    assert ((probabilities >= 0.0) & (probabilities <= 1.0)).all()
