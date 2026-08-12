"""Aggregate-only DICOM/series audit.

Computes geometry-derived slice order and laterality, decode reliability,
and series-metadata agreement statistics used to inform the Phase 3B image
pipeline design before it is frozen (see `docs/collaboration/active_task.md`
round 38, finding 3). Every function here is aggregate/per-series -- callers
are responsible for not logging raw pixel data, report text, or study
identifiers alongside the results.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
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
        header_read_failures: Number of those files whose header could not
            be read (malformed DICOM or an OS-level read error). Any value
            above 0 means `ordering_usable` is forced `False` -- a series
            this project can't fully read isn't one it can validate the
            order of -- while the other diagnostics are still computed from
            whichever headers were read successfully (round 55, finding 1).
        has_full_geometry_tags: Whether every successfully-read slice
            carries both `ImagePositionPatient` and
            `ImageOrientationPatient`.
        order_agreement: Signed `InstanceNumber`-vs-geometry Spearman rank
            correlation, or `None` if geometry tags are missing or there are
            <2 slices. A value near +1 or -1 both mean the two orderings are
            consistently monotonic; the sign alone does not indicate which
            physical direction `InstanceNumber` increases in without a
            separately fixed geometry-axis convention.
        ordering_usable: Whether `validate_and_order_series`'s stricter
            production-grade gate (finite/parseable/non-degenerate/
            consistent-orientation/unique-position geometry, or else a
            fully-parseable-and-unique `InstanceNumber` sequence) passed --
            a stronger requirement than `has_full_geometry_tags`, which only
            checks tag presence, not validity.
        ordering_method: `"geometry"` or `"instance_number"` if
            `ordering_usable`, else `None`.
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
    header_read_failures: int
    has_full_geometry_tags: bool
    order_agreement: float | None
    ordering_usable: bool
    ordering_method: str | None
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


# Minimum cosine similarity each slice's row/column direction cosines must
# have with the first slice's (round-50-approved full-orientation-agreement
# contract, not just derived-normal agreement -- round 52, finding 3).
# 0.999 corresponds to roughly a 2.6-degree misalignment budget: generous
# enough for real-world floating-point/rounding noise in a single coherent
# acquisition, tight enough to reject a genuinely different orientation
# (e.g. a 90-degree in-plane rotation, which agreeing derived normals alone
# would miss).
_ORIENTATION_TOLERANCE_DEFAULT = 0.999
# Minimum spacing (mm) required between any two slices' projected
# positions, so two slices at (numerically) the same physical location
# aren't treated as orderable. 0.01mm is far below this dataset's observed
# pixel spacing range (0.137-1.172mm, docs/7_image_baseline_insights.md) --
# small enough to only catch genuine duplicates/near-duplicates, not flag
# real, closely-spaced slices as a problem.
_POSITION_TOLERANCE_MM_DEFAULT = 0.01
# Maximum allowed deviation of each direction-cosine vector's norm from 1.0.
# DICOM's ImageOrientationPatient direction cosines are defined as unit
# vectors; 0.01 tolerates ordinary floating-point storage/rounding noise
# without accepting a meaningfully non-unit (and therefore untrustworthy)
# vector.
_UNIT_NORM_TOLERANCE_DEFAULT = 0.01
# Maximum allowed |dot product| between a slice's row and column direction
# cosines, which the DICOM standard defines as orthogonal (dot product 0).
# 0.01 tolerates rounding noise without accepting a meaningfully non-
# orthogonal (and therefore untrustworthy) pair.
_ORTHOGONALITY_TOLERANCE_DEFAULT = 0.01


@dataclass(frozen=True)
class OrderingValidation:
    """Whether a series' slices validate for reliable anatomical ordering.

    Attributes:
        usable: Whether either validation route succeeded.
        method: `"geometry"` or `"instance_number"` if `usable`, else
            `None`.
        ordered_paths: The validated slice order, or `None` if not usable.
    """

    usable: bool
    method: str | None
    ordered_paths: tuple[Path, ...] | None


def _finite_floats(raw: Sequence[object], expected_length: int) -> tuple[float, ...] | None:
    try:
        values = tuple(float(v) for v in raw)
    except (TypeError, ValueError):
        return None
    if len(values) != expected_length or not all(math.isfinite(v) for v in values):
        return None
    return values


def _validated_geometry_order(
    dcm_paths: Sequence[Path],
    headers: Sequence[pydicom.Dataset],
    orientation_tolerance: float,
    position_tolerance_mm: float,
    unit_norm_tolerance: float,
    orthogonality_tolerance: float,
) -> list[Path] | None:
    row_directions: list[np.ndarray] = []
    column_directions: list[np.ndarray] = []
    positions_raw: list[tuple[float, ...]] = []
    for dataset in headers:
        if "ImagePositionPatient" not in dataset or "ImageOrientationPatient" not in dataset:
            return None
        orientation = _finite_floats(dataset.ImageOrientationPatient, 6)
        position = _finite_floats(dataset.ImagePositionPatient, 3)
        if orientation is None or position is None:
            return None
        row_direction = np.asarray(orientation[:3], dtype=float)
        column_direction = np.asarray(orientation[3:], dtype=float)
        row_norm = float(np.linalg.norm(row_direction))
        column_norm = float(np.linalg.norm(column_direction))
        # The approved contract (docs/collaboration/active_task.md round 50)
        # requires every slice's full orientation to agree, not just its
        # derived normal -- comparing normals alone would accept a 90-degree
        # in-plane rotation between slices, since that preserves the normal
        # (round 52, finding 3). Also reject direction cosines that aren't
        # unit-length or mutually orthogonal, which a bare cross-product
        # degeneracy check (`slice_normal`) doesn't catch either.
        if (
            abs(row_norm - 1.0) > unit_norm_tolerance
            or abs(column_norm - 1.0) > unit_norm_tolerance
        ):
            return None
        # Normalize before any angle-based (dot-product) comparison: a raw
        # dot product is only a true cosine similarity for exactly unit
        # vectors, and this project deliberately accepts some unit-norm
        # slack above -- comparing un-normalized vectors against a cosine-
        # similarity threshold produces an asymmetric false rejection
        # entirely within that allowed slack (round 55, finding 2).
        unit_row = row_direction / row_norm
        unit_column = column_direction / column_norm
        if abs(float(np.dot(unit_row, unit_column))) > orthogonality_tolerance:
            return None
        row_directions.append(unit_row)
        column_directions.append(unit_column)
        positions_raw.append(position)

    reference_row, reference_column = row_directions[0], column_directions[0]
    for row_direction, column_direction in zip(row_directions, column_directions, strict=True):
        if (
            float(np.dot(row_direction, reference_row)) < orientation_tolerance
            or float(np.dot(column_direction, reference_column)) < orientation_tolerance
        ):
            return None

    try:
        reference_normal = slice_normal(np.concatenate([reference_row, reference_column]))
    except ValueError:
        return None

    positions = [slice_position(position, reference_normal) for position in positions_raw]
    sorted_positions = sorted(positions)
    if any(
        (later - earlier) < position_tolerance_mm for earlier, later in pairwise(sorted_positions)
    ):
        return None

    rank = np.argsort(positions)
    return [dcm_paths[i] for i in rank]


def _validated_instance_number_order(
    dcm_paths: Sequence[Path], headers: Sequence[pydicom.Dataset]
) -> list[Path] | None:
    instance_numbers: list[int] = []
    for dataset in headers:
        if "InstanceNumber" not in dataset:
            return None
        try:
            instance_numbers.append(int(dataset.InstanceNumber))
        except (TypeError, ValueError):
            return None
    if len(set(instance_numbers)) != len(instance_numbers):
        return None
    order = sorted(range(len(headers)), key=lambda i: instance_numbers[i])
    return [dcm_paths[i] for i in order]


def _validate_and_order(
    dcm_paths: Sequence[Path],
    headers: Sequence[pydicom.Dataset],
    orientation_tolerance: float,
    position_tolerance_mm: float,
    unit_norm_tolerance: float,
    orthogonality_tolerance: float,
) -> OrderingValidation:
    geometry_order = _validated_geometry_order(
        dcm_paths,
        headers,
        orientation_tolerance,
        position_tolerance_mm,
        unit_norm_tolerance,
        orthogonality_tolerance,
    )
    if geometry_order is not None:
        return OrderingValidation(
            usable=True, method="geometry", ordered_paths=tuple(geometry_order)
        )

    instance_order = _validated_instance_number_order(dcm_paths, headers)
    if instance_order is not None:
        return OrderingValidation(
            usable=True, method="instance_number", ordered_paths=tuple(instance_order)
        )

    return OrderingValidation(usable=False, method=None, ordered_paths=None)


def _require_tolerance_in_range(
    name: str,
    value: float,
    low: float,
    high: float,
    low_inclusive: bool = True,
    high_inclusive: bool = True,
) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")
    below = value < low if low_inclusive else value <= low
    above = value > high if high_inclusive else value >= high
    if below or above:
        low_bracket = "[" if low_inclusive else "("
        high_bracket = "]" if high_inclusive else ")"
        raise ValueError(f"{name} must be in {low_bracket}{low}, {high}{high_bracket}, got {value}")


def validate_and_order_series(
    series_dir: Path,
    orientation_tolerance: float = _ORIENTATION_TOLERANCE_DEFAULT,
    position_tolerance_mm: float = _POSITION_TOLERANCE_MM_DEFAULT,
    unit_norm_tolerance: float = _UNIT_NORM_TOLERANCE_DEFAULT,
    orthogonality_tolerance: float = _ORTHOGONALITY_TOLERANCE_DEFAULT,
) -> OrderingValidation:
    """Validate whether `series_dir`'s slices can be reliably, anatomically ordered.

    Tries true DICOM geometry first: every slice must have finite, parseable
    `ImagePositionPatient`/`ImageOrientationPatient`; unit-length row/column
    direction cosines (within `unit_norm_tolerance`); row and column
    direction cosines mutually orthogonal (within `orthogonality_tolerance`);
    every slice's row *and* column direction cosines individually consistent
    with the first slice's (cosine similarity >= `orientation_tolerance` for
    both -- comparing only the derived normal would accept a 90-degree
    in-plane rotation between slices, since that leaves the normal
    unchanged); and projected positions that are pairwise distinguishable
    (>= `position_tolerance_mm` apart). Falls back to `InstanceNumber` order
    only if every slice has one, parseable as an integer, with no
    duplicates. If neither route validates, the series is reported unusable
    rather than silently falling back to filename order -- an ordering this
    project never labels anatomical without validation
    (`docs/collaboration/active_task.md` rounds 45, 49, and 52).

    Args:
        series_dir: Directory containing one series' `.dcm` slice files.
        orientation_tolerance: Minimum cosine similarity each slice's row
            and column direction cosines must have with the first slice's.
            Must be in [0.0, 1.0].
        position_tolerance_mm: Minimum spacing required between any two
            slices' projected positions. Must be in (0.0, 1000.0].
        unit_norm_tolerance: Maximum allowed deviation of a direction-cosine
            vector's norm from 1.0. Must be in [0.0, 1.0).
        orthogonality_tolerance: Maximum allowed |dot product| between a
            slice's (normalized) row and column direction cosines. Must be
            in [0.0, 1.0).

    Returns:
        The computed `OrderingValidation`. An unreadable or malformed
        `.dcm` file counts as unusable (`usable=False`), the same as failed
        geometry/`InstanceNumber` validation -- a candidate this project
        can't read is a candidate it can't trust, not a reason to crash the
        caller.

    Raises:
        FileNotFoundError: If `series_dir` contains no `.dcm` files.
        ValueError: If any tolerance argument is out of its valid range.
    """
    # Bounds are deliberately tighter than "any non-negative float": an
    # infinite or requirement-defeating value (e.g. a unit-norm/orthogonality
    # tolerance >= 1.0 accepts a zero/degenerate vector; a zero position
    # tolerance admits exact duplicate positions via the strict "<" spacing
    # check; a negative orientation tolerance can admit oppositely-directed
    # axes) would silently disable the very check it configures rather than
    # raising (round 55, finding 3).
    _require_tolerance_in_range("orientation_tolerance", orientation_tolerance, 0.0, 1.0)
    _require_tolerance_in_range(
        "position_tolerance_mm",
        position_tolerance_mm,
        0.0,
        1000.0,
        low_inclusive=False,
    )
    _require_tolerance_in_range(
        "unit_norm_tolerance", unit_norm_tolerance, 0.0, 1.0, high_inclusive=False
    )
    _require_tolerance_in_range(
        "orthogonality_tolerance", orthogonality_tolerance, 0.0, 1.0, high_inclusive=False
    )

    dcm_paths = sorted(series_dir.glob("*.dcm"))
    if not dcm_paths:
        raise FileNotFoundError(f"No .dcm files found in {series_dir}")
    try:
        headers = [pydicom.dcmread(path, stop_before_pixels=True) for path in dcm_paths]
    except (pydicom.errors.InvalidDicomError, OSError):
        return OrderingValidation(usable=False, method=None, ordered_paths=None)
    return _validate_and_order(
        dcm_paths,
        headers,
        orientation_tolerance,
        position_tolerance_mm,
        unit_norm_tolerance,
        orthogonality_tolerance,
    )


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

    Header tags are read for every slice (cheap, `stop_before_pixels`) under
    the same narrow exception policy `validate_and_order_series` uses --
    malformed or unreadable files don't crash the audit, they're counted in
    `header_read_failures` and excluded from the diagnostics computed below.
    Pixel data is fully decoded only for a `central_band_indices` sample, so
    decode reliability is measured without paying full-series decode cost.
    The sample is drawn from the series' validated anatomical order when
    `validate_and_order_series` succeeds; when it doesn't, decode-
    reliability sampling (which doesn't depend on slice order) falls back
    to filename order for that narrow purpose only -- see `ordering_usable`/
    `ordering_method` for whether the order actually validated.

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

    headers: list[pydicom.Dataset] = []
    header_read_failures = 0
    for path in dcm_paths:
        try:
            headers.append(pydicom.dcmread(path, stop_before_pixels=True))
        except (pydicom.errors.InvalidDicomError, OSError):
            header_read_failures += 1
    slice_count = len(dcm_paths)

    if not headers:
        # Every file was unreadable: nothing to compute header-derived
        # diagnostics from. Decode sampling below still legitimately runs
        # against the original files and will itself report the failures.
        has_full_geometry_tags = False
        agreement: float | None = None
        ordering_validation = OrderingValidation(usable=False, method=None, ordered_paths=None)
        ordered_paths = dcm_paths
        laterality_tag_present_fraction = 0.0
        laterality_tag = None
        laterality_tag_consistent = True
        has_cross_tag_conflict = False
        geometry_laterality = None
        pixel_spacing = None
    else:
        first = headers[0]

        has_full_geometry_tags = all(
            "ImagePositionPatient" in ds and "ImageOrientationPatient" in ds for ds in headers
        )

        # `has_full_geometry_tags` only checks tag *presence* (matching this
        # field's own contract), not validity -- a present-but-degenerate
        # orientation or a missing InstanceNumber on some slice must not
        # crash the whole audit, only leave this one diagnostic unresolved.
        agreement = None
        if has_full_geometry_tags:
            try:
                normal = slice_normal(first.ImageOrientationPatient)
                positions = [slice_position(ds.ImagePositionPatient, normal) for ds in headers]
                instance_numbers = [int(ds.InstanceNumber) for ds in headers]
                agreement = order_agreement(instance_numbers, positions)
            except (ValueError, TypeError, AttributeError):
                agreement = None

        if header_read_failures > 0:
            # Can't validate a complete anatomical order when at least one
            # member's data is missing entirely (round 55, finding 1).
            ordering_validation = OrderingValidation(usable=False, method=None, ordered_paths=None)
        else:
            ordering_validation = _validate_and_order(
                dcm_paths,
                headers,
                _ORIENTATION_TOLERANCE_DEFAULT,
                _POSITION_TOLERANCE_MM_DEFAULT,
                _UNIT_NORM_TOLERANCE_DEFAULT,
                _ORTHOGONALITY_TOLERANCE_DEFAULT,
            )
        # Decode-reliability sampling doesn't need a validated order (decode
        # success/failure doesn't depend on slice order) -- fall back to
        # filename order only for that narrow purpose when validation fails,
        # never presented elsewhere as anatomical.
        ordered_paths = (
            ordering_validation.ordered_paths
            if ordering_validation.usable and ordering_validation.ordered_paths is not None
            else dcm_paths
        )

        slice_laterality_tags = [_slice_laterality_tag(ds) for ds in headers]
        has_cross_tag_conflict = any(_slice_laterality_cross_tag_conflict(ds) for ds in headers)
        present_tags = [tag for tag in slice_laterality_tags if tag is not None]
        laterality_tag_present_fraction = len(present_tags) / len(headers)
        distinct_tags = set(present_tags)
        laterality_tag_consistent = len(distinct_tags) <= 1
        laterality_tag = present_tags[0] if laterality_tag_consistent and present_tags else None

        geometry_laterality = None
        if has_full_geometry_tags and "PixelSpacing" in first:
            try:
                geometry_laterality = laterality_from_geometry(
                    first.ImagePositionPatient,
                    first.ImageOrientationPatient,
                    int(first.Rows),
                    int(first.Columns),
                    first.PixelSpacing,
                )
            except (ValueError, TypeError, AttributeError):
                geometry_laterality = None

        pixel_spacing = (
            (float(first.PixelSpacing[0]), float(first.PixelSpacing[1]))
            if "PixelSpacing" in first
            else None
        )

    laterality_conflict = bool(
        laterality_tag and geometry_laterality and laterality_tag != geometry_laterality
    )
    laterality_filled_by_geometry = bool(laterality_tag is None and geometry_laterality is not None)
    laterality_resolved_call = laterality_tag if laterality_tag is not None else geometry_laterality

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
        header_read_failures=header_read_failures,
        has_full_geometry_tags=has_full_geometry_tags,
        order_agreement=agreement,
        ordering_usable=ordering_validation.usable,
        ordering_method=ordering_validation.method,
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
