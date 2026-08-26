"""Frozen report-only baseline and leakage-safe OOF evaluation."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.metrics import macro_auc, per_label_auc

FoldIndices = tuple[np.ndarray, np.ndarray]


@dataclass(frozen=True)
class ReportCrossValidationResult:
    """Safe aggregate and OOF products from one frozen CV run.

    Attributes:
        oof_probabilities: One probability per study and canonical label.
        pooled_macro_auc: Primary macro AUC over every OOF prediction.
        pooled_per_label_auc: Pooled AUC for each canonical label.
        fold_macro_auc: Diagnostic macro AUC for each fold.
        fold_per_label_auc: Diagnostic per-label AUC mappings by fold.
        vocabulary_sizes: Learned fold-local TF-IDF vocabulary sizes.
    """

    oof_probabilities: pd.DataFrame
    pooled_macro_auc: float
    pooled_per_label_auc: dict[str, float]
    fold_macro_auc: tuple[float, ...]
    fold_per_label_auc: tuple[dict[str, float], ...]
    vocabulary_sizes: tuple[int, ...]


def build_report_vectorizer() -> TfidfVectorizer:
    """Return the frozen character n-gram TF-IDF vectorizer."""
    return TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=2,
        max_features=50_000,
        sublinear_tf=True,
        lowercase=True,
        strip_accents=None,
    )


def build_report_classifier() -> OneVsRestClassifier:
    """Return the frozen explicit one-vs-rest logistic classifier."""
    return OneVsRestClassifier(
        LogisticRegression(
            penalty="l2",
            solver="liblinear",
            C=1.0,
            class_weight="balanced",
            max_iter=2_000,
            random_state=42,
        ),
        n_jobs=1,
    )


def cross_validate_report_model(
    reports: pd.Series,
    y: pd.DataFrame,
    folds: tuple[FoldIndices, ...],
) -> ReportCrossValidationResult:
    """Fit fold-local report models and return complete OOF diagnostics.

    Args:
        reports: Validated labeled-study report strings.
        y: Binary targets in canonical label-column order.
        folds: Preselected train/validation positional index pairs.

    Returns:
        Complete OOF probabilities and aggregate-only score diagnostics.

    Raises:
        ValueError: If inputs or fold coverage are malformed, fitted
            probabilities are invalid, or an estimator cannot fit.
        ConvergenceWarning: If any one-vs-rest estimator does not converge.
    """
    _validate_modeling_data(reports, y)
    _validate_oof_coverage(folds, len(y))

    oof_probabilities = pd.DataFrame(np.nan, index=y.index, columns=LABEL_COLUMNS)
    fold_macro_scores: list[float] = []
    fold_label_scores: list[dict[str, float]] = []
    vocabulary_sizes: list[int] = []

    for training_indices, validation_indices in folds:
        vectorizer = build_report_vectorizer()
        classifier = build_report_classifier()
        training_features = vectorizer.fit_transform(reports.iloc[training_indices])
        validation_features = vectorizer.transform(reports.iloc[validation_indices])

        _fit_classifier(classifier, training_features, y.iloc[training_indices])

        probabilities = classifier.predict_proba(validation_features)
        oof_probabilities.iloc[validation_indices, :] = probabilities
        fold_truth = y.iloc[validation_indices]
        fold_predictions = pd.DataFrame(
            probabilities,
            index=fold_truth.index,
            columns=LABEL_COLUMNS,
        )
        fold_label_scores.append(per_label_auc(fold_truth, fold_predictions))
        fold_macro_scores.append(macro_auc(fold_truth, fold_predictions))
        vocabulary_sizes.append(len(vectorizer.vocabulary_))

    _validate_probabilities(oof_probabilities.to_numpy(), "OOF")
    return ReportCrossValidationResult(
        oof_probabilities=oof_probabilities,
        pooled_macro_auc=macro_auc(y, oof_probabilities),
        pooled_per_label_auc=per_label_auc(y, oof_probabilities),
        fold_macro_auc=tuple(fold_macro_scores),
        fold_per_label_auc=tuple(fold_label_scores),
        vocabulary_sizes=tuple(vocabulary_sizes),
    )


def fit_report_model(
    reports: pd.Series,
    y: pd.DataFrame,
) -> tuple[TfidfVectorizer, OneVsRestClassifier]:
    """Fit the frozen report model once on all validated labeled studies.

    Args:
        reports: Validated labeled-study report strings.
        y: Binary targets in canonical label-column order.

    Returns:
        The fitted vectorizer and explicit one-vs-rest classifier.

    Raises:
        ValueError: If inputs are malformed or an estimator cannot fit.
        ConvergenceWarning: If any one-vs-rest estimator does not converge.
    """
    _validate_modeling_data(reports, y)
    vectorizer = build_report_vectorizer()
    classifier = build_report_classifier()
    features = vectorizer.fit_transform(reports)
    _fit_classifier(classifier, features, y)
    return vectorizer, classifier


def _validate_modeling_data(reports: pd.Series, y: pd.DataFrame) -> None:
    if len(reports) != len(y):
        raise ValueError("reports and y must have the same row count")
    if y.empty or list(y.columns) != LABEL_COLUMNS:
        raise ValueError("y must be non-empty with canonical LABEL_COLUMNS order")
    if not reports.apply(lambda value: isinstance(value, str)).all():
        raise ValueError("reports must contain only strings")


def _validate_oof_coverage(folds: tuple[FoldIndices, ...], row_count: int) -> None:
    coverage = np.zeros(row_count, dtype=int)
    for _, validation_indices in folds:
        # `coverage[validation_indices] += 1` is buffered: an index repeated
        # within one fold's array increments only once, so a row duplicated
        # inside a single fold would satisfy the "exactly once" check below
        # while actually being scored twice. `np.add.at` is unbuffered.
        np.add.at(coverage, validation_indices, 1)
    if not np.equal(coverage, 1).all():
        raise ValueError("every OOF row must be covered exactly once")


def _validate_probabilities(probabilities: np.ndarray, label: str) -> None:
    if not np.isfinite(probabilities).all():
        raise ValueError(f"{label} probabilities must be finite")
    if ((probabilities < 0.0) | (probabilities > 1.0)).any():
        raise ValueError(f"{label} probabilities must be within [0, 1]")


def _fit_classifier(
    classifier: OneVsRestClassifier,
    features,
    y: pd.DataFrame,
) -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="'penalty' was deprecated in version 1.8.*",
            category=FutureWarning,
        )
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(features, y)
