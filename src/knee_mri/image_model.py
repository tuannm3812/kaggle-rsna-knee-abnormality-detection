"""Frozen image-baseline classifier and leakage-safe OOF evaluation.

Implements section 9 of the Phase 3B specification
(`docs/superpowers/specs/2026-08-26-phase-3b-image-baseline-design.md`).

Reuses Phase 3A's estimator shape and fold protocol, with one deliberate
difference: `C = 0.1` rather than Phase 3A's `1.0`. That value was tuned for
a 50,000-feature sparse TF-IDF input; this is ~388 dense features on the same
58 studies, a far higher per-feature overfitting risk.

**`C` is frozen before evaluation, and nothing here may search over it.**
Choosing `C` by maximizing the pooled OOF macro AUC and then reporting that
maximum uses validation outcomes for selection and yields an optimistic
estimate. If the first honest run shows severe overfitting, the correct
response is pre-registered nested CV -- selecting inside each outer training
fold -- never post-hoc re-tuning against the same predictions.

**Only the 384 continuous embedding dimensions are standardized.** The four
binary flags pass through untouched: standardizing a near-constant column
divides by a near-zero standard deviation and manufactures a single
high-leverage outlier, which is the worse failure. See
`knee_mri.study_features` for why those flags are near-degenerate at this
sample size.

The scaler and classifier are strictly fold-local. The frozen encoder has no
fitted state, so global features may be extracted once outside the fold loop,
but nothing fitted may cross a fold boundary. Round 80 found the report
harness had no classifier-leakage test at all -- fitting on every row left
its suite green while inflating the pooled score -- so both fold-locality
assertions are pinned here from the start.
"""

from __future__ import annotations

import hashlib
import warnings
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.metrics import macro_auc, per_label_auc

# The shared OOF-coverage guard is imported rather than reimplemented. It
# contains a fix that was subtle enough to ship broken once (buffered
# `+=` hiding a row duplicated within one fold, round 80), and a second copy
# would be free to drift back.
from knee_mri.report_model import _validate_oof_coverage, _validate_probabilities
from knee_mri.study_features import EMBEDDING_DIM, STUDY_VECTOR_DIM

FoldIndices = tuple[np.ndarray, np.ndarray]

# Frozen by section 9.
IMAGE_CLASSIFIER_C = 0.1
CONTINUOUS_DIMENSIONS = EMBEDDING_DIM


@dataclass(frozen=True)
class ImageCrossValidationResult:
    """Aggregate and OOF products from one frozen image-baseline CV run.

    Attributes:
        oof_probabilities: One probability per study and canonical label.
        pooled_macro_auc: The primary metric, over every OOF prediction.
        pooled_per_label_auc: Pooled AUC per canonical label (diagnostic).
        fold_macro_auc: Per-fold macro AUC (diagnostic only -- small-sample
            fold scores are noisy and a value below 0.5 is not by itself
            evidence of a wiring error).
        fold_per_label_auc: Per-fold, per-label AUC (diagnostic).
    """

    oof_probabilities: pd.DataFrame
    pooled_macro_auc: float
    pooled_per_label_auc: dict[str, float]
    fold_macro_auc: tuple[float, ...]
    fold_per_label_auc: tuple[dict[str, float], ...]


class PartialStandardScaler:
    """Standardize the leading continuous columns; pass the rest through.

    Deliberately not `sklearn.preprocessing.StandardScaler` over the whole
    matrix, and not a `ColumnTransformer` (which may reorder columns): the
    contract is that the first `CONTINUOUS_DIMENSIONS` columns are scaled and
    the trailing flag columns are returned bit-for-bit unchanged.
    """

    def __init__(self, continuous_dimensions: int = CONTINUOUS_DIMENSIONS):
        self.continuous_dimensions = continuous_dimensions
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None

    def fit(self, matrix: np.ndarray) -> PartialStandardScaler:
        continuous = np.asarray(matrix, dtype=np.float64)[:, : self.continuous_dimensions]
        self.mean_ = continuous.mean(axis=0)
        scale = continuous.std(axis=0)
        # A zero-variance continuous dimension would divide by zero; leaving
        # it at scale 1 maps it to a constant 0 offset instead, which the
        # intercept absorbs.
        self.scale_ = np.where(scale > 0.0, scale, 1.0)
        return self

    def transform(self, matrix: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.scale_ is None:
            raise ValueError("scaler must be fitted before transform")
        values = np.array(matrix, dtype=np.float64, copy=True)
        values[:, : self.continuous_dimensions] = (
            values[:, : self.continuous_dimensions] - self.mean_
        ) / self.scale_
        return values


def build_image_classifier() -> OneVsRestClassifier:
    """Return the frozen one-vs-rest logistic classifier for the image head."""
    return OneVsRestClassifier(
        LogisticRegression(
            penalty="l2",
            solver="liblinear",
            C=IMAGE_CLASSIFIER_C,
            class_weight="balanced",
            max_iter=2_000,
            random_state=42,
        ),
        n_jobs=1,
    )


def fold_signature(
    study_ids: Sequence[str], folds: Sequence[FoldIndices]
) -> str:
    """A stable digest of the ordered study IDs and their fold membership.

    `select_multilabel_folds` is row-order-sensitive, so identical labels in a
    different row order produce different folds. Persisting and comparing this
    digest is what lets the image baseline claim its macro AUC is comparable
    to the report baseline's -- rather than assuming the same algorithm and
    seed imply the same membership, which they do not.
    """
    digest = hashlib.sha256()
    for study_id in study_ids:
        digest.update(str(study_id).encode("utf-8"))
        digest.update(b"\x00")
    for training_indices, validation_indices in folds:
        digest.update(b"|")
        digest.update(np.asarray(training_indices, dtype=np.int64).tobytes())
        digest.update(b"/")
        digest.update(np.asarray(validation_indices, dtype=np.int64).tobytes())
    return digest.hexdigest()


def _fit_classifier(
    classifier: OneVsRestClassifier, matrix: np.ndarray, targets: pd.DataFrame
) -> None:
    """Fit, treating non-convergence as fatal.

    Mirrors Phase 3A. A `ConvergenceWarning` means the reported coefficients
    are whatever the solver happened to reach when it ran out of iterations,
    so a score computed from them is not the score of the frozen contract --
    exactly the kind of quietly-wrong result this pipeline cannot detect
    downstream. The `penalty` deprecation is separately silenced because it
    is a known-benign notice about a keyword the frozen contract pins.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="'penalty' was deprecated in version 1.8.*",
            category=FutureWarning,
        )
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(matrix, targets)


def _validate_inputs(features: pd.DataFrame, y: pd.DataFrame) -> None:
    if list(y.columns) != LABEL_COLUMNS:
        raise ValueError("y columns must match LABEL_COLUMNS in canonical order")
    if len(features) != len(y):
        raise ValueError("features and y must have the same number of rows")
    if features.shape[1] != STUDY_VECTOR_DIM:
        raise ValueError(f"features must be {STUDY_VECTOR_DIM}-dimensional")
    if features.empty or not np.isfinite(features.to_numpy()).all():
        raise ValueError("features must be non-empty and finite")


def cross_validate_image_model(
    features: pd.DataFrame,
    y: pd.DataFrame,
    folds: Sequence[FoldIndices],
) -> ImageCrossValidationResult:
    """Fit fold-local scalers and classifiers, returning OOF diagnostics.

    Args:
        features: One `STUDY_VECTOR_DIM`-wide row per labelled study.
        y: Binary targets in canonical label-column order, same row order.
        folds: Preselected train/validation positional index pairs.

    Returns:
        Pooled OOF macro AUC as the primary metric, with per-label and
        per-fold scores as diagnostics.

    Raises:
        ValueError: If inputs are malformed or fold coverage is not exactly
            one validation appearance per row.
    """
    _validate_inputs(features, y)
    _validate_oof_coverage(tuple(folds), len(y))

    matrix = features.to_numpy(dtype=np.float64)
    oof_probabilities = pd.DataFrame(np.nan, index=y.index, columns=LABEL_COLUMNS)
    fold_macro: list[float] = []
    fold_per_label: list[dict[str, float]] = []

    for training_indices, validation_indices in folds:
        # Both the scaler and the classifier are fitted on training rows only.
        scaler = PartialStandardScaler().fit(matrix[training_indices])
        classifier = build_image_classifier()
        _fit_classifier(
            classifier, scaler.transform(matrix[training_indices]), y.iloc[training_indices]
        )

        probabilities = classifier.predict_proba(scaler.transform(matrix[validation_indices]))
        _validate_probabilities(probabilities, "out-of-fold")
        oof_probabilities.iloc[validation_indices, :] = probabilities

        fold_truth = y.iloc[validation_indices]
        fold_predictions = pd.DataFrame(
            probabilities, index=fold_truth.index, columns=LABEL_COLUMNS
        )
        fold_macro.append(macro_auc(fold_truth, fold_predictions))
        fold_per_label.append(per_label_auc(fold_truth, fold_predictions))

    return ImageCrossValidationResult(
        oof_probabilities=oof_probabilities,
        pooled_macro_auc=macro_auc(y, oof_probabilities),
        pooled_per_label_auc=per_label_auc(y, oof_probabilities),
        fold_macro_auc=tuple(fold_macro),
        fold_per_label_auc=tuple(fold_per_label),
    )


def fit_image_model(
    features: pd.DataFrame, y: pd.DataFrame
) -> tuple[PartialStandardScaler, OneVsRestClassifier]:
    """Refit scaler and classifier on every labelled study, for inference.

    Runs after evaluation, never before: the scaler fitted here has seen every
    row and must not be used to produce any score that is reported.
    """
    _validate_inputs(features, y)
    matrix = features.to_numpy(dtype=np.float64)
    scaler = PartialStandardScaler().fit(matrix)
    classifier = build_image_classifier()
    _fit_classifier(classifier, scaler.transform(matrix), y)
    return scaler, classifier
