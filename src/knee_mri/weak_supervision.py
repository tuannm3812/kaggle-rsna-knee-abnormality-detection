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

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from knee_mri.image_model import (
    CONTINUOUS_DIMENSIONS,
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
        ValueError: If the frames disagree on shape or columns.
    """
    if len(train_features) != len(weak_labels):
        raise ValueError("train_features and weak_labels must have the same row count")
    if list(weak_labels.columns) != list(labels):
        raise ValueError("weak_labels columns must match labels in order")
    if train_features.shape[1] != evaluation_features.shape[1]:
        raise ValueError("training and evaluation features must have the same width")

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
        head.fit(scaler.transform(train_matrix[resolved]), targets.astype(int))
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
