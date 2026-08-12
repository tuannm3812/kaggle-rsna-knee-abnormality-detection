"""Aggregate-only DICOM/series audit.

Computes geometry-derived slice order and laterality, decode reliability,
and series-metadata agreement statistics used to inform the Phase 3B image
pipeline design before it is frozen (see `docs/collaboration/active_task.md`
round 38, finding 3). Every function here is aggregate/per-series -- callers
are responsible for not logging raw pixel data, report text, or study
identifiers alongside the results.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pydicom


def slice_normal(image_orientation_patient: Sequence[float]) -> np.ndarray:
    """Unit vector normal to a DICOM slice plane.

    Args:
        image_orientation_patient: The six `ImageOrientationPatient` direction
            cosines -- the first three for the row direction (increasing
            column index), the last three for the column direction
            (increasing row index).

    Returns:
        The unit-length cross product of the two direction vectors.

    Raises:
        ValueError: If the two direction vectors are degenerate (cross
            product is zero).
    """
    iop = np.asarray(image_orientation_patient, dtype=float)
    row_direction, column_direction = iop[:3], iop[3:]
    normal = np.cross(row_direction, column_direction)
    norm = np.linalg.norm(normal)
    if norm == 0:
        raise ValueError("image_orientation_patient direction vectors are degenerate")
    return normal / norm


def slice_position(image_position_patient: Sequence[float], normal: np.ndarray) -> float:
    """Signed distance of a slice's origin along its plane normal.

    Args:
        image_position_patient: `ImagePositionPatient`, the (x, y, z) of the
            first pixel's center, in mm.
        normal: A slice-plane normal from `slice_normal`.

    Returns:
        The projection of `image_position_patient` onto `normal`; slices
        from the same series can be ranked by this value to recover true
        physical order.
    """
    return float(np.dot(np.asarray(image_position_patient, dtype=float), normal))


def order_agreement(
    instance_numbers: Sequence[int], geometry_positions: Sequence[float]
) -> float | None:
    """Spearman rank correlation between `InstanceNumber` and geometry order.

    A consistent reversal (correlation near -1) is still a usable order --
    only correlations near 0 indicate the two orderings actually disagree.

    Args:
        instance_numbers: Each slice's `InstanceNumber`.
        geometry_positions: Each slice's `slice_position`, same order.

    Returns:
        The rank correlation in [-1, 1], or `None` if fewer than two slices
        are given.

    Raises:
        ValueError: If the two sequences have different lengths.
    """
    if len(instance_numbers) != len(geometry_positions):
        raise ValueError("instance_numbers and geometry_positions must be the same length")
    if len(instance_numbers) < 2:
        return None
    instance_ranks = np.argsort(np.argsort(instance_numbers))
    geometry_ranks = np.argsort(np.argsort(geometry_positions))
    return float(np.corrcoef(instance_ranks, geometry_ranks)[0, 1])


def laterality_from_geometry(
    image_position_patient: Sequence[float],
    image_orientation_patient: Sequence[float],
    rows: int,
    columns: int,
    pixel_spacing: Sequence[float],
    dead_zone_mm: float = 20.0,
) -> str | None:
    """Infer scanned-knee laterality from DICOM geometry tags.

    Computes the image's physical center in patient (LPS) coordinates per
    the standard DICOM pixel-to-patient mapping and reads its sign along the
    patient's left-right axis (positive x is patient left in LPS).

    Args:
        image_position_patient: `ImagePositionPatient`, the (x, y, z) of the
            first pixel's center, in mm.
        image_orientation_patient: `ImageOrientationPatient`'s six direction
            cosines (row direction, then column direction).
        rows: `Rows`, the slice's pixel height.
        columns: `Columns`, the slice's pixel width.
        pixel_spacing: `PixelSpacing`, (row spacing, column spacing) in mm.
        dead_zone_mm: Minimum |x| to call a side; smaller values are
            reported as unresolved (near the body midline).

    Returns:
        `"L"`, `"R"`, or `None` if the center falls within the dead zone.
    """
    ipp = np.asarray(image_position_patient, dtype=float)
    iop = np.asarray(image_orientation_patient, dtype=float)
    row_direction, column_direction = iop[:3], iop[3:]
    row_spacing, column_spacing = (float(value) for value in pixel_spacing)
    # DICOM's pixel-to-patient mapping indexes pixel centers from 0, so the
    # image's center pixel index is (columns - 1) / 2 and (rows - 1) / 2, not
    # columns / 2 and rows / 2.
    center = (
        ipp
        + ((columns - 1) / 2) * column_spacing * row_direction
        + ((rows - 1) / 2) * row_spacing * column_direction
    )
    x = center[0]
    if x > dead_zone_mm:
        return "L"
    if x < -dead_zone_mm:
        return "R"
    return None


_VALID_LATERALITY_VALUES = frozenset({"L", "R"})

# `Laterality` (0020,0060) is the general DICOM laterality tag; the newer,
# more specific `ImageLaterality` (0020,0062) is checked as a fallback when
# `Laterality` is absent or invalid on a given slice.
_LATERALITY_TAGS = ("Laterality", "ImageLaterality")


def _normalize_laterality(raw: object) -> str | None:
    """Validate a raw DICOM laterality value, rejecting anything but L/R."""
    if raw is None:
        return None
    value = str(raw).strip().upper()
    return value if value in _VALID_LATERALITY_VALUES else None


def _slice_laterality_values(dataset: pydicom.Dataset) -> dict[str, str]:
    """Every present, valid laterality-family value on one slice, by tag name."""
    values = {}
    for tag_name in _LATERALITY_TAGS:
        if tag_name in dataset:
            normalized = _normalize_laterality(getattr(dataset, tag_name))
            if normalized is not None:
                values[tag_name] = normalized
    return values


def _slice_laterality_tag(dataset: pydicom.Dataset) -> str | None:
    """A single slice's validated laterality call, preferring `Laterality`.

    Does not by itself reveal a `Laterality`/`ImageLaterality` disagreement
    when both are valid -- see `_slice_laterality_cross_tag_conflict`.
    """
    values = _slice_laterality_values(dataset)
    for tag_name in _LATERALITY_TAGS:
        if tag_name in values:
            return values[tag_name]
    return None


def _slice_laterality_cross_tag_conflict(dataset: pydicom.Dataset) -> bool:
    """Whether `Laterality` and `ImageLaterality` are both valid and disagree."""
    values = _slice_laterality_values(dataset)
    return len(set(values.values())) > 1


def central_band_indices(
    slice_count: int, sample_size: int, band: tuple[float, float] = (0.2, 0.8)
) -> list[int]:
    """Evenly-spaced slice indices within a stack's central fraction.

    Args:
        slice_count: Total number of slices in the (anatomically-ordered)
            stack.
        sample_size: How many indices to return.
        band: The (low, high) fraction of the stack to sample within.

    Returns:
        Sorted, de-duplicated 0-based indices; length is at most
        `min(sample_size, slice_count)`.

    Raises:
        ValueError: If `slice_count` or `sample_size` is not positive.
    """
    if slice_count <= 0:
        raise ValueError("slice_count must be positive")
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    low, high = band
    low_index = low * (slice_count - 1)
    high_index = high * (slice_count - 1)
    positions = np.linspace(low_index, high_index, num=min(sample_size, slice_count))
    return sorted({round(position) for position in positions})


def fluid_fat_suppression_agreement(series_df: pd.DataFrame) -> dict[str, float | int]:
    """Cross-tabulate `Fluid_Sensitive` against `Fat_Suppression`.

    Args:
        series_df: A `train_series.csv`/`test_series.csv`-shaped frame.

    Returns:
        A dict with `total`, `agree`, `agreement_rate`, and counts for each
        of the four (fluid, fat_suppression) combinations.
    """
    fluid = series_df["Fluid_Sensitive"]
    fat = series_df["Fat_Suppression"]
    total = len(series_df)
    agree = int((fluid == fat).sum())
    return {
        "total": total,
        "agree": agree,
        "agreement_rate": agree / total if total else float("nan"),
        "fluid1_fat1": int(((fluid == 1) & (fat == 1)).sum()),
        "fluid1_fat0": int(((fluid == 1) & (fat == 0)).sum()),
        "fluid0_fat1": int(((fluid == 0) & (fat == 1)).sum()),
        "fluid0_fat0": int(((fluid == 0) & (fat == 0)).sum()),
    }


def plane_series_counts(series_df: pd.DataFrame) -> pd.DataFrame:
    """Per-study series counts by `Anatomical_Plane`.

    Args:
        series_df: A `train_series.csv`/`test_series.csv`-shaped frame.

    Returns:
        A study-indexed frame with one column per observed plane, counting
        that study's series in each plane (0 where absent).
    """
    return (
        series_df.groupby(["StudyInstanceUID", "Anatomical_Plane"]).size().unstack(fill_value=0)
    )


@dataclass(frozen=True)
class SeriesAudit:
    """Aggregate-only geometry/decode audit for one DICOM series.

    Attributes:
        slice_count: Number of `.dcm` files found.
        has_full_geometry_tags: Whether every slice carries both
            `ImagePositionPatient` and `ImageOrientationPatient`.
        order_agreement: Signed `InstanceNumber`-vs-geometry Spearman rank
            correlation, or `None` if geometry tags are missing or there are
            <2 slices. A value near +1 or -1 both mean the two orderings are
            consistently monotonic; the sign alone does not indicate which
            physical direction `InstanceNumber` increases in without a
            separately fixed geometry-axis convention.
        laterality_tag_present_fraction: Fraction of slices carrying a valid
            (`L`/`R`) `Laterality` or `ImageLaterality` value. `0.0` is "no
            slice has a valid tag", `1.0` is "every slice does" (complete
            coverage); values between are partial coverage.
        laterality_tag: The validated laterality value shared by every
            tag-bearing slice, or `None` if no slice has a valid tag, or if
            tag-bearing slices disagree with each other. Where a slice has
            both a valid `Laterality` and a disagreeing valid
            `ImageLaterality`, this uses `Laterality`'s value (see
            `laterality_cross_tag_conflict` for whether that happened).
        laterality_tag_consistent: Whether every tag-bearing slice's *call*
            (post cross-tag precedence) agrees (trivially `True` if no slice
            has a valid tag).
        laterality_cross_tag_conflict: Whether any single slice has both a
            valid `Laterality` and a valid `ImageLaterality` that disagree
            with each other -- a stronger, more specific signal than
            `laterality_tag_consistent`, which only compares the resolved
            call across slices and would not by itself surface this.
        laterality_from_geometry: The geometry-derived laterality call, if
            resolvable.
        laterality_conflict: Whether `laterality_tag` and
            `laterality_from_geometry` are both resolved and disagree.
        laterality_filled_by_geometry: Whether `laterality_tag` is
            unresolved (missing, invalid, or inconsistent across slices)
            while `laterality_from_geometry` is resolved -- the case where a
            geometry fallback actually recovers a call the tag alone
            couldn't make.
        laterality_resolved_call: `laterality_tag` if resolved, else
            `laterality_from_geometry`, else `None` -- one candidate
            tag-over-geometry precedence for audit/reporting purposes only.
            This precedence (and whether a cross-tag or tag/geometry
            conflict should ever be silently resolved rather than left
            unresolved) is a modeling-pipeline design decision, not yet
            approved; do not treat this field as production policy.
        pixel_spacing: The first slice's `PixelSpacing`, if present.
        decode_attempted: How many slices a full pixel decode was tried on.
        decode_failures: How many of those decodes raised an exception.
        decode_results: One `(transfer_syntax_uid, succeeded)` pair per
            attempted decode, so failures can be attributed to specific
            transfer syntaxes rather than reported as one undifferentiated
            rate.
    """

    slice_count: int
    has_full_geometry_tags: bool
    order_agreement: float | None
    laterality_tag_present_fraction: float
    laterality_tag: str | None
    laterality_tag_consistent: bool
    laterality_cross_tag_conflict: bool
    laterality_from_geometry: str | None
    laterality_conflict: bool
    laterality_filled_by_geometry: bool
    laterality_resolved_call: str | None
    pixel_spacing: tuple[float, float] | None
    decode_attempted: int
    decode_failures: int
    decode_results: tuple[tuple[str, bool], ...]


def _instance_number_sort_key(dataset: pydicom.Dataset) -> tuple[int, int]:
    """Sort key ranking a valid `InstanceNumber` first, ascending.

    Slices with a missing or non-integer `InstanceNumber` sort after every
    valid one; Python's stable sort then leaves them in their original
    (filename) relative order as a final deterministic tie-break.
    """
    if "InstanceNumber" in dataset:
        try:
            return (0, int(dataset.InstanceNumber))
        except (TypeError, ValueError):
            pass
    return (1, 0)


def _order_paths_by_geometry(
    dcm_paths: Sequence[Path], headers: Sequence[pydicom.Dataset]
) -> list[Path]:
    """`dcm_paths` reordered by true DICOM geometry.

    Falls back to `InstanceNumber` order when geometry tags aren't complete
    -- the round-39/41 preflight audit measured `InstanceNumber` order as a
    reliable proxy for true physical order in this dataset (unlike raw
    filename/SOP-UID order, previously measured unreliable), and
    `dicom_io.py::load_series` already relies on the same tag for this
    reason. Missing/invalid/duplicate `InstanceNumber` values fall back
    further, deterministically, to filename order.
    """
    has_full_geometry_tags = all(
        "ImagePositionPatient" in ds and "ImageOrientationPatient" in ds for ds in headers
    )
    if has_full_geometry_tags:
        normal = slice_normal(headers[0].ImageOrientationPatient)
        positions = [slice_position(ds.ImagePositionPatient, normal) for ds in headers]
        rank = np.argsort(positions)
        return [dcm_paths[i] for i in rank]
    order = sorted(range(len(headers)), key=lambda i: _instance_number_sort_key(headers[i]))
    return [dcm_paths[i] for i in order]


def anatomically_ordered_paths(series_dir: Path) -> list[Path]:
    """Every `.dcm` in `series_dir`, ordered by true DICOM geometry.

    Falls back to `InstanceNumber` order (then filename order as a final,
    deterministic tie-break) when geometry tags aren't available on every
    slice. Exposed so callers besides `audit_series` (e.g. the actual
    slice-sampling pipeline) order slices the same, empirically-checked way
    rather than re-deriving or duplicating this logic.

    Args:
        series_dir: Directory containing one series' `.dcm` slice files.

    Returns:
        Paths sorted into anatomical order.

    Raises:
        FileNotFoundError: If `series_dir` contains no `.dcm` files.
    """
    dcm_paths = sorted(series_dir.glob("*.dcm"))
    if not dcm_paths:
        raise FileNotFoundError(f"No .dcm files found in {series_dir}")
    headers = [pydicom.dcmread(path, stop_before_pixels=True) for path in dcm_paths]
    return _order_paths_by_geometry(dcm_paths, headers)


@dataclass(frozen=True)
class GroupLateralityAgreement:
    """Aggregate laterality-call agreement across a group of series.

    Intended for an ephemeral, in-memory grouping (e.g. every series in one
    study, or just its up-to-three plane-representative series) -- callers
    are responsible for never persisting the identifiers used to form the
    group alongside this result.

    Attributes:
        total: Number of series in the group.
        resolved: Number of series with a non-`None` call.
        consistent: Whether every resolved call agrees (trivially `True` if
            none are resolved).
        consensus_call: The shared call if `consistent` and at least one
            series resolved, else `None`.
    """

    total: int
    resolved: int
    consistent: bool
    consensus_call: str | None


def aggregate_group_laterality(resolved_calls: Sequence[str | None]) -> GroupLateralityAgreement:
    """Summarize agreement across a group's per-series `laterality_resolved_call`s.

    Args:
        resolved_calls: One `SeriesAudit.laterality_resolved_call` per series
            in the group (`None` where unresolved).

    Returns:
        The computed `GroupLateralityAgreement`.
    """
    present = [call for call in resolved_calls if call is not None]
    distinct = set(present)
    consistent = len(distinct) <= 1
    return GroupLateralityAgreement(
        total=len(resolved_calls),
        resolved=len(present),
        consistent=consistent,
        consensus_call=present[0] if consistent and present else None,
    )


def audit_series(series_dir: Path, decode_sample_size: int = 5) -> SeriesAudit:
    """Read every `.dcm` in `series_dir` and compute a geometry/decode audit.

    Header tags are read for every slice (cheap, `stop_before_pixels`);
    pixel data is fully decoded only for a `central_band_indices` sample of
    the anatomically-ordered stack, matching the sampling the real pipeline
    intends to use, so decode reliability is measured without paying full-
    series decode cost.

    Args:
        series_dir: Directory containing one series' `.dcm` slice files.
        decode_sample_size: How many slices to attempt full pixel decode on.

    Returns:
        The computed `SeriesAudit`.

    Raises:
        FileNotFoundError: If `series_dir` contains no `.dcm` files.
    """
    dcm_paths = sorted(series_dir.glob("*.dcm"))
    if not dcm_paths:
        raise FileNotFoundError(f"No .dcm files found in {series_dir}")

    headers = [pydicom.dcmread(path, stop_before_pixels=True) for path in dcm_paths]
    slice_count = len(headers)
    first = headers[0]

    has_full_geometry_tags = all(
        "ImagePositionPatient" in ds and "ImageOrientationPatient" in ds for ds in headers
    )

    agreement: float | None = None
    if has_full_geometry_tags:
        normal = slice_normal(first.ImageOrientationPatient)
        positions = [slice_position(ds.ImagePositionPatient, normal) for ds in headers]
        instance_numbers = [int(ds.InstanceNumber) for ds in headers]
        agreement = order_agreement(instance_numbers, positions)
    ordered_paths = _order_paths_by_geometry(dcm_paths, headers)

    slice_laterality_tags = [_slice_laterality_tag(ds) for ds in headers]
    has_cross_tag_conflict = any(_slice_laterality_cross_tag_conflict(ds) for ds in headers)
    present_tags = [tag for tag in slice_laterality_tags if tag is not None]
    laterality_tag_present_fraction = len(present_tags) / slice_count if slice_count else 0.0
    distinct_tags = set(present_tags)
    laterality_tag_consistent = len(distinct_tags) <= 1
    laterality_tag = present_tags[0] if laterality_tag_consistent and present_tags else None

    geometry_laterality = None
    if has_full_geometry_tags and "PixelSpacing" in first:
        geometry_laterality = laterality_from_geometry(
            first.ImagePositionPatient,
            first.ImageOrientationPatient,
            int(first.Rows),
            int(first.Columns),
            first.PixelSpacing,
        )

    laterality_conflict = bool(
        laterality_tag and geometry_laterality and laterality_tag != geometry_laterality
    )
    laterality_filled_by_geometry = bool(laterality_tag is None and geometry_laterality is not None)
    laterality_resolved_call = laterality_tag if laterality_tag is not None else geometry_laterality

    pixel_spacing = (
        (float(first.PixelSpacing[0]), float(first.PixelSpacing[1]))
        if "PixelSpacing" in first
        else None
    )

    sample_indices = central_band_indices(len(ordered_paths), decode_sample_size)
    decode_results: list[tuple[str, bool]] = []
    for index in sample_indices:
        path = ordered_paths[index]
        try:
            dataset = pydicom.dcmread(path)
            transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
            _ = dataset.pixel_array
            decode_results.append((transfer_syntax, True))
        except Exception:
            try:
                transfer_syntax = str(
                    pydicom.dcmread(path, stop_before_pixels=True).file_meta.TransferSyntaxUID
                )
            except Exception:
                transfer_syntax = "unknown"
            decode_results.append((transfer_syntax, False))
    decode_failures = sum(1 for _, succeeded in decode_results if not succeeded)

    return SeriesAudit(
        slice_count=slice_count,
        has_full_geometry_tags=has_full_geometry_tags,
        order_agreement=agreement,
        laterality_tag_present_fraction=laterality_tag_present_fraction,
        laterality_tag=laterality_tag,
        laterality_tag_consistent=laterality_tag_consistent,
        laterality_cross_tag_conflict=has_cross_tag_conflict,
        laterality_from_geometry=geometry_laterality,
        laterality_conflict=laterality_conflict,
        laterality_filled_by_geometry=laterality_filled_by_geometry,
        laterality_resolved_call=laterality_resolved_call,
        pixel_spacing=pixel_spacing,
        decode_attempted=len(sample_indices),
        decode_failures=decode_failures,
        decode_results=tuple(decode_results),
    )
