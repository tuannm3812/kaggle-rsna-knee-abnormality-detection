"""Training a per-label image head on report-derived weak labels.

Phase 2 evaluated `labels.extract_weak_labels` for *precision* and returned
No-go: 0 of 12 labels cleared a Wilson lower-bound gate, because per-label
support among the 58 human-labelled studies is only about 10 to 20. That
verdict answered whether the labels can be trusted individually. It did not
answer whether **training** on them improves the score, which is a separate
question with a cleaner test: fit on report-only studies and evaluate on the
58 human-labelled ones. Noisy training labels cannot corrupt a human-labelled
evaluation set.

**Abstentions are excluded per label, never coerced to zero.** The extractor
returns `None` when a report does not speak to a finding, and treating that as
a confident negative would fabricate negatives at scale -- precisely the
failure the assertion-aware extractor exists to avoid. Each label therefore
trains on its own subset of rows, so the heads cannot share a single fitted
estimator and are fitted individually here.

Every counter this module reports is aggregate: row counts and class counts,
never a study identifier.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from knee_mri.image_model import (
    CONTINUOUS_DIMENSIONS,
    FLAG_DIMENSIONS,
    IMAGE_CLASSIFIER_C,
    PartialStandardScaler,
)
from knee_mri.labels import LABEL_COLUMNS

# A label needs enough resolved rows, and enough of each class, before a
# fitted head means anything. Below either floor the label abstains at 0.5
# rather than contributing a head fitted on almost nothing -- which would add
# noise to the macro average while looking like a measurement.
WEAK_MIN_SUPPORT = 20
WEAK_MIN_CLASS_COUNT = 5

# Chance. A label that cannot be fitted contributes no ranking information
# rather than a spurious one; AUC of a constant column is exactly 0.5.
ABSTAIN_PROBABILITY = 0.5


@dataclass(frozen=True)
class WeakLabelFit:
    """Predictions from per-label heads, and what each head was fitted on.

    Attributes:
        probabilities: One row per evaluation study, columns in
            `LABEL_COLUMNS` order. Abstained labels are constant 0.5.
        support: Resolved (non-abstaining) training rows per label.
        positives: Positive training rows per label.
        abstained: Labels that could not be fitted, in canonical order.
    """

    probabilities: pd.DataFrame
    support: dict[str, int]
    positives: dict[str, int]
    abstained: tuple[str, ...]


def _binary_head() -> LogisticRegression:
    """The same estimator the image head uses, as a single binary model.

    Deliberately mirrors `image_model.build_image_classifier`'s inner
    estimator rather than reusing the one-vs-rest wrapper, which requires
    every label to share one row set -- the thing weak labels cannot do.
    """
    return LogisticRegression(
        penalty="l2",
        solver="liblinear",
        C=IMAGE_CLASSIFIER_C,
        class_weight="balanced",
        max_iter=2_000,
        random_state=42,
    )


def _fit_head(head: LogisticRegression, matrix: np.ndarray, targets: np.ndarray) -> None:
    """Fit, treating non-convergence as fatal.

    Mirrors `image_model._fit_classifier`, and for the same reason: a
    `ConvergenceWarning` means the coefficients are wherever the solver
    stopped, so a score computed from them is not the score of the frozen
    contract. Round 107 found this path called `fit` directly and so could
    have fed an unconverged head into the decision statistic. The `penalty`
    deprecation is separately silenced as a known-benign notice about a
    keyword this contract pins.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="'penalty' was deprecated in version 1.8.*",
            category=FutureWarning,
        )
        warnings.simplefilter("error", ConvergenceWarning)
        head.fit(matrix, targets)


def _validate_inputs(
    train_features: pd.DataFrame,
    weak_labels: pd.DataFrame,
    evaluation_features: pd.DataFrame,
    continuous_dimensions: int,
    labels: Sequence[str],
) -> pd.DataFrame:
    """Reject the pairings a caller can silently get wrong.

    Equal row counts do not establish that row *i* of the features is the
    study that produced row *i* of the labels; a frame sorted or filtered on
    the way in keeps its length and loses its correspondence. Requiring equal
    indexes makes that misalignment loud. The notebook builds both frames
    positionally with a `RangeIndex`, so no misalignment was ever observed --
    this is the guard that keeps it that way.

    Returns:
        The weak labels as `float64`. **The caller must fit from this frame,
        not from its argument.** Round 109 and round 111 each found a type
        that passed validation and then behaved differently where it was
        consumed, because validation coerced and the fitting loop did not.
        Returning one normalized representation removes the second reader, so
        that class of divergence cannot recur by adding a dtype.
    """
    if len(train_features) != len(weak_labels):
        raise ValueError("train_features and weak_labels must have the same row count")
    if not train_features.index.equals(weak_labels.index):
        raise ValueError("train_features and weak_labels must share the same index")
    if list(weak_labels.columns) != list(labels):
        raise ValueError("weak_labels columns must match labels in order")

    # Checked before the width, because the expected width is *derived* from
    # this value: a non-positive split would otherwise be reported as a
    # feature frame of the wrong size, which sends the reader to the wrong
    # place entirely.
    if continuous_dimensions <= 0:
        raise ValueError("continuous_dimensions must be positive")
    expected_width = continuous_dimensions + FLAG_DIMENSIONS
    if train_features.shape[1] != expected_width:
        raise ValueError(f"train_features must be {expected_width}-dimensional")
    if train_features.shape[1] != evaluation_features.shape[1]:
        raise ValueError("training and evaluation features must have the same width")

    for name, frame in (
        ("train_features", train_features),
        ("evaluation_features", evaluation_features),
    ):
        if frame.empty or not np.isfinite(frame.to_numpy(dtype=np.float64)).all():
            raise ValueError(f"{name} must be non-empty and finite")

    # Checked before the coercion below, and not merely for tidiness. The
    # fitting loop reads `column.to_numpy()` *without* a dtype, so a
    # string-valued frame that survives `astype(float)` here would compare
    # `"1" == 1` as False downstream, count zero positives, and abstain every
    # label into a macro of exactly 0.5 -- a clean-looking null result
    # produced by a type error. Reproduced before this guard was added.
    # Complex is checked first because it *is* numeric by pandas' reckoning,
    # and casting it to float discards the imaginary part with only a
    # `ComplexWarning` -- so `1+1j` validated as a clean 1 while the fitting
    # loop, reading the original column, found `1+1j == 1` false. Round 111
    # reproduced twelve abstentions and a macro of exactly 0.5 that way.
    complex_columns = [
        label for label in labels if pd.api.types.is_complex_dtype(weak_labels[label])
    ]
    if complex_columns:
        raise ValueError(
            f"weak_labels columns must be real; got complex dtype in {complex_columns}"
        )
    non_numeric = [
        label for label in labels if not pd.api.types.is_numeric_dtype(weak_labels[label])
    ]
    if non_numeric:
        raise ValueError(f"weak_labels columns must be numeric; got object dtype in {non_numeric}")

    normalized = weak_labels.astype(np.float64)
    values = normalized.to_numpy()
    if not np.isin(values[~np.isnan(values)], (0.0, 1.0)).all():
        raise ValueError("weak_labels values must be 1, 0, or NaN for abstain")
    return normalized


def fit_weak_label_heads(
    train_features: pd.DataFrame,
    weak_labels: pd.DataFrame,
    evaluation_features: pd.DataFrame,
    continuous_dimensions: int = CONTINUOUS_DIMENSIONS,
    labels: Sequence[str] = tuple(LABEL_COLUMNS),
) -> WeakLabelFit:
    """Fit one head per label on its resolved rows and predict the eval set.

    Args:
        train_features: Study vectors for the weakly-labelled studies.
        weak_labels: Same row order, columns in `labels`, values 1, 0, or
            NaN for abstain.
        evaluation_features: Study vectors for the held-out studies to
            predict. Must be disjoint from `train_features` by construction;
            this function cannot check that and does not try.
        continuous_dimensions: Leading columns to standardize; the rest are
            the unscaled flags.
        labels: Label columns to fit, in output order.

    Returns:
        The predictions and the per-label support behind them.

    Raises:
        ValueError: If the frames disagree on shape, index, or columns, if a
            label column is complex or non-numeric, if a feature matrix is
            empty or non-finite, if a weak label is anything but 1, 0 or
            NaN, or if `continuous_dimensions` is not positive.
        ConvergenceWarning: If any head fails to converge, promoted to an
            error because an unconverged head is not the frozen contract.
    """
    # Rebound deliberately: everything below reads the validated float64
    # frame, so no consumer can see a representation validation did not.
    weak_labels = _validate_inputs(
        train_features, weak_labels, evaluation_features, continuous_dimensions, labels
    )

    train_matrix = train_features.to_numpy(dtype=np.float64)
    evaluation_matrix = evaluation_features.to_numpy(dtype=np.float64)

    probabilities = pd.DataFrame(
        ABSTAIN_PROBABILITY,
        index=evaluation_features.index,
        columns=list(labels),
        dtype=np.float64,
    )
    support: dict[str, int] = {}
    positives: dict[str, int] = {}
    abstained: list[str] = []

    for label in labels:
        column = weak_labels[label]
        resolved = column.notna().to_numpy()
        targets = column.to_numpy()[resolved]
        support[label] = int(resolved.sum())
        positives[label] = int((targets == 1).sum())

        negatives = int((targets == 0).sum())
        if (
            support[label] < WEAK_MIN_SUPPORT
            or positives[label] < WEAK_MIN_CLASS_COUNT
            or negatives < WEAK_MIN_CLASS_COUNT
        ):
            abstained.append(label)
            continue

        scaler = PartialStandardScaler(
            continuous_dimensions=continuous_dimensions
        ).fit(train_matrix[resolved])
        head = _binary_head()
        _fit_head(head, scaler.transform(train_matrix[resolved]), targets.astype(int))
        probabilities[label] = head.predict_proba(
            scaler.transform(evaluation_matrix)
        )[:, 1]

    return WeakLabelFit(
        probabilities=probabilities,
        support=support,
        positives=positives,
        abstained=tuple(abstained),
    )


def weak_label_frame(
    reports: Sequence[str], labels: Sequence[str] = tuple(LABEL_COLUMNS)
) -> pd.DataFrame:
    """Resolve a column of report text into a weak-label frame.

    Args:
        reports: One report per study, in study order.
        labels: Label columns to emit, in order.

    Returns:
        A frame of 1/0/NaN with one row per report.
    """
    from knee_mri.labels import extract_weak_labels

    rows = [extract_weak_labels(report if isinstance(report, str) else "") for report in reports]
    return pd.DataFrame(
        [[np.nan if row[label] is None else float(row[label]) for label in labels] for row in rows],
        columns=list(labels),
    )
