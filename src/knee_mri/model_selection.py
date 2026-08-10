"""Deterministic multilabel fold selection for study-level evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from iterstrat.ml_stratifiers import MultilabelStratifiedKFold

from knee_mri.labels import LABEL_COLUMNS

FoldIndices = tuple[np.ndarray, np.ndarray]


def select_multilabel_folds(
    y: pd.DataFrame,
    candidate_splits: tuple[int, ...] = (5, 4, 3, 2),
    seed: int = 42,
) -> tuple[int, tuple[FoldIndices, ...]]:
    """Select the first split whose validation folds contain both classes.

    Each candidate is instantiated and materialized exactly once. Candidate
    order is authoritative; no seed retry or model score influences selection.

    Args:
        y: Binary target frame in canonical label-column order.
        candidate_splits: Fold counts to attempt, in preference order.
        seed: Random seed shared by every candidate splitter.

    Returns:
        The selected fold count and its train/validation positional indices.

    Raises:
        ValueError: If the target frame is malformed or no candidate gives
            both classes for every label in every validation fold.
    """
    if list(y.columns) != LABEL_COLUMNS:
        raise ValueError("y columns must match LABEL_COLUMNS in canonical order")
    if y.empty or not y.isin([0, 1]).all().all():
        raise ValueError("y must be a non-empty binary target frame")

    positions = np.arange(len(y))
    for n_splits in candidate_splits:
        splitter = MultilabelStratifiedKFold(
            n_splits=n_splits,
            shuffle=True,
            random_state=seed,
        )
        folds = tuple(splitter.split(positions, y.to_numpy()))
        if all(y.iloc[validation].nunique().eq(2).all() for _, validation in folds):
            return n_splits, folds

    raise ValueError("No candidate fold count gives both classes for every validation label")
