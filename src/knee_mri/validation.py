"""Shared validation boundaries for labeled competition studies."""

from __future__ import annotations

import numpy as np
import pandas as pd

from knee_mri.labels import LABEL_COLUMNS


def validate_labeled_studies(frame: pd.DataFrame) -> None:
    """Validate identifiers, reports, and binary targets for labeled studies.

    Args:
        frame: Fully labeled study rows containing the canonical identifier,
            report, and target columns.

    Raises:
        ValueError: If required columns are absent, the frame is empty,
            identifiers are null or duplicated, labels are not Boolean-free
            binary values, or reports are missing, non-string, or blank.
    """
    required_columns = {"StudyInstanceUID", "Report", *LABEL_COLUMNS}
    missing = required_columns - set(frame.columns)
    if missing:
        raise ValueError(f"labeled studies are missing required columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("labeled studies have zero rows")
    if frame["StudyInstanceUID"].isna().any() or frame["StudyInstanceUID"].duplicated().any():
        raise ValueError("labeled studies have null or duplicate StudyInstanceUID values")

    for label in LABEL_COLUMNS:
        column = frame[label]
        # Check values rather than dtype: bools can hide in object columns,
        # while valid CSV-derived labels remain float64 after NaN filtering.
        has_bool_value = column.apply(lambda value: isinstance(value, (bool, np.bool_))).any()
        if has_bool_value or not column.isin([0, 1]).all():
            raise ValueError(f"labeled studies column '{label}' has values outside {{0, 1}}")

    reports_are_strings = frame["Report"].apply(lambda value: isinstance(value, str))
    if frame["Report"].isna().any() or not reports_are_strings.all():
        raise ValueError("labeled studies have a missing or non-string Report value")
    if frame["Report"].str.strip().eq("").any():
        raise ValueError("labeled studies have a Report empty after stripping")
