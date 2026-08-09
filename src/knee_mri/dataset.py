"""Study-level series selection and train.csv label-completeness splitting."""

from __future__ import annotations

import pandas as pd

from knee_mri.labels import LABEL_COLUMNS


def series_for_study(series_df: pd.DataFrame, study_id: str) -> pd.DataFrame:
    """Return every series row belonging to one study.

    Args:
        series_df: A `train_series.csv`/`test_series.csv`-shaped frame.
        study_id: The `StudyInstanceUID` to filter to.

    Returns:
        The subset of `series_df` for that study, in its original row order.
    """
    return series_df.loc[series_df["StudyInstanceUID"] == study_id]


def select_primary_series(
    series_df: pd.DataFrame,
    study_id: str,
    plane: str = "Sagittal",
    prefer_fluid_sensitive: bool = True,
) -> str | None:
    """Pick one `SeriesInstanceUID` to represent a study for a given plane.

    Filters to the requested `Anatomical_Plane` first, then (if requested)
    prefers a fluid-sensitive sequence — knee abnormalities like effusion,
    meniscus/ligament tears show up most clearly on fluid-sensitive
    sequences (T2/PD/STIR). Falls back to the first matching series if no
    fluid-sensitive one is present.

    Args:
        series_df: A `train_series.csv`/`test_series.csv`-shaped frame.
        study_id: The `StudyInstanceUID` to select a series for.
        plane: The `Anatomical_Plane` to require (`"Sagittal"`,
            `"Coronal"`, or `"Axial"`).
        prefer_fluid_sensitive: If `True`, prefer a series with
            `Fluid_Sensitive == 1` among the plane-matching candidates.

    Returns:
        The chosen `SeriesInstanceUID`, or `None` if no series for this
        study matches `plane`.
    """
    candidates = series_for_study(series_df, study_id)
    candidates = candidates.loc[candidates["Anatomical_Plane"] == plane]
    if candidates.empty:
        return None

    if prefer_fluid_sensitive:
        fluid_sensitive = candidates.loc[candidates["Fluid_Sensitive"] == 1]
        if not fluid_sensitive.empty:
            candidates = fluid_sensitive

    return str(candidates.iloc[0]["SeriesInstanceUID"])


def split_labeled_studies(
    train_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split `train.csv` into fully-labeled and label-missing studies.

    Args:
        train_df: A `train.csv`-shaped frame containing `LABEL_COLUMNS`.

    Returns:
        A `(labeled, unlabeled)` tuple: `labeled` has no missing values
        across `LABEL_COLUMNS`; `unlabeled` has at least one missing
        label and is a weak-labeling candidate (see
        `knee_mri.labels.extract_weak_labels`).
    """
    has_missing_label = train_df[LABEL_COLUMNS].isna().any(axis=1)
    labeled = train_df.loc[~has_missing_label]
    unlabeled = train_df.loc[has_missing_label]
    return labeled, unlabeled
