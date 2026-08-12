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


def _slice_laterality_tag(dataset: pydicom.Dataset) -> str | None:
    """A single slice's validated laterality, preferring `Laterality`."""
    for tag_name in _LATERALITY_TAGS:
        if tag_name in dataset:
            normalized = _normalize_laterality(getattr(dataset, tag_name))
            if normalized is not None:
                return normalized
    return None


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
            (`L`/`R`) `Laterality` or `ImageLaterality` value.
        laterality_tag: The validated laterality value shared by every
            tag-bearing slice, or `None` if no slice has a valid tag, or if
            tag-bearing slices disagree with each other.
        laterality_tag_consistent: Whether every tag-bearing slice agrees
            (trivially `True` if no slice has a valid tag).
        laterality_from_geometry: The geometry-derived laterality call, if
            resolvable.
        laterality_conflict: Whether `laterality_tag` and
            `laterality_from_geometry` are both resolved and disagree.
        laterality_filled_by_geometry: Whether `laterality_tag` is
            unresolved (missing, invalid, or inconsistent across slices)
            while `laterality_from_geometry` is resolved -- the case where a
            geometry fallback actually recovers a call the tag alone
            couldn't make.
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
    laterality_from_geometry: str | None
    laterality_conflict: bool
    laterality_filled_by_geometry: bool
    pixel_spacing: tuple[float, float] | None
    decode_attempted: int
    decode_failures: int
    decode_results: tuple[tuple[str, bool], ...]


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
    ordered_paths = dcm_paths
    if has_full_geometry_tags:
        normal = slice_normal(first.ImageOrientationPatient)
        positions = [slice_position(ds.ImagePositionPatient, normal) for ds in headers]
        instance_numbers = [int(ds.InstanceNumber) for ds in headers]
        agreement = order_agreement(instance_numbers, positions)
        rank = np.argsort(positions)
        ordered_paths = [dcm_paths[i] for i in rank]

    slice_laterality_tags = [_slice_laterality_tag(ds) for ds in headers]
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
        laterality_from_geometry=geometry_laterality,
        laterality_conflict=laterality_conflict,
        laterality_filled_by_geometry=laterality_filled_by_geometry,
        pixel_spacing=pixel_spacing,
        decode_attempted=len(sample_indices),
        decode_failures=decode_failures,
        decode_results=tuple(decode_results),
    )
