"""Study-level series selection and competition-frame preparation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.validation import validate_labeled_studies


@dataclass(frozen=True)
class ModelingInputs:
    """Validated train/test views for Phase 3A modeling.

    Attributes:
        labeled_studies: Defensive copy of the fully labeled train rows.
        test_studies: Defensive copy of test rows with blank reports normalized.
        missing_test_report_count: Number of missing or blank test reports.
    """

    labeled_studies: pd.DataFrame
    test_studies: pd.DataFrame
    missing_test_report_count: int


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


def prepare_modeling_inputs(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    sample_df: pd.DataFrame,
    expected_labeled_count: int = 58,
) -> ModelingInputs:
    """Validate and prepare competition frames for report modeling.

    Args:
        train_df: Competition training frame containing reports and targets.
        test_df: Competition test frame containing reports.
        sample_df: Competition sample-submission frame in canonical order.
        expected_labeled_count: Frozen number of fully labeled train studies.

    Returns:
        Defensive labeled/test copies plus the aggregate blank-report count.

    Raises:
        ValueError: If any approved Phase 3A input-contract rule is violated.
    """
    train_required = {"StudyInstanceUID", "Report", *LABEL_COLUMNS}
    test_required = {"StudyInstanceUID", "Report"}
    sample_columns = ["StudyInstanceUID", *LABEL_COLUMNS]

    _require_columns(train_df, train_required, "train")
    _require_columns(test_df, test_required, "test")
    _require_columns(sample_df, set(sample_columns), "sample")
    if list(sample_df.columns) != sample_columns:
        raise ValueError("sample columns must match the canonical order")

    _validate_identifiers(train_df, "train")
    _validate_identifiers(test_df, "test")
    _validate_identifiers(sample_df, "sample")
    if not sample_df["StudyInstanceUID"].reset_index(drop=True).equals(
        test_df["StudyInstanceUID"].reset_index(drop=True)
    ):
        raise ValueError("sample and test identifiers must match in the same order")

    labeled, _ = split_labeled_studies(train_df)
    labeled = labeled.copy()
    if len(labeled) != expected_labeled_count:
        raise ValueError(f"expected exactly {expected_labeled_count} fully labeled studies")
    validate_labeled_studies(labeled)
    for label in LABEL_COLUMNS:
        if labeled[label].nunique() != 2:
            raise ValueError(f"labeled studies must contain both classes for '{label}'")

    test_studies = test_df.copy()
    reports = test_studies["Report"]
    missing_reports = reports.isna()
    reports_are_strings = reports.apply(lambda value: isinstance(value, str))
    if ((~missing_reports) & (~reports_are_strings)).any():
        raise ValueError("test has a non-string Report value")
    blank_reports = reports.apply(lambda value: isinstance(value, str) and not value.strip())
    empty_reports = missing_reports | blank_reports
    test_studies.loc[empty_reports, "Report"] = ""

    return ModelingInputs(
        labeled_studies=labeled,
        test_studies=test_studies,
        missing_test_report_count=int(empty_reports.sum()),
    )


def _require_columns(frame: pd.DataFrame, required: set[str], frame_name: str) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{frame_name} is missing required columns: {sorted(missing)}")


def _validate_identifiers(frame: pd.DataFrame, frame_name: str) -> None:
    identifiers = frame["StudyInstanceUID"]
    if identifiers.isna().any():
        raise ValueError(f"{frame_name} has null StudyInstanceUID values")
    if identifiers.duplicated().any():
        raise ValueError(f"{frame_name} has duplicate StudyInstanceUID values")
