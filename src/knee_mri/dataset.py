"""Study-level series selection and competition-frame preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.series_audit import validate_and_order_series
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


def rank_candidate_series(
    series_df: pd.DataFrame,
    series_root: Path,
    study_id: str,
    plane: str,
    prefer_fluid_sensitive: bool = True,
) -> list[str]:
    """Rank a study's candidate series for one plane, most to least preferred.

    Preference order: `Fluid_Sensitive == 1` before `== 0` (the same
    preference `select_primary_series` uses); more `.dcm` slices before
    fewer, a cheap deterministic proxy for series completeness;
    `SeriesInstanceUID` ascending as a final, fully deterministic tie-break.
    Unlike `select_primary_series`, this returns every candidate in
    preference order (not just the top pick), so a caller can retry the
    next one if the top choice fails validation.

    Args:
        series_df: A `train_series.csv`/`test_series.csv`-shaped frame.
        series_root: Directory containing
            `<StudyInstanceUID>/<SeriesInstanceUID>/` DICOM subdirectories
            -- read only to count each candidate's slices for ranking.
        study_id: The `StudyInstanceUID` to rank candidates for.
        plane: The `Anatomical_Plane` to require.
        prefer_fluid_sensitive: If `True`, rank `Fluid_Sensitive == 1`
            series ahead of `== 0` ones.

    Returns:
        `SeriesInstanceUID`s in preference order (most to least); empty if
        the study has no series in `plane`.
    """
    candidates = series_for_study(series_df, study_id)
    candidates = candidates.loc[candidates["Anatomical_Plane"] == plane]
    if candidates.empty:
        return []

    def _slice_count(series_id: str) -> int:
        series_dir = series_root / study_id / series_id
        return len(list(series_dir.glob("*.dcm"))) if series_dir.is_dir() else 0

    def _sort_key(row: dict) -> tuple[int, int, str]:
        series_id = str(row["SeriesInstanceUID"])
        fluid_rank = 0 if (prefer_fluid_sensitive and row["Fluid_Sensitive"] == 1) else 1
        return (fluid_rank, -_slice_count(series_id), series_id)

    ranked_rows = sorted(candidates.to_dict("records"), key=_sort_key)
    return [str(row["SeriesInstanceUID"]) for row in ranked_rows]


@dataclass(frozen=True)
class PlaneSelection:
    """The outcome of selecting one usable series for a plane.

    Attributes:
        plane: The `Anatomical_Plane` this selection is for.
        series_instance_uid: The selected series, or `None` if no ranked
            candidate validated (the missing-plane case).
        ordering_method: `"geometry"` or `"instance_number"` if a series was
            selected, else `None`.
        ordered_paths: The selected series' validated slice order, or
            `None` if no candidate validated.
        candidates_tried: How many ranked candidates were validated before
            returning (including the winner, if any) -- `1` means the
            top-ranked candidate validated with no retry needed.
    """

    plane: str
    series_instance_uid: str | None
    ordering_method: str | None
    ordered_paths: tuple[Path, ...] | None
    candidates_tried: int


def select_validated_series(
    series_df: pd.DataFrame,
    series_root: Path,
    study_id: str,
    plane: str,
    prefer_fluid_sensitive: bool = True,
) -> PlaneSelection:
    """Rank `plane`'s candidates and return the first that validates.

    Tries each of `rank_candidate_series`'s candidates in order, validating
    each with `series_audit.validate_and_order_series`, and returns the
    first usable one. If no candidate validates (or none exist), returns a
    `PlaneSelection` with `series_instance_uid=None` -- the missing-plane
    case, to be excluded from the study embedding with its presence flag
    set to 0 (`docs/collaboration/active_task.md` rounds 46-47). A series
    that fails validation is never used and never falls back to an
    unvalidated (e.g. filename) order.

    Args:
        series_df: A `train_series.csv`/`test_series.csv`-shaped frame.
        series_root: Directory containing
            `<StudyInstanceUID>/<SeriesInstanceUID>/` DICOM subdirectories.
        study_id: The `StudyInstanceUID` to select a series for.
        plane: The `Anatomical_Plane` to require.
        prefer_fluid_sensitive: Passed through to `rank_candidate_series`.

    Returns:
        The computed `PlaneSelection`.
    """
    candidates = rank_candidate_series(
        series_df, series_root, study_id, plane, prefer_fluid_sensitive
    )
    candidates_tried = 0
    for series_id in candidates:
        series_dir = series_root / study_id / series_id
        candidates_tried += 1
        try:
            validation = validate_and_order_series(series_dir)
        except FileNotFoundError:
            continue
        if validation.usable:
            return PlaneSelection(
                plane=plane,
                series_instance_uid=series_id,
                ordering_method=validation.method,
                ordered_paths=validation.ordered_paths,
                candidates_tried=candidates_tried,
            )
    return PlaneSelection(
        plane=plane,
        series_instance_uid=None,
        ordering_method=None,
        ordered_paths=None,
        candidates_tried=candidates_tried,
    )


def validated_plane_candidates(
    series_df: pd.DataFrame,
    series_root: Path,
    study_id: str,
    plane: str,
    prefer_fluid_sensitive: bool = True,
) -> list[tuple[str, tuple[Path, ...]]]:
    """Every ranked candidate for a plane that passes ordering validation.

    `select_validated_series` returns only the first candidate that
    validates, which is right when ordering is the only thing that can fail.
    But section 4 of the Phase 3B specification adds a second, later failure
    mode -- fewer than three of the sampled slices decoding -- and requires
    that to trigger the same same-plane retry. A caller cannot do that with
    only the winner, so this returns the whole validated shortlist in
    preference order and lets the decode stage keep walking it.

    Args:
        series_df: A `train_series.csv`/`test_series.csv`-shaped frame.
        series_root: Directory containing
            `<StudyInstanceUID>/<SeriesInstanceUID>/` DICOM subdirectories.
        study_id: The `StudyInstanceUID` to rank candidates for.
        plane: The `Anatomical_Plane` to require.
        prefer_fluid_sensitive: Passed through to `rank_candidate_series`.

    Returns:
        `(series_instance_uid, ordered_paths)` for each candidate that
        validated, in preference order. Empty when the plane has no series
        or none of them validate -- the missing-plane case.
    """
    validated: list[tuple[str, tuple[Path, ...]]] = []
    for series_id in rank_candidate_series(
        series_df, series_root, study_id, plane, prefer_fluid_sensitive
    ):
        series_dir = series_root / study_id / series_id
        try:
            validation = validate_and_order_series(series_dir)
        except FileNotFoundError:
            continue
        if validation.usable and validation.ordered_paths is not None:
            validated.append((series_id, validation.ordered_paths))
    return validated


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
    # An all-missing Report column arrives from read_csv as float64, and
    # assigning "" into it raises TypeError on pandas 3.x (it only warned on
    # 2.x, and pyproject allows >=2.2 with no upper bound). Cast first so the
    # normalization this function documents works on both.
    test_studies["Report"] = test_studies["Report"].astype(object).mask(empty_reports, "")

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
