"""DICOM-to-DINOv2 intensity normalization for Phase 3B.

Implements section 6 of the Phase 3B specification
(`docs/superpowers/specs/2026-08-26-phase-3b-image-baseline-design.md`),
applied per slice in this exact order:

1. Build the pixel-padding mask **in the stored-value domain, before** the
   modality transform, using the inclusive interval when both
   `PixelPaddingValue` and `PixelPaddingRangeLimit` are present.
2. Apply the modality transform (`RescaleSlope` / `RescaleIntercept`).
3. Invert for `MONOCHROME1` polarity.
4. Reject a slice with insufficient usable variation.
5. Clip to per-slice p1/p99 and rescale to `[0, 1]`; excluded padding maps
   to `0`.
6. Replicate to three channels.
7. Standardize with the attached processor's own `image_mean` / `image_std`.

Step 1's ordering is not stylistic. With `slope=2, intercept=-1024`, a mask
built *after* the transform using the same literal padding value matches
**none** of the padding, which then enters the percentile estimate and skews
the entire slice (measured in round 82).

Step 3's reference point is deliberately unspecified by the contract, and
cannot matter: step 5's per-slice percentile rescale is affine and
data-range-relative, so any strictly decreasing affine inversion cancels
exactly. **That equivalence is a consequence of step 5 being per-slice.** If
the bounds ever became per-series pooled (round 61's rejected option 2) or
window/VOI-driven, the inversion reference would suddenly matter and this
module would need revisiting.

Step 7 has no fallback by design. Missing or malformed processor metadata is
a hard error; substituting remembered ImageNet constants is exactly the
silent-wrongness this contract exists to prevent, and a test asserts no such
literal appears in this file.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch


class InsufficientVariationError(ValueError):
    """A slice carries too little usable signal to normalize.

    Section 6 step 4: the caller treats this as a decode failure, subject to
    section 4's minimum-three-of-five rule.
    """


def padding_mask(
    stored: np.ndarray,
    padding_value: float | None = None,
    padding_range_limit: float | None = None,
) -> np.ndarray:
    """Section 6 step 1, evaluated on raw stored values.

    Args:
        stored: The slice's stored pixel values, before any rescale.
        padding_value: `PixelPaddingValue`, if present.
        padding_range_limit: `PixelPaddingRangeLimit`, if present. When given,
            the padding is the **inclusive interval** it forms with
            `padding_value`; the two bounds may arrive in either order.

    Returns:
        A boolean mask, all-`False` when no padding tag is present.
    """
    if padding_value is None:
        return np.zeros(stored.shape, dtype=bool)
    if padding_range_limit is None:
        return np.asarray(stored == padding_value)
    low, high = sorted((float(padding_value), float(padding_range_limit)))
    return np.asarray((stored >= low) & (stored <= high))


def _invert(values: np.ndarray, reference: str) -> np.ndarray:
    """One of several equivalent `MONOCHROME1` inversions (see module docs)."""
    if reference == "negate":
        return -values
    if reference == "max_minus":
        finite = values[np.isfinite(values)]
        return (finite.max() if finite.size else 0.0) - values
    if reference == "bitdepth":
        return (2**12 - 1) - values
    raise ValueError(f"unknown inversion reference: {reference}")


def _percentile_rescale(values: np.ndarray, excluded: np.ndarray) -> np.ndarray:
    """Section 6 steps 4-5: variation gate, then clip and rescale to `[0, 1]`."""
    usable = (~excluded) & np.isfinite(values)
    if not usable.any():
        raise InsufficientVariationError("slice has no finite, non-padding pixels")

    low, high = np.percentile(values[usable], [1, 99])
    # The explicit criterion for section 6 step 4's "insufficient variation".
    # It correctly rejects a constant slice, an all-padding slice, and a
    # sparse-bright slice whose 1st and 99th percentiles coincide.
    if not (math.isfinite(low) and math.isfinite(high)) or high <= low:
        raise InsufficientVariationError(f"p1 ({low}) is not below p99 ({high})")

    rescaled = (np.clip(values, low, high) - low) / (high - low)
    rescaled[~usable] = 0.0
    return rescaled.astype(np.float32)


def normalize_slice(
    stored: np.ndarray,
    *,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
    photometric_interpretation: str = "MONOCHROME2",
    pixel_padding_value: float | None = None,
    pixel_padding_range_limit: float | None = None,
) -> np.ndarray:
    """Run section 6 steps 1-5 on one slice's stored pixel values.

    Args:
        stored: Stored pixel values, before any rescale.
        rescale_slope: `RescaleSlope`, if present.
        rescale_intercept: `RescaleIntercept`, if present.
        photometric_interpretation: `PhotometricInterpretation`; only
            `MONOCHROME1` triggers inversion.
        pixel_padding_value: `PixelPaddingValue`, if present.
        pixel_padding_range_limit: `PixelPaddingRangeLimit`, if present.

    Returns:
        A `float32` array in `[0, 1]`, with padding at `0`.

    Raises:
        InsufficientVariationError: If the usable pixels cannot support a
            meaningful clip. The caller treats this as a decode failure.
    """
    excluded = padding_mask(stored, pixel_padding_value, pixel_padding_range_limit)

    values = np.asarray(stored, dtype=np.float64)
    if rescale_slope is not None or rescale_intercept is not None:
        values = values * float(rescale_slope or 1.0) + float(rescale_intercept or 0.0)

    if str(photometric_interpretation).strip().upper() == "MONOCHROME1":
        values = _invert(values, "negate")

    return _percentile_rescale(values, excluded)


def to_three_channel(image: np.ndarray | torch.Tensor) -> torch.Tensor:
    """Section 6 step 6: replicate one grayscale plane to three channels."""
    tensor = (
        image if isinstance(image, torch.Tensor) else torch.from_numpy(np.asarray(image))
    )
    return tensor.to(torch.float32).expand(3, *tensor.shape).clone()


def load_processor_statistics(
    config_path: str | Path,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Read `image_mean` / `image_std` from the attached processor config.

    Args:
        config_path: Path to the model's own `preprocessor_config.json`.

    Returns:
        The `(mean, std)` channel statistics.

    Raises:
        ValueError: If the file is missing, unparseable, or does not carry
            three usable values for each statistic. There is deliberately no
            fallback: section 6 step 7 forbids substituting remembered
            constants, because a wrong-but-plausible normalization is exactly
            the kind of silent error this pipeline cannot detect downstream.
    """
    path = Path(config_path)
    try:
        config = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"image processor config is unreadable: {path}") from error

    statistics: list[tuple[float, float, float]] = []
    for key in ("image_mean", "image_std"):
        values = config.get(key)
        if not isinstance(values, (list, tuple)) or len(values) != 3:
            raise ValueError(f"image processor config lacks a 3-value '{key}'")
        try:
            numbers = tuple(float(value) for value in values)
        except (TypeError, ValueError) as error:
            raise ValueError(f"image processor config has non-numeric '{key}'") from error
        if not all(math.isfinite(number) for number in numbers):
            raise ValueError(f"image processor config has non-finite '{key}'")
        if key == "image_std" and any(number <= 0.0 for number in numbers):
            raise ValueError("image processor config has a non-positive 'image_std'")
        statistics.append(numbers)

    return statistics[0], statistics[1]


def standardize(
    three_channel: torch.Tensor,
    mean: Sequence[float],
    std: Sequence[float],
) -> torch.Tensor:
    """Section 6 step 7: apply the processor's channel statistics.

    Note that padding introduced by section 5's letterbox is `0` in the
    `[0, 1]` domain and therefore lands at `-mean / std` here -- the extreme
    low end of the range, not a neutral value. See `knee_mri.framing`.
    """
    if three_channel.shape[0] != 3:
        raise ValueError("expected a three-channel image")
    mean_tensor = torch.tensor(tuple(mean), dtype=torch.float32).reshape(3, 1, 1)
    std_tensor = torch.tensor(tuple(std), dtype=torch.float32).reshape(3, 1, 1)
    return (three_channel.to(torch.float32) - mean_tensor) / std_tensor
