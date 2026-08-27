from __future__ import annotations

import pytest
import torch

from knee_mri.framing import TARGET_SIZE, letterbox_slice


def _image(rows: int, columns: int) -> torch.Tensor:
    return torch.rand(rows, columns, dtype=torch.float32)


@pytest.mark.parametrize(
    ("rows", "columns", "spacing"),
    [
        (256, 256, (0.5, 0.5)),  # square isotropic
        (320, 256, (0.5, 0.4)),  # portrait, anisotropic spacing
        (256, 320, (0.4, 0.5)),  # landscape
        (512, 512, (0.137, 0.137)),  # smallest observed spacing
        (256, 256, (1.172, 1.172)),  # largest observed spacing
        (400, 200, (0.25, 0.5)),  # equal physical sides via anisotropy
        (800, 2, (1.0, 1.0)),  # extreme portrait
        (2, 800, (1.0, 1.0)),  # extreme landscape
    ],
)
def test_letterbox_always_returns_the_target_square(rows, columns, spacing):
    result = letterbox_slice(_image(rows, columns), spacing)

    assert result.image.shape == (TARGET_SIZE, TARGET_SIZE)


def test_longer_physical_side_maps_to_target_and_shorter_rounds_half_up():
    # 320 x 0.5 = 160.0 mm tall, 256 x 0.4 = 102.4 mm wide -> portrait.
    # 336 * 102.4 / 160 = 215.04 -> floor(215.04 + 0.5) = 215.
    result = letterbox_slice(_image(320, 256), (0.5, 0.4))

    assert result.content_height == TARGET_SIZE
    assert result.content_width == 215


def test_short_side_is_clamped_to_at_least_one_pixel():
    # 336 * 1 / 1000 = 0.336, which would round to 0 without the clamp.
    result = letterbox_slice(_image(1000, 1), (1.0, 1.0))

    assert result.content_width == 1
    assert result.image.shape == (TARGET_SIZE, TARGET_SIZE)


@pytest.mark.parametrize(
    ("rows", "columns", "spacing"),
    [(320, 256, (0.5, 0.4)), (256, 320, (0.4, 0.5)), (512, 256, (0.5, 0.5))],
)
def test_padding_splits_evenly_with_the_extra_pixel_bottom_or_right(rows, columns, spacing):
    result = letterbox_slice(_image(rows, columns), spacing)

    assert result.pad_bottom - result.pad_top in (0, 1)
    assert result.pad_right - result.pad_left in (0, 1)
    assert result.pad_top + result.content_height + result.pad_bottom == TARGET_SIZE
    assert result.pad_left + result.content_width + result.pad_right == TARGET_SIZE


def test_letterbox_never_crops_anatomy():
    """Letterboxing scales the whole slice and pads; it must not crop.

    Markers at all four corners must survive inside the content region.
    """
    image = torch.zeros(320, 256, dtype=torch.float32)
    image[0, 0] = image[0, -1] = image[-1, 0] = image[-1, -1] = 1.0

    result = letterbox_slice(image, (0.5, 0.4))
    content = result.image[
        result.pad_top : result.pad_top + result.content_height,
        result.pad_left : result.pad_left + result.content_width,
    ]

    assert content[0, 0] > 0
    assert content[0, -1] > 0
    assert content[-1, 0] > 0
    assert content[-1, -1] > 0


def test_padding_is_zero_in_the_normalized_domain():
    result = letterbox_slice(torch.ones(512, 256, dtype=torch.float32), (0.5, 0.5))

    assert result.pad_left > 0 or result.pad_top > 0
    if result.pad_left > 0:
        assert torch.all(result.image[:, : result.pad_left] == 0.0)
    if result.pad_top > 0:
        assert torch.all(result.image[: result.pad_top, :] == 0.0)


def test_letterbox_preserves_physical_aspect_ratio_closely():
    rows, columns, (row_spacing, column_spacing) = 320, 256, (0.5, 0.4)
    result = letterbox_slice(_image(rows, columns), (row_spacing, column_spacing))

    physical = (rows * row_spacing) / (columns * column_spacing)
    rendered = result.content_height / result.content_width

    assert rendered == pytest.approx(physical, rel=0.01)


@pytest.mark.parametrize("spacing", [(0.0, 0.5), (-0.5, 0.5), (0.5, float("nan")), (0.5,)])
def test_letterbox_rejects_unusable_spacing(spacing):
    """Section 5's precondition is enforced upstream in the series validator,
    but this function must not silently produce garbage if handed bad
    spacing directly.
    """
    with pytest.raises(ValueError, match="pixel_spacing"):
        letterbox_slice(_image(64, 64), spacing)


def test_letterbox_rejects_non_two_dimensional_input():
    with pytest.raises(ValueError, match="two-dimensional"):
        letterbox_slice(torch.rand(3, 64, 64), (0.5, 0.5))
