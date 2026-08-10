"""Competition submission construction and boundary validation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from knee_mri.labels import LABEL_COLUMNS


def build_submission(
    sample_df: pd.DataFrame,
    test_ids: pd.Series,
    probabilities: np.ndarray,
) -> pd.DataFrame:
    """Return a validated submission in competition row and column order.

    Args:
        sample_df: Competition sample submission in canonical schema.
        test_ids: Test identifiers in their original row order.
        probabilities: Test probabilities shaped as rows by canonical labels.

    Returns:
        A defensive copy of the sample with only target values replaced.

    Raises:
        ValueError: If schema, row order, identifiers, shape, or probability
            values violate the competition submission contract.
    """
    expected_columns = ["StudyInstanceUID", *LABEL_COLUMNS]
    if list(sample_df.columns) != expected_columns:
        raise ValueError("sample submission columns do not match the canonical schema")
    if len(sample_df) != len(test_ids):
        raise ValueError("sample submission and test row counts differ")

    sample_ids = sample_df["StudyInstanceUID"]
    if sample_ids.isna().any() or test_ids.isna().any():
        raise ValueError("submission identifiers must be non-null")
    if sample_ids.duplicated().any() or test_ids.duplicated().any():
        raise ValueError("submission identifiers must be unique")
    if not sample_ids.reset_index(drop=True).equals(test_ids.reset_index(drop=True)):
        raise ValueError("sample submission identifiers must match test order")

    values = np.asarray(probabilities, dtype=float)
    if values.shape != (len(test_ids), len(LABEL_COLUMNS)):
        raise ValueError("probability matrix has the wrong shape")
    if not np.isfinite(values).all() or ((values < 0.0) | (values > 1.0)).any():
        raise ValueError("probabilities must be finite and within [0, 1]")

    submission = sample_df.copy()
    submission.loc[:, LABEL_COLUMNS] = values
    return submission
