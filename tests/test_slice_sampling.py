from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from knee_mri.slice_sampling import (
    MINIMUM_DECODED_SLICES,
    SLICE_SAMPLE_SIZE,
    sample_plane,
    select_plane_sample,
)


def _write_slice(path: Path, instance_number: int, *, corrupt=False, constant=False) -> None:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = generate_uid()
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.InstanceNumber = instance_number
    ds.Rows = 8
    ds.Columns = 8
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelSpacing = [0.5, 0.5]

    if corrupt:
        ds.PixelData = b"\x00\x00"  # far too short for 8x8x16-bit
    elif constant:
        ds.PixelData = np.full((8, 8), 500, dtype=np.uint16).tobytes()
    else:
        rng = np.random.default_rng(instance_number)
        ds.PixelData = rng.integers(0, 4096, size=(8, 8), dtype=np.uint16).tobytes()
    ds.save_as(str(path), write_like_original=False)


def _series(tmp_path: Path, name: str, slice_count: int, **kwargs) -> list[Path]:
    series_dir = tmp_path / name
    series_dir.mkdir()
    paths = []
    for instance_number in range(1, slice_count + 1):
        path = series_dir / f"{instance_number:03d}.dcm"
        _write_slice(path, instance_number, **kwargs)
        paths.append(path)
    return paths


def _corrupt(paths: list[Path], indices) -> None:
    for index in indices:
        _write_slice(paths[index], index + 1, corrupt=True)


# -- sampling one plane --


def test_a_healthy_series_yields_the_full_sample():
    assert SLICE_SAMPLE_SIZE == 5
    assert MINIMUM_DECODED_SLICES == 3


def test_sample_plane_decodes_five_central_band_slices(tmp_path: Path):
    paths = _series(tmp_path, "healthy", 30)

    result = sample_plane(paths)

    assert result.attempted == 5
    assert result.decoded == 5
    assert result.usable is True
    assert len(result.images) == 5
    for image in result.images:
        assert image.dtype == np.float32
        assert 0.0 <= float(image.min()) and float(image.max()) <= 1.0


def test_sampling_is_deterministic(tmp_path: Path):
    paths = _series(tmp_path, "deterministic", 30)

    first = sample_plane(paths)
    second = sample_plane(paths)

    assert [image.tolist() for image in first.images] == [
        image.tolist() for image in second.images
    ]


def test_two_failures_still_leave_the_plane_usable(tmp_path: Path):
    paths = _series(tmp_path, "two_bad", 30)
    sampled = sample_plane(paths)
    assert sampled.decoded == 5
    _corrupt(paths, [6, 15])  # two of the band [6, 10, 15, 19, 23]

    result = sample_plane(paths)

    assert result.attempted == 5
    assert result.decoded == MINIMUM_DECODED_SLICES
    assert result.usable is True
    assert len(result.images) == 3


def test_three_failures_make_the_plane_unusable(tmp_path: Path):
    paths = _series(tmp_path, "three_bad", 30)
    _corrupt(paths, [6, 10, 15])

    result = sample_plane(paths)

    assert result.decoded < MINIMUM_DECODED_SLICES
    assert result.usable is False


def test_a_slice_with_no_usable_variation_counts_as_a_decode_failure(tmp_path: Path):
    """Section 6 step 4 routes an unnormalizable slice into section 4's
    minimum-of-three rule, so it must be counted as a failure, not crash.
    """
    paths = _series(tmp_path, "constant", 30, constant=True)

    result = sample_plane(paths)

    assert result.decoded == 0
    assert result.usable is False


def test_an_unreadable_file_counts_as_a_decode_failure(tmp_path: Path):
    paths = _series(tmp_path, "unreadable", 30)
    paths[15].write_bytes(b"not a real dicom file")

    result = sample_plane(paths)

    assert result.attempted == 5
    assert result.decoded == 4
    assert result.usable is True


@pytest.mark.parametrize("slice_count", [1, 2, 4])
def test_very_short_stacks_can_never_meet_the_minimum(tmp_path: Path, slice_count: int):
    """Rounding collapses duplicate central-band positions, so some short
    stacks yield fewer than three indices and can never satisfy the minimum
    however perfectly they decode.

    The affected set is exactly {1, 2, 4} and is NOT monotonic: a 3-slice
    stack yields [0, 1, 2] and CAN meet the minimum, while a 4-slice stack
    yields only [1, 2] and cannot. Round 83 recorded this as "four or fewer",
    which is wrong; corrected in round 87. Unreachable on observed data --
    the shortest corpus series has 11 slices -- but pinned so the real
    boundary cannot drift unnoticed.
    """
    paths = _series(tmp_path, f"short_{slice_count}", slice_count)

    result = sample_plane(paths)

    assert result.attempted < MINIMUM_DECODED_SLICES
    assert result.usable is False


@pytest.mark.parametrize("slice_count", [3, 5, 6])
def test_short_but_sufficient_stacks_can_meet_the_minimum(tmp_path: Path, slice_count: int):
    """The other half of the boundary: these yield at least three indices."""
    paths = _series(tmp_path, f"ok_{slice_count}", slice_count)

    result = sample_plane(paths)

    assert result.attempted >= MINIMUM_DECODED_SLICES
    assert result.usable is True


def test_the_shortest_observed_stack_depth_still_works(tmp_path: Path):
    paths = _series(tmp_path, "eleven", 11)

    result = sample_plane(paths)

    assert result.attempted == 5
    assert result.usable is True


# -- retry across ranked candidates --


def test_the_first_usable_candidate_wins(tmp_path: Path):
    first = _series(tmp_path, "first", 30)
    second = _series(tmp_path, "second", 30)

    outcome = select_plane_sample([first, second])

    assert outcome.absent is False
    assert outcome.candidates_tried == 1
    assert outcome.sample is not None


def test_an_unusable_candidate_triggers_retry(tmp_path: Path):
    bad = _series(tmp_path, "bad", 30)
    _corrupt(bad, [6, 10, 15])
    good = _series(tmp_path, "good", 30)

    outcome = select_plane_sample([bad, good])

    assert outcome.absent is False
    assert outcome.candidates_tried == 2
    assert outcome.sample.usable is True


def test_the_plane_is_absent_only_after_every_candidate_fails(tmp_path: Path):
    first = _series(tmp_path, "f1", 30)
    second = _series(tmp_path, "f2", 30)
    _corrupt(first, [6, 10, 15])
    _corrupt(second, [6, 10, 15])

    outcome = select_plane_sample([first, second])

    assert outcome.absent is True
    assert outcome.sample is None
    assert outcome.candidates_tried == 2


def test_no_candidates_means_the_plane_is_absent(tmp_path: Path):
    outcome = select_plane_sample([])

    assert outcome.absent is True
    assert outcome.candidates_tried == 0


def test_reported_counters_carry_no_identifiers(tmp_path: Path):
    """Telemetry must be aggregate-only: no path, study, or series id."""
    paths = _series(tmp_path, "telemetry", 30)

    outcome = select_plane_sample([paths])
    rendered = repr(outcome.counters())

    assert "telemetry" not in rendered
    assert ".dcm" not in rendered
    assert str(tmp_path) not in rendered
    assert set(outcome.counters()) == {"attempted", "decoded", "candidates_tried", "absent"}


# -- sampling density is parameterized without moving the frozen default --


def test_the_default_sample_size_is_still_the_frozen_five(tmp_path):
    """The density experiment must not disturb the reported baseline."""
    paths = _series(tmp_path, "default", 40)

    assert sample_plane(paths).attempted == SLICE_SAMPLE_SIZE


def test_a_larger_sample_size_attempts_and_decodes_more_slices(tmp_path):
    paths = _series(tmp_path, "dense", 40)

    dense = sample_plane(paths, sample_size=15)

    assert dense.attempted == 15
    assert dense.decoded == 15


def test_a_denser_sample_stays_inside_the_same_central_band(tmp_path):
    """Density is the single variable under test.

    If a larger sample also reached further toward the periphery, a measured
    difference could not be attributed to density rather than extent.
    """
    from knee_mri.series_audit import central_band_indices

    slice_count = 200
    sparse = central_band_indices(slice_count, SLICE_SAMPLE_SIZE)
    dense = central_band_indices(slice_count, 15)

    assert min(dense) == min(sparse)
    assert max(dense) == max(sparse)
    assert len(dense) > len(sparse)


def test_the_minimum_decoded_rule_does_not_scale_with_sample_size(tmp_path):
    """Plane-absence behaviour must stay identical across the comparison.

    Scaling the minimum with the sample size would let the denser variant
    drop planes the baseline kept, changing which studies contribute rather
    than only how densely each is sampled.
    """
    from knee_mri.series_audit import central_band_indices

    good = _series(tmp_path, "good", 30)
    mixed = _series(tmp_path, "corrupt", 30, corrupt=True)
    # Exactly the minimum decodable, among otherwise-unreadable slices.
    for index in central_band_indices(30, 15)[:MINIMUM_DECODED_SLICES]:
        mixed[index] = good[index]

    sample = sample_plane(mixed, sample_size=15)

    assert sample.attempted > MINIMUM_DECODED_SLICES
    assert sample.decoded == MINIMUM_DECODED_SLICES
    assert sample.usable is True


def test_select_plane_sample_forwards_the_sample_size(tmp_path):
    paths = _series(tmp_path, "forwarded", 40)

    outcome = select_plane_sample([paths], sample_size=15)

    assert outcome.sample is not None
    assert outcome.sample.attempted == 15
