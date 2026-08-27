"""Physical-aspect letterboxing for Phase 3B image inputs.

Implements section 5 of the Phase 3B specification
(`docs/superpowers/specs/2026-08-26-phase-3b-image-baseline-design.md`).

The slice is resized to its true physical aspect ratio -- derived from
`Rows * row_spacing` by `Columns * column_spacing` -- then padded to a square
`336 x 336`. Nothing is cropped: the alternatives considered and rejected in
round 61 were an unmeasured 90% centre crop (no evidence the discarded margin
is background) and a fixed-millimetre crop (needs an anatomical extent this
project has never measured).

**Padding is not a neutral value, and it is not a small share of the input.**
For ordinary anisotropic acquisitions padding occupies roughly 36% of the
`336 x 336` result (a 320x256 slice at 0.5/0.4 mm spacing renders as 336x215)
and up to 50% for a 512x256 slice at isotropic spacing. Section 5 pads with
`0` in the locally normalized `[0, 1]` domain, and section 6 then applies the
attached processor's channel standardization, so that `0` becomes roughly
`-2.12`, `-2.04`, `-1.80` across the three channels -- the extreme low end of
the real-pixel range, which reaches `+2.25`. Measured against the vendored
processor config, not assumed. This is the approved contract and is
deliberately not changed here; it is documented so the consequence is visible
at the point of use (rounds 81 and 86).

Because padding and genuinely dark tissue both end up at `0`, they cannot be
told apart by pixel value. `LetterboxedSlice` therefore reports the padding
geometry explicitly, so any later step that needs to exclude padding can do
so structurally rather than by thresholding.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import torch
import torch.nn.functional as F

# The frozen DINOv2 input edge. Evenly divisible by the encoder's 14-pixel
# patch size (24 x 24 = 576 patches) and the resolution already exercised by
# the preflight GPU timing probe.
TARGET_SIZE = 336


@dataclass(frozen=True)
class LetterboxedSlice:
    """A `TARGET_SIZE` square slice plus the geometry used to build it.

    Attributes:
        image: The `(TARGET_SIZE, TARGET_SIZE)` result.
        content_height: Rows occupied by resized image data.
        content_width: Columns occupied by resized image data.
        pad_top: Padding rows above the content.
        pad_bottom: Padding rows below the content.
        pad_left: Padding columns left of the content.
        pad_right: Padding columns right of the content.
    """

    image: torch.Tensor
    content_height: int
    content_width: int
    pad_top: int
    pad_bottom: int
    pad_left: int
    pad_right: int


def _validated_spacing(pixel_spacing: Sequence[float]) -> tuple[float, float]:
    values = tuple(pixel_spacing)
    if len(values) != 2:
        raise ValueError("pixel_spacing must have exactly two values")
    try:
        row_spacing, column_spacing = (float(value) for value in values)
    except (TypeError, ValueError) as error:
        raise ValueError("pixel_spacing must be numeric") from error
    if not all(math.isfinite(value) for value in (row_spacing, column_spacing)):
        raise ValueError("pixel_spacing must be finite")
    if row_spacing <= 0.0 or column_spacing <= 0.0:
        raise ValueError("pixel_spacing must be strictly positive")
    return row_spacing, column_spacing


def content_shape(
    rows: int, columns: int, pixel_spacing: Sequence[float]
) -> tuple[int, int]:
    """Resized `(height, width)` before padding, per section 5 steps 1-2.

    The longer physical side maps to `TARGET_SIZE`; the shorter is scaled by
    the physical aspect ratio, rounded half-up (`floor(value + 0.5)`), and
    clamped to `[1, TARGET_SIZE]`. The clamp only ever engages at aspect
    ratios far beyond anything this corpus contains; it exists so a
    pathological ratio degrades to a one-pixel strip rather than a zero-sized
    tensor.
    """
    row_spacing, column_spacing = _validated_spacing(pixel_spacing)
    physical_height = rows * row_spacing
    physical_width = columns * column_spacing

    if physical_height >= physical_width:
        height = TARGET_SIZE
        width = math.floor((TARGET_SIZE * physical_width / physical_height) + 0.5)
        width = min(max(width, 1), TARGET_SIZE)
    else:
        width = TARGET_SIZE
        height = math.floor((TARGET_SIZE * physical_height / physical_width) + 0.5)
        height = min(max(height, 1), TARGET_SIZE)
    return height, width


def letterbox_slice(
    image: torch.Tensor, pixel_spacing: Sequence[float]
) -> LetterboxedSlice:
    """Resize to physical aspect ratio and pad to a `TARGET_SIZE` square.

    Args:
        image: A two-dimensional float tensor, expected in the locally
            normalized `[0, 1]` domain (section 6 steps 1-6). This function
            does not itself normalize.
        pixel_spacing: DICOM `PixelSpacing` as `(row_spacing,
            column_spacing)` in millimetres.

    Returns:
        The padded slice and its content/padding geometry.

    Raises:
        ValueError: If `image` is not two-dimensional, or `pixel_spacing` is
            not two finite strictly-positive values. Series-level validation
            rejects such spacing upstream; this guard exists so a direct
            caller cannot silently produce a wrongly-scaled slice.
    """
    if image.ndim != 2:
        raise ValueError("image must be two-dimensional (rows, columns)")

    rows, columns = int(image.shape[0]), int(image.shape[1])
    height, width = content_shape(rows, columns, pixel_spacing)

    # Antialiasing matters when downsampling a large matrix into 336: without
    # it, bilinear sampling aliases fine structure. Confirmed available for
    # `mode="bilinear"` on the pinned torch.
    resized = F.interpolate(
        image[None, None].to(torch.float32),
        size=(height, width),
        mode="bilinear",
        align_corners=False,
        antialias=True,
    )[0, 0]

    pad_height = TARGET_SIZE - height
    pad_width = TARGET_SIZE - width
    # Split evenly; the extra pixel of an odd remainder goes bottom/right.
    pad_top = pad_height // 2
    pad_bottom = pad_height - pad_top
    pad_left = pad_width // 2
    pad_right = pad_width - pad_left

    padded = F.pad(resized, (pad_left, pad_right, pad_top, pad_bottom), value=0.0)

    return LetterboxedSlice(
        image=padded,
        content_height=height,
        content_width=width,
        pad_top=pad_top,
        pad_bottom=pad_bottom,
        pad_left=pad_left,
        pad_right=pad_right,
    )
