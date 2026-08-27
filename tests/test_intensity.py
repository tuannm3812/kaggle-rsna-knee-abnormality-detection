from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from knee_mri import intensity
from knee_mri.intensity import (
    InsufficientVariationError,
    load_processor_statistics,
    normalize_slice,
    padding_mask,
    standardize,
    to_three_channel,
)

VENDORED_CONFIG = Path("vendor/dinov2-small-preprocessor_config.json")


# -- step 1: padding mask, built in the STORED-value domain --


def test_padding_mask_matches_a_single_padding_value():
    stored = np.array([[-2000, -2000, 10], [20, 30, 40]])

    assert padding_mask(stored, padding_value=-2000).sum() == 2


def test_padding_mask_uses_the_inclusive_interval_when_a_range_limit_is_given():
    stored = np.array([[-2000, -1800, -1500], [10, 20, 30]])

    mask = padding_mask(stored, padding_value=-2000, padding_range_limit=-1500)

    assert mask.sum() == 3
    assert mask[0].all()


def test_padding_mask_is_order_insensitive_for_the_interval_bounds():
    stored = np.array([[-2000, -1800, -1500], [10, 20, 30]])

    forwards = padding_mask(stored, padding_value=-2000, padding_range_limit=-1500)
    backwards = padding_mask(stored, padding_value=-1500, padding_range_limit=-2000)

    assert np.array_equal(forwards, backwards)


def test_padding_mask_is_empty_without_padding_tags():
    assert padding_mask(np.array([[1, 2], [3, 4]])).sum() == 0


def test_padding_must_be_masked_before_the_modality_transform():
    """Round 64's clarification, and round 82 measured why it is load-bearing.

    With slope=2 / intercept=-1024 a mask built after the transform, using the
    same literal padding value, catches none of the padding -- which then
    enters the percentile estimate and skews the whole slice.
    """
    stored = np.array([[-2000, -2000], [100, 3000]], dtype=np.int64)

    correct = padding_mask(stored, padding_value=-2000)
    transformed = stored * 2.0 - 1024.0
    naive_post_transform = transformed == -2000

    assert correct.sum() == 2
    assert naive_post_transform.sum() == 0


# -- steps 2-5: modality transform, polarity, variation gate, percentiles --


def test_normalize_applies_rescale_slope_and_intercept():
    stored = np.array([[0, 100], [200, 300]], dtype=np.int64)

    without = normalize_slice(stored)
    with_transform = normalize_slice(stored, rescale_slope=2.0, rescale_intercept=-50.0)

    # A positive affine transform is absorbed by the per-slice percentile
    # rescale, so the normalized image is unchanged -- but it must not crash
    # or alter ordering.
    assert np.allclose(without, with_transform)


@pytest.mark.parametrize("invert_reference", ["negate", "max_minus", "bitdepth"])
def test_monochrome1_inversion_reference_is_immaterial(invert_reference):
    """Section 6 step 3 says "invert" without naming a reference point.

    Round 82 proved the choice cannot matter: step 5's per-slice percentile
    rescale is affine and data-range-relative, so any strictly decreasing
    affine inversion cancels. Pinned here because the equivalence would break
    if the bounds ever became per-series pooled or VOI-driven.
    """
    rng = np.random.default_rng(0)
    stored = rng.integers(0, 4096, size=(32, 32)).astype(np.int64)

    reference = normalize_slice(stored, photometric_interpretation="MONOCHROME1")
    alternative = intensity._invert(stored.astype(float), invert_reference)
    alternative = intensity._percentile_rescale(
        alternative, np.zeros(stored.shape, dtype=bool)
    )

    assert np.allclose(reference, alternative)


def test_monochrome1_reverses_brightness_order():
    stored = np.array([[0, 1000], [2000, 4000]], dtype=np.int64)

    normal = normalize_slice(stored, photometric_interpretation="MONOCHROME2")
    inverted = normalize_slice(stored, photometric_interpretation="MONOCHROME1")

    assert normal.argmax() == 3
    assert inverted.argmax() == 0


@pytest.mark.parametrize(
    "stored",
    [
        np.full((8, 8), 500, dtype=np.int64),  # entirely constant
        np.zeros((8, 8), dtype=np.int64),  # constant zero
    ],
)
def test_insufficient_variation_raises(stored):
    """Section 6 step 4 leaves "insufficient" undefined; `p99 <= p1` pins it."""
    with pytest.raises(InsufficientVariationError):
        normalize_slice(stored)


def test_a_slice_that_is_entirely_padding_raises():
    stored = np.full((8, 8), -2000, dtype=np.int64)

    with pytest.raises(InsufficientVariationError):
        normalize_slice(stored, pixel_padding_value=-2000)


def test_a_sparse_bright_slice_raises_because_p1_equals_p99():
    stored = np.zeros((16, 16), dtype=np.int64)
    stored[0, 0] = 4000  # a single bright pixel in 256

    with pytest.raises(InsufficientVariationError):
        normalize_slice(stored)


def test_normalized_output_spans_the_unit_interval():
    rng = np.random.default_rng(1)
    stored = rng.integers(0, 4096, size=(64, 64)).astype(np.int64)

    normalized = normalize_slice(stored)

    assert normalized.min() == pytest.approx(0.0)
    assert normalized.max() == pytest.approx(1.0)
    assert normalized.dtype == np.float32


def test_padding_is_mapped_to_normalized_zero_and_excluded_from_percentiles():
    stored = np.array([[-2000, -2000], [1000, 2000]], dtype=np.int64)

    normalized = normalize_slice(stored, pixel_padding_value=-2000)

    assert normalized[0, 0] == pytest.approx(0.0)
    assert normalized[0, 1] == pytest.approx(0.0)
    # Percentiles came from {1000, 2000} only; had -2000 been included the
    # real tissue would have been crushed into the top of the range.
    assert normalized[1, 0] == pytest.approx(0.0)
    assert normalized[1, 1] == pytest.approx(1.0)


def test_non_finite_pixels_are_excluded_from_percentiles():
    stored = np.array([[np.nan, 1000.0], [2000.0, 3000.0]])

    normalized = normalize_slice(stored)

    assert np.isfinite(normalized).all()


# -- steps 6-7: channel replication and processor standardization --


def test_three_channel_replication_is_exact():
    image = np.linspace(0.0, 1.0, 16, dtype=np.float32).reshape(4, 4)

    replicated = to_three_channel(image)

    assert replicated.shape == (3, 4, 4)
    for channel in range(3):
        assert torch.allclose(replicated[channel], torch.from_numpy(image))


def test_processor_statistics_load_from_the_vendored_config():
    mean, std = load_processor_statistics(VENDORED_CONFIG)

    assert len(mean) == 3
    assert len(std) == 3
    assert all(0.0 < value < 1.0 for value in mean + std)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"image_mean": [0.5, 0.5, 0.5]},
        {"image_mean": [0.5, 0.5], "image_std": [0.5, 0.5, 0.5]},
        {"image_mean": [0.5, 0.5, 0.5], "image_std": [0.0, 0.5, 0.5]},
        {"image_mean": [0.5, 0.5, 0.5], "image_std": "not a list"},
    ],
)
def test_missing_or_malformed_processor_metadata_is_a_hard_error(tmp_path: Path, payload):
    """Section 6 step 7: no remembered-constant fallback, ever."""
    config = tmp_path / "preprocessor_config.json"
    config.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="processor"):
        load_processor_statistics(config)


def test_module_contains_no_hardcoded_imagenet_constants():
    """The failure this guards is silent substitution of remembered values."""
    source = inspect.getsource(intensity)

    for forbidden in ("0.485", "0.456", "0.406", "0.229", "0.224", "0.225"):
        assert forbidden not in source


def test_manual_pipeline_matches_the_attached_image_processor():
    """Section 6's required equivalence test, now genuinely local.

    Centre-crop must be disabled alongside resize and rescale: the real
    config crops to 224, which would compare a different image entirely
    (round 86).
    """
    transformers = pytest.importorskip("transformers")

    config = json.loads(VENDORED_CONFIG.read_text())
    processor = transformers.BitImageProcessor(
        **{key: value for key, value in config.items() if key != "image_processor_type"}
    )

    rng = np.random.default_rng(2)
    normalized = rng.random((336, 336)).astype(np.float32)

    mean, std = load_processor_statistics(VENDORED_CONFIG)
    ours = standardize(to_three_channel(normalized), mean, std)

    theirs = processor(
        np.stack([normalized] * 3, axis=-1),
        do_resize=False,
        do_rescale=False,
        do_center_crop=False,
        return_tensors="pt",
    )["pixel_values"][0]

    assert ours.shape == theirs.shape == (3, 336, 336)
    assert torch.allclose(ours, theirs, atol=1e-5)
