"""Central-band slice sampling with the decode/retry fallback for Phase 3B.

Implements section 4 of the Phase 3B specification
(`docs/superpowers/specs/2026-08-26-phase-3b-image-baseline-design.md`):
sample five deterministic central-band slices from a series' validated
anatomical order, require at least three to decode, mean only those that did,
and otherwise retry the next ranked same-plane candidate before declaring the
plane absent.

"Decode failure" here deliberately covers three distinct causes, because all
three leave the pipeline without a usable slice: an unreadable file, pixel
data that cannot be decoded, and a slice whose intensity cannot be normalized
(section 6 step 4's insufficient-variation gate). Counting them together is
what makes the minimum-of-three rule mean "three slices we can actually feed
the encoder".

**Stacks of exactly 1, 2, or 4 slices can never satisfy the minimum.**
`central_band_indices` collapses duplicate rounded positions, so those depths
yield fewer than three indices however perfectly every one decodes. The set is
**not** monotonic: a 3-slice stack yields `[0, 1, 2]` and can meet the
minimum, while a 4-slice stack yields only `[1, 2]` and cannot. (Round 83
recorded this as "four or fewer", which is wrong; corrected in round 87.)
Unreachable on observed data -- the shortest series in the corpus has 11
slices -- but a real property of the contract, pinned by test.

Every counter reported here is aggregate: counts only, never a path, study, or
series identifier.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pydicom

from knee_mri.intensity import InsufficientVariationError, normalize_slice
from knee_mri.series_audit import central_band_indices

# Frozen by section 4.
SLICE_SAMPLE_SIZE = 5
MINIMUM_DECODED_SLICES = 3


@dataclass(frozen=True)
class SampledPlane:
    """Normalized slices from one candidate series, plus decode counts.

    Attributes:
        images: The successfully decoded and normalized slices, in
            anatomical order. When `usable`, at least
            `MINIMUM_DECODED_SLICES` and at most the requested sample size.
        attempted: How many slices were sampled and tried.
        decoded: How many of those yielded a usable normalized image.
        usable: Whether `decoded` met the minimum.
    """

    images: tuple[np.ndarray, ...]
    attempted: int
    decoded: int
    usable: bool


@dataclass(frozen=True)
class PlaneSampleOutcome:
    """The result of trying ranked candidates for one anatomical plane."""

    sample: SampledPlane | None
    candidates_tried: int
    absent: bool

    def counters(self) -> dict[str, int | bool]:
        """Aggregate-only telemetry for this plane. No identifiers."""
        return {
            "attempted": self.sample.attempted if self.sample else 0,
            "decoded": self.sample.decoded if self.sample else 0,
            "candidates_tried": self.candidates_tried,
            "absent": self.absent,
        }


def _decode_and_normalize(path: Path) -> np.ndarray | None:
    """Read one slice and normalize it, or return `None` on any failure.

    The exception types are listed explicitly rather than caught broadly:
    a blanket handler here would hide genuine programming errors behind a
    silently-dropped slice, and dropping slices is exactly what the
    minimum-of-three rule is counting.
    """
    try:
        dataset = pydicom.dcmread(path)
        stored = dataset.pixel_array
    except (pydicom.errors.InvalidDicomError, OSError, AttributeError, ValueError, TypeError):
        return None

    try:
        return normalize_slice(
            stored,
            rescale_slope=getattr(dataset, "RescaleSlope", None),
            rescale_intercept=getattr(dataset, "RescaleIntercept", None),
            photometric_interpretation=getattr(
                dataset, "PhotometricInterpretation", "MONOCHROME2"
            ),
            pixel_padding_value=getattr(dataset, "PixelPaddingValue", None),
            pixel_padding_range_limit=getattr(dataset, "PixelPaddingRangeLimit", None),
        )
    except (InsufficientVariationError, ValueError, TypeError):
        return None


def sample_plane(
    ordered_paths: Sequence[Path], sample_size: int = SLICE_SAMPLE_SIZE
) -> SampledPlane:
    """Sample and decode the central band of one validated series.

    Args:
        ordered_paths: The series' slice paths in validated anatomical order
            (from `validate_and_order_series`). Filename order must never be
            passed here as though it were anatomical.
        sample_size: How many central-band slices to attempt. Defaults to the
            frozen `SLICE_SAMPLE_SIZE`; a caller evaluating a pre-registered
            sampling-density experiment may pass a larger value. The band
            itself is unchanged, so a larger value samples the same extent
            more densely rather than reaching further toward the periphery.

    Returns:
        The decoded slices and their counts. `usable` is `False` when fewer
        than `MINIMUM_DECODED_SLICES` decoded, which the caller treats as a
        failed candidate.
    """
    if not ordered_paths:
        return SampledPlane(images=(), attempted=0, decoded=0, usable=False)

    indices = central_band_indices(len(ordered_paths), sample_size)
    images = [
        image
        for image in (_decode_and_normalize(ordered_paths[index]) for index in indices)
        if image is not None
    ]
    return SampledPlane(
        images=tuple(images),
        attempted=len(indices),
        decoded=len(images),
        usable=len(images) >= MINIMUM_DECODED_SLICES,
    )


def select_plane_sample(
    ranked_candidates: Sequence[Sequence[Path]],
    sample_size: int = SLICE_SAMPLE_SIZE,
) -> PlaneSampleOutcome:
    """Try ranked same-plane candidates until one yields a usable sample.

    Args:
        ranked_candidates: Each candidate's slice paths in validated
            anatomical order, best-ranked first.
        sample_size: Forwarded to `sample_plane`. The minimum-decoded rule is
            deliberately NOT scaled with it, so plane-absence behaviour stays
            identical and a density experiment changes one variable only.

    Returns:
        The winning sample and how many candidates were tried, or
        `absent=True` once every candidate has failed. The plane is absent
        only after exhaustion -- never on the first failure.
    """
    tried = 0
    for candidate in ranked_candidates:
        tried += 1
        sample = sample_plane(candidate, sample_size=sample_size)
        if sample.usable:
            return PlaneSampleOutcome(sample=sample, candidates_tried=tried, absent=False)
    return PlaneSampleOutcome(sample=None, candidates_tried=tried, absent=True)
