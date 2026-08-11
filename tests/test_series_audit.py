from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from knee_mri.series_audit import (
    SeriesAudit,
    audit_series,
    central_band_indices,
    fluid_fat_suppression_agreement,
    laterality_from_geometry,
    order_agreement,
    plane_series_counts,
    slice_normal,
    slice_position,
)

# -- slice_normal / slice_position --


def test_slice_normal_is_unit_cross_product_for_axial_orientation():
    normal = slice_normal([1, 0, 0, 0, 1, 0])
    assert normal == pytest.approx([0, 0, 1])


def test_slice_normal_raises_on_degenerate_orientation():
    with pytest.raises(ValueError, match="degenerate"):
        slice_normal([1, 0, 0, 1, 0, 0])


def test_slice_position_is_dot_product_with_normal():
    normal = np.array([0.0, 0.0, 1.0])
    assert slice_position([1, 2, 5], normal) == pytest.approx(5.0)


# -- order_agreement --


def test_order_agreement_perfect_when_instance_number_tracks_geometry():
    assert order_agreement([1, 2, 3], [0, 5, 10]) == pytest.approx(1.0)


def test_order_agreement_negative_one_on_consistent_reversal():
    assert order_agreement([1, 2, 3], [10, 5, 0]) == pytest.approx(-1.0)


def test_order_agreement_none_below_two_slices():
    assert order_agreement([1], [0]) is None
    assert order_agreement([], []) is None


def test_order_agreement_raises_on_length_mismatch():
    with pytest.raises(ValueError, match="same length"):
        order_agreement([1, 2], [0])


# -- laterality_from_geometry --


def test_laterality_from_geometry_calls_left_and_right():
    orientation = [1, 0, 0, 0, 1, 0]
    left = laterality_from_geometry(
        image_position_patient=[30, 0, 0],
        image_orientation_patient=orientation,
        rows=4,
        columns=4,
        pixel_spacing=(1.0, 1.0),
    )
    right = laterality_from_geometry(
        image_position_patient=[-30, 0, 0],
        image_orientation_patient=orientation,
        rows=4,
        columns=4,
        pixel_spacing=(1.0, 1.0),
    )
    assert left == "L"
    assert right == "R"


def test_laterality_from_geometry_unresolved_within_dead_zone():
    result = laterality_from_geometry(
        image_position_patient=[-1, 0, 0],
        image_orientation_patient=[1, 0, 0, 0, 1, 0],
        rows=4,
        columns=4,
        pixel_spacing=(1.0, 1.0),
    )
    assert result is None


# -- central_band_indices --


def test_central_band_indices_full_band_covers_whole_stack():
    assert central_band_indices(5, 5, band=(0.0, 1.0)) == [0, 1, 2, 3, 4]


def test_central_band_indices_caps_at_slice_count():
    indices = central_band_indices(3, 10)
    assert len(indices) <= 3
    assert all(0 <= i < 3 for i in indices)


def test_central_band_indices_rejects_non_positive_inputs():
    with pytest.raises(ValueError, match="slice_count"):
        central_band_indices(0, 5)
    with pytest.raises(ValueError, match="sample_size"):
        central_band_indices(5, 0)


# -- fluid_fat_suppression_agreement / plane_series_counts --


def test_fluid_fat_suppression_agreement_counts_all_combinations():
    series_df = pd.DataFrame(
        {
            "Fluid_Sensitive": [1, 1, 0, 0],
            "Fat_Suppression": [1, 0, 1, 0],
        }
    )
    result = fluid_fat_suppression_agreement(series_df)
    assert result == {
        "total": 4,
        "agree": 2,
        "agreement_rate": 0.5,
        "fluid1_fat1": 1,
        "fluid1_fat0": 1,
        "fluid0_fat1": 1,
        "fluid0_fat0": 1,
    }


def test_plane_series_counts_pivots_per_study():
    series_df = pd.DataFrame(
        {
            "StudyInstanceUID": ["s1", "s1", "s2"],
            "Anatomical_Plane": ["Sagittal", "Coronal", "Sagittal"],
        }
    )
    counts = plane_series_counts(series_df)
    assert counts.loc["s1", "Sagittal"] == 1
    assert counts.loc["s1", "Coronal"] == 1
    assert counts.loc["s2", "Sagittal"] == 1
    assert counts.loc["s2", "Coronal"] == 0


# -- audit_series (integration, synthetic on-disk DICOM) --


def _write_synthetic_slice(
    path: Path,
    instance_number: int,
    *,
    image_position_patient: tuple[float, float, float] | None = None,
    image_orientation_patient: tuple[float, ...] | None = None,
    pixel_spacing: tuple[float, float] | None = None,
    laterality: str | None = None,
    corrupt_pixel_data: bool = False,
) -> None:
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
    ds.Rows = 4
    ds.Columns = 4
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0

    if image_position_patient is not None:
        ds.ImagePositionPatient = list(image_position_patient)
    if image_orientation_patient is not None:
        ds.ImageOrientationPatient = list(image_orientation_patient)
    if pixel_spacing is not None:
        ds.PixelSpacing = list(pixel_spacing)
    if laterality is not None:
        ds.Laterality = laterality

    if corrupt_pixel_data:
        ds.PixelData = b"\x00\x00"  # far too short for a 4x4x16-bit slice
    else:
        pixels = np.full((4, 4), instance_number, dtype=np.uint16)
        ds.PixelData = pixels.tobytes()

    ds.save_as(str(path), write_like_original=False)


def test_audit_series_reports_geometry_order_and_laterality(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    orientation = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    for instance_number, z in [(1, 0.0), (2, 5.0), (3, 10.0)]:
        _write_synthetic_slice(
            series_dir / f"{instance_number}.dcm",
            instance_number=instance_number,
            image_position_patient=(30.0, 0.0, z),
            image_orientation_patient=orientation,
            pixel_spacing=(1.0, 1.0),
            laterality="L",
        )

    result = audit_series(series_dir)

    assert isinstance(result, SeriesAudit)
    assert result.slice_count == 3
    assert result.has_full_geometry_tags is True
    assert result.order_agreement == pytest.approx(1.0)
    assert result.has_laterality_tag is True
    assert result.laterality_tag == "L"
    assert result.laterality_from_geometry == "L"
    assert result.laterality_conflict is False
    assert result.pixel_spacing == (1.0, 1.0)
    assert result.decode_attempted == 3
    assert result.decode_failures == 0


def test_audit_series_handles_missing_geometry_tags(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    for instance_number in (1, 2):
        _write_synthetic_slice(series_dir / f"{instance_number}.dcm", instance_number)

    result = audit_series(series_dir)

    assert result.has_full_geometry_tags is False
    assert result.order_agreement is None
    assert result.has_laterality_tag is False
    assert result.laterality_from_geometry is None
    assert result.laterality_conflict is False
    assert result.pixel_spacing is None


def test_audit_series_counts_pixel_decode_failures(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(series_dir / "1.dcm", instance_number=1, corrupt_pixel_data=True)
    _write_synthetic_slice(series_dir / "2.dcm", instance_number=2)

    result = audit_series(series_dir, decode_sample_size=2)

    assert result.decode_attempted == 2
    assert result.decode_failures == 1


def test_audit_series_raises_on_empty_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty_series"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError, match=r"No \.dcm files"):
        audit_series(empty_dir)
