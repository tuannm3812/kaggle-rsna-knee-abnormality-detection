"""Competition scoring metric: macro-averaged AUC-ROC across the 12 labels."""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import roc_auc_score

from knee_mri.labels import LABEL_COLUMNS


def per_label_auc(y_true: pd.DataFrame, y_pred: pd.DataFrame) -> dict[str, float]:
    """Compute ROC-AUC independently for each of the 12 target columns.

    Args:
        y_true: Ground-truth binary labels, one column per `LABEL_COLUMNS`
            entry, one row per study.
        y_pred: Predicted probabilities, same shape/columns as `y_true`.

    Returns:
        A dict mapping each label column to its ROC-AUC score.

    Raises:
        ValueError: If either frame is missing a label column, or if a label
            column has only one class present in `y_true` (ROC-AUC is
            undefined in that case).
    """
    # Both metrics score the whole 12-label panel, so a single-label frame is
    # a caller error rather than a one-label score. Naming the missing columns
    # beats the bare KeyError that indexing would otherwise raise, which reads
    # as a missing row and sends the reader to the wrong place.
    for name, frame in (("y_true", y_true), ("y_pred", y_pred)):
        missing = [label for label in LABEL_COLUMNS if label not in frame.columns]
        if missing:
            raise ValueError(
                f"{name} is missing label columns {missing}; both metrics score "
                "the full panel, so pass every label and read one entry from "
                "the returned mapping."
            )

    if not y_true.index.equals(y_pred.index):
        # roc_auc_score drops the index and pairs rows positionally, so a
        # mismatch here would be scored against the wrong rows silently
        # rather than raising.
        raise ValueError("y_true and y_pred must share the same index")

    scores: dict[str, float] = {}
    for label in LABEL_COLUMNS:
        if y_true[label].nunique() < 2:
            raise ValueError(
                f"Cannot compute ROC-AUC for '{label}': only one class "
                "present in y_true."
            )
        scores[label] = roc_auc_score(y_true[label], y_pred[label])
    return scores


def macro_auc(y_true: pd.DataFrame, y_pred: pd.DataFrame) -> float:
    """Compute the competition metric: the unweighted mean of per-label ROC-AUC.

    Args:
        y_true: Ground-truth binary labels, one column per `LABEL_COLUMNS`
            entry, one row per study.
        y_pred: Predicted probabilities, same shape/columns as `y_true`.

    Returns:
        The macro-averaged ROC-AUC across the 12 target columns.
    """
    scores = per_label_auc(y_true, y_pred)
    return sum(scores.values()) / len(scores)
