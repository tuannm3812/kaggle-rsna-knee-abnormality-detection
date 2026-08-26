import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

import knee_mri.series_audit as series_audit
from knee_mri.series_audit import (
    GroupLateralityAgreement,
    OrderingValidation,
    SeriesAudit,
    aggregate_group_laterality,
    audit_series,
    central_band_indices,
    fluid_fat_suppression_agreement,
    laterality_from_geometry,
    order_agreement,
    plane_series_counts,
    series_transfer_syntax,
    slice_normal,
    slice_position,
    validate_and_order_series,
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


@pytest.mark.parametrize(
    ("orientation", "expected_axis", "expected_signed_x"),
    [
        ((-1, 0, 0, 0, 1, 0), "columns", -1.0),
        ((0, 1, 0, 1, 0, 0), "rows", 1.0),
        ((0, 1, 0, 0, 0, 1), "slices", 1.0),
    ],
)
def test_patient_lr_axis_metrics_maps_signed_x_to_array_axis(
    orientation: tuple[float, ...], expected_axis: str, expected_signed_x: float
):
    result = series_audit.patient_lr_axis_metrics(orientation)

    assert result.array_axis == expected_axis
    assert result.signed_x == pytest.approx(expected_signed_x)
    assert result.dominant_abs_x == pytest.approx(1.0)
    assert result.runner_up_abs_x == pytest.approx(0.0)
    assert result.dominance_gap == pytest.approx(1.0)


def test_patient_lr_axis_metrics_leaves_tied_axis_unresolved():
    root_half = math.sqrt(0.5)
    result = series_audit.patient_lr_axis_metrics(
        (root_half, root_half, 0, root_half, -root_half, 0)
    )

    assert result.array_axis is None
    assert result.signed_x is None
    assert result.dominant_abs_x == pytest.approx(root_half)
    assert result.runner_up_abs_x == pytest.approx(root_half)
    assert result.dominance_gap == pytest.approx(0.0)


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


def test_order_agreement_midranks_ties_rather_than_ordinal_ranks():
    # True Spearman depends only on the values, never on the order tied
    # entries happen to arrive in. Ordinal (double-argsort) ranks broke that:
    # these two inputs differ only in which tied slice comes first on disk.
    assert order_agreement([1, 1, 2], [0.0, 1.0, 2.0]) == pytest.approx(
        order_agreement([1, 1, 2], [1.0, 0.0, 2.0])
    )
    assert order_agreement([1, 1, 2], [0.0, 1.0, 2.0]) == pytest.approx(0.8660254037844387)


@pytest.mark.parametrize(
    ("instance_numbers", "positions"),
    [
        ([7, 7, 7, 7], [0.0, 1.0, 2.0, 3.0]),
        ([7, 7, 7, 7], [3.0, 2.0, 1.0, 0.0]),
        ([1, 2, 3, 4], [5.0, 5.0, 5.0, 5.0]),
    ],
)
def test_order_agreement_none_when_either_input_is_constant(instance_numbers, positions):
    # A constant input carries no ordering information, so the correlation is
    # undefined. Ordinal ranks reported a perfect +/-1.0 here, which would let
    # a series with no usable InstanceNumber inflate a "fraction monotonic"
    # statistic cited as evidence that every series is internally ordered.
    assert order_agreement(instance_numbers, positions) is None


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


def test_laterality_from_geometry_pins_row_column_axis_convention():
    # Every other fixture in this suite is 4x4 with PixelSpacing (1.0, 1.0),
    # which makes the two possible row/column pairings algebraically
    # identical -- so none of them can detect a swapped convention. This case
    # is deliberately anisotropic in BOTH dimensions and spacing so the
    # pairing is observable.
    #
    # DICOM's pixel-to-patient mapping pairs the row direction cosine with the
    # COLUMN index and PixelSpacing[1], and the column direction cosine with
    # the ROW index and PixelSpacing[0]. Here the column direction has no
    # x-component, so only the row-direction term moves the centre:
    #   correct:  -40 + ((128 - 1) / 2) * 0.25 = -24.125  -> "R"
    #   swapped:  -40 + ((512 - 1) / 2) * 1.00 = +215.5   -> "L"
    result = laterality_from_geometry(
        image_position_patient=[-40.0, 0.0, 0.0],
        image_orientation_patient=[1, 0, 0, 0, 0, -1],
        rows=512,
        columns=128,
        pixel_spacing=(1.0, 0.25),
    )
    assert result == "R"


# -- central_band_indices --


def test_central_band_indices_full_band_covers_whole_stack():
    assert central_band_indices(5, 5, band=(0.0, 1.0)) == [0, 1, 2, 3, 4]


def test_central_band_indices_caps_at_slice_count():
    indices = central_band_indices(3, 10)
    assert len(indices) <= 3
    assert all(0 <= i < 3 for i in indices)


def test_central_band_indices_yields_the_full_sample_for_every_observed_stack_depth():
    """Rounding collapses duplicate positions, so a small stack can yield
    fewer indices than requested. Section 4 of the Phase 3B spec samples five
    and requires at least three decodes, which silently assumes five are
    actually attempted. Pin where that assumption holds: the shortest series
    observed in the corpus has 11 slices, and every depth from 7 up returns
    the full five.
    """
    for slice_count in range(7, 330):
        assert len(central_band_indices(slice_count, 5)) == 5


def test_central_band_indices_collapses_only_on_very_short_stacks():
    """The converse, pinned so the boundary cannot drift unnoticed: at four
    slices the sampler returns two indices, which is already below section
    4's minimum of three successful decodes -- such a series can never
    satisfy that rule however well it decodes. Unreachable on observed data
    (minimum observed depth is 11) but recorded rather than assumed.
    """
    assert [len(central_band_indices(n, 5)) for n in range(1, 7)] == [1, 2, 3, 2, 3, 4]


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
    image_laterality: str | None = None,
    corrupt_pixel_data: bool = False,
    omit_instance_number: bool = False,
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
    if not omit_instance_number:
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
    if image_laterality is not None:
        ds.ImageLaterality = image_laterality

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
    assert result.laterality_tag_present_fraction == pytest.approx(1.0)
    assert result.laterality_tag == "L"
    assert result.laterality_tag_consistent is True
    assert result.laterality_from_geometry == "L"
    assert result.laterality_conflict is False
    assert result.laterality_filled_by_geometry is False
    assert result.pixel_spacing == (1.0, 1.0)
    assert result.decode_attempted == 3
    assert result.decode_failures == 0
    assert len(result.decode_results) == 3
    assert all(succeeded for _, succeeded in result.decode_results)


def test_audit_series_reports_consistent_reversal_as_negative_correlation(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    orientation = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    # InstanceNumber increases while geometry position decreases: a
    # consistent reversal, not disagreement.
    for instance_number, z in [(1, 10.0), (2, 5.0), (3, 0.0)]:
        _write_synthetic_slice(
            series_dir / f"{instance_number}.dcm",
            instance_number=instance_number,
            image_position_patient=(30.0, 0.0, z),
            image_orientation_patient=orientation,
            pixel_spacing=(1.0, 1.0),
        )

    result = audit_series(series_dir)

    assert result.order_agreement == pytest.approx(-1.0)


def test_audit_series_falls_back_to_image_laterality(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    for instance_number in (1, 2):
        _write_synthetic_slice(
            series_dir / f"{instance_number}.dcm",
            instance_number=instance_number,
            image_laterality="R",
        )

    result = audit_series(series_dir)

    assert result.laterality_tag_present_fraction == pytest.approx(1.0)
    assert result.laterality_tag == "R"
    assert result.laterality_tag_consistent is True


def test_audit_series_rejects_invalid_laterality_values(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(series_dir / "1.dcm", instance_number=1, laterality="")
    _write_synthetic_slice(series_dir / "2.dcm", instance_number=2, laterality="U")

    result = audit_series(series_dir)

    assert result.laterality_tag_present_fraction == pytest.approx(0.0)
    assert result.laterality_tag is None
    assert result.laterality_tag_consistent is True


def test_audit_series_flags_inconsistent_laterality_across_slices(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(series_dir / "1.dcm", instance_number=1, laterality="L")
    _write_synthetic_slice(series_dir / "2.dcm", instance_number=2, laterality="R")

    result = audit_series(series_dir)

    assert result.laterality_tag_present_fraction == pytest.approx(1.0)
    assert result.laterality_tag_consistent is False
    assert result.laterality_tag is None


def test_audit_series_flags_cross_tag_conflict_between_laterality_tags(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(
        series_dir / "1.dcm", instance_number=1, laterality="L", image_laterality="R"
    )

    result = audit_series(series_dir)

    assert result.laterality_cross_tag_conflict is True
    # Laterality still takes precedence for the resolved call.
    assert result.laterality_tag == "L"


def test_audit_series_no_cross_tag_conflict_when_tags_agree(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(
        series_dir / "1.dcm", instance_number=1, laterality="L", image_laterality="L"
    )

    result = audit_series(series_dir)

    assert result.laterality_cross_tag_conflict is False


def test_audit_series_resolved_call_prefers_tag_over_geometry(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(-30.0, 0.0, 0.0),
        image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        pixel_spacing=(1.0, 1.0),
        laterality="L",
    )

    result = audit_series(series_dir)

    # Geometry alone would call this "R" (negative x); the tag still wins.
    assert result.laterality_from_geometry == "R"
    assert result.laterality_resolved_call == "L"


def test_audit_series_resolved_call_falls_back_to_geometry(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(30.0, 0.0, 0.0),
        image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        pixel_spacing=(1.0, 1.0),
    )

    result = audit_series(series_dir)

    assert result.laterality_tag is None
    assert result.laterality_resolved_call == "L"


def test_audit_series_resolved_call_none_when_unresolvable(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(series_dir / "1.dcm", instance_number=1)

    result = audit_series(series_dir)

    assert result.laterality_resolved_call is None


def test_audit_series_reports_geometry_filling_a_missing_laterality_tag(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    orientation = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    for instance_number, z in [(1, 0.0), (2, 5.0)]:
        _write_synthetic_slice(
            series_dir / f"{instance_number}.dcm",
            instance_number=instance_number,
            image_position_patient=(30.0, 0.0, z),
            image_orientation_patient=orientation,
            pixel_spacing=(1.0, 1.0),
        )

    result = audit_series(series_dir)

    assert result.laterality_tag is None
    assert result.laterality_from_geometry == "L"
    assert result.laterality_filled_by_geometry is True
    assert result.laterality_conflict is False


def test_audit_series_handles_missing_geometry_tags(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    for instance_number in (1, 2):
        _write_synthetic_slice(series_dir / f"{instance_number}.dcm", instance_number)

    result = audit_series(series_dir)

    assert result.has_full_geometry_tags is False
    assert result.order_agreement is None
    assert result.laterality_tag_present_fraction == pytest.approx(0.0)
    assert result.laterality_from_geometry is None
    assert result.laterality_conflict is False
    assert result.laterality_filled_by_geometry is False
    assert result.pixel_spacing is None


def test_audit_series_counts_pixel_decode_failures(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(series_dir / "1.dcm", instance_number=1, corrupt_pixel_data=True)
    _write_synthetic_slice(series_dir / "2.dcm", instance_number=2)

    result = audit_series(series_dir, decode_sample_size=2)

    assert result.decode_attempted == 2
    assert result.decode_failures == 1
    assert len(result.decode_results) == 2
    assert sum(1 for _, succeeded in result.decode_results if not succeeded) == 1
    assert all(transfer_syntax != "unknown" for transfer_syntax, _ in result.decode_results)


def test_audit_series_raises_on_empty_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty_series"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError, match=r"No \.dcm files"):
        audit_series(empty_dir)


def test_audit_series_does_not_crash_on_degenerate_present_orientation(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    # Row and column direction cosines identical: geometry tags are present
    # but the cross product (slice normal) is degenerate.
    degenerate_orientation = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=degenerate_orientation,
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=2,
        image_position_patient=(0.0, 0.0, 1.0),
        image_orientation_patient=degenerate_orientation,
    )

    result = audit_series(series_dir)

    assert result.order_agreement is None
    # Geometry fails (degenerate), but valid unique InstanceNumbers let the
    # fallback route still validate the series.
    assert result.ordering_usable is True
    assert result.ordering_method == "instance_number"


def test_audit_series_does_not_crash_on_missing_instance_number(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    orientation = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=orientation,
        omit_instance_number=True,
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=2,
        image_position_patient=(0.0, 0.0, 1.0),
        image_orientation_patient=orientation,
        omit_instance_number=True,
    )

    result = audit_series(series_dir)

    assert result.order_agreement is None
    # Valid geometry lets the series validate even without InstanceNumber.
    assert result.ordering_usable is True
    assert result.ordering_method == "geometry"


def test_audit_series_counts_unreadable_header_in_mixed_series(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    orientation = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=orientation,
        pixel_spacing=(1.0, 1.0),
        laterality="L",
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=2,
        image_position_patient=(0.0, 0.0, 1.0),
        image_orientation_patient=orientation,
        pixel_spacing=(1.0, 1.0),
        laterality="L",
    )
    (series_dir / "3.dcm").write_bytes(b"not a real dicom file")

    result = audit_series(series_dir)

    assert result.slice_count == 3
    assert result.header_read_failures == 1
    # A series missing one member's data entirely cannot be validated as a
    # complete order, even though the two readable slices agree.
    assert result.ordering_usable is False
    assert result.ordering_method is None
    # An unreadable slice cannot prove it carries valid geometry tags, so it
    # counts against "coverage" claims rather than being silently excluded
    # from their denominator (round 57, cleanup 1) -- even though both
    # readable slices have full geometry tags and a valid "L" laterality
    # tag, has_full_geometry_tags is False and the fraction is 2/3, not 1.0.
    assert result.has_full_geometry_tags is False
    assert result.laterality_tag_present_fraction == pytest.approx(2 / 3)
    assert result.laterality_tag == "L"


def test_audit_series_handles_wholly_unreadable_series(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    (series_dir / "1.dcm").write_bytes(b"not a real dicom file")
    (series_dir / "2.dcm").write_bytes(b"also not a real dicom file")

    result = audit_series(series_dir)

    assert result.slice_count == 2
    assert result.header_read_failures == 2
    assert result.ordering_usable is False
    assert result.ordering_method is None
    assert result.has_full_geometry_tags is False
    assert result.order_agreement is None
    assert result.laterality_tag_present_fraction == pytest.approx(0.0)
    assert result.laterality_tag is None
    assert result.laterality_from_geometry is None
    assert result.pixel_spacing is None
    # Decode sampling still runs against the original files and reports
    # the same underlying unreadability as a decode failure.
    assert result.decode_failures == result.decode_attempted


@pytest.mark.parametrize(
    ("label", "orientation", "spacing", "expected_spacing"),
    [
        ("pixel_spacing_zero_length", (1.0, 0.0, 0.0, 0.0, 1.0, 0.0), (), None),
        ("pixel_spacing_vm_1", (1.0, 0.0, 0.0, 0.0, 1.0, 0.0), (0.5,), None),
        ("orientation_zero_length", (), (0.5, 0.5), (0.5, 0.5)),
    ],
)
def test_audit_series_survives_present_but_valueless_tags(
    tmp_path: Path,
    label: str,
    orientation: tuple,
    spacing: tuple,
    expected_spacing: tuple | None,
):
    # A tag can be present and still carry no usable value: a zero-length
    # element reads back as None and a VM-1 PixelSpacing as a bare DSfloat,
    # both unsubscriptable. audit_series documents FileNotFoundError as its
    # only exception, and one such slice anywhere in the corpus would
    # otherwise abort the whole preflight run rather than degrade.
    series_dir = tmp_path / label
    series_dir.mkdir()
    for instance_number in (1, 2):
        _write_synthetic_slice(
            series_dir / f"{instance_number}.dcm",
            instance_number=instance_number,
            image_position_patient=(30.0, 0.0, 5.0 * instance_number),
            image_orientation_patient=orientation,
            pixel_spacing=spacing,
        )

    result = audit_series(series_dir)

    assert result.slice_count == 2
    assert result.pixel_spacing == expected_spacing
    # Geometry-derived laterality cannot resolve from a valueless tag, but
    # that degrades one diagnostic rather than condemning the series.
    assert result.laterality_from_geometry is None
    assert result.ordering_usable is True


# -- series_transfer_syntax (codec census, round 60 finding 8) --


def test_series_transfer_syntax_reads_representative_slice(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    for instance_number in (1, 2):
        _write_synthetic_slice(series_dir / f"{instance_number}.dcm", instance_number)

    # _write_synthetic_slice stores ExplicitVRLittleEndian (uncompressed).
    assert series_transfer_syntax(series_dir) == "1.2.840.10008.1.2.1"


def test_series_transfer_syntax_skips_unreadable_leading_file(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    # Sorts first, so a naive "read dcm_paths[0]" would report the series as
    # unknown even though every other slice states its syntax perfectly well.
    (series_dir / "0.dcm").write_bytes(b"not a real dicom file")
    _write_synthetic_slice(series_dir / "1.dcm", instance_number=1)

    assert series_transfer_syntax(series_dir) == "1.2.840.10008.1.2.1"


def test_series_transfer_syntax_none_when_every_file_unreadable(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    (series_dir / "1.dcm").write_bytes(b"not a real dicom file")
    (series_dir / "2.dcm").write_bytes(b"also not a real dicom file")

    assert series_transfer_syntax(series_dir) is None


def test_series_transfer_syntax_raises_on_empty_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty_series"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError, match=r"No \.dcm files"):
        series_transfer_syntax(empty_dir)


# -- validate_and_order_series --


def test_validate_and_order_series_uses_geometry_when_valid(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    orientation = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    # Filenames deliberately sort opposite to the true geometric (z) order.
    _write_synthetic_slice(
        series_dir / "a_last.dcm",
        instance_number=3,
        image_position_patient=(30.0, 0.0, 10.0),
        image_orientation_patient=orientation,
    )
    _write_synthetic_slice(
        series_dir / "b_middle.dcm",
        instance_number=2,
        image_position_patient=(30.0, 0.0, 5.0),
        image_orientation_patient=orientation,
    )
    _write_synthetic_slice(
        series_dir / "c_first.dcm",
        instance_number=1,
        image_position_patient=(30.0, 0.0, 0.0),
        image_orientation_patient=orientation,
    )

    result = validate_and_order_series(series_dir)

    assert result.usable is True
    assert result.method == "geometry"
    assert [path.name for path in result.ordered_paths] == [
        "c_first.dcm",
        "b_middle.dcm",
        "a_last.dcm",
    ]


def test_validate_and_order_series_falls_back_to_instance_number_without_geometry(
    tmp_path: Path,
):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    # Filenames deliberately sort opposite to InstanceNumber, so this only
    # passes if the fallback actually uses InstanceNumber, not filename.
    _write_synthetic_slice(series_dir / "a_first.dcm", instance_number=3)
    _write_synthetic_slice(series_dir / "b_middle.dcm", instance_number=2)
    _write_synthetic_slice(series_dir / "c_last.dcm", instance_number=1)

    result = validate_and_order_series(series_dir)

    assert result.usable is True
    assert result.method == "instance_number"
    assert [path.name for path in result.ordered_paths] == [
        "c_last.dcm",
        "b_middle.dcm",
        "a_first.dcm",
    ]


def test_validate_and_order_series_unusable_on_duplicate_instance_numbers(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    # No geometry, and both slices share the same InstanceNumber: this must
    # be reported unusable, not silently fall back to filename order.
    _write_synthetic_slice(series_dir / "1.dcm", instance_number=1)
    _write_synthetic_slice(series_dir / "2.dcm", instance_number=1)

    result = validate_and_order_series(series_dir)

    assert result == OrderingValidation(usable=False, method=None, ordered_paths=None)


def test_validate_and_order_series_unusable_on_inconsistent_orientation(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    # Two slices with very different orientation -- not one coherent series.
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=2,
        image_position_patient=(0.0, 0.0, 5.0),
        image_orientation_patient=(0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
    )

    result = validate_and_order_series(series_dir)

    # Geometry route fails (inconsistent orientation); InstanceNumber route
    # is valid and unique, so it's the accepted fallback.
    assert result.usable is True
    assert result.method == "instance_number"


def test_validate_and_order_series_unusable_on_duplicate_positions(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    orientation = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    # Both slices at the identical physical position -- geometry can't order them.
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=orientation,
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=2,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=orientation,
    )

    result = validate_and_order_series(series_dir)

    # Geometry route fails (duplicate position); InstanceNumber route is
    # valid and unique, so it's the accepted fallback.
    assert result.usable is True
    assert result.method == "instance_number"


def test_validate_and_order_series_unusable_when_neither_route_validates(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    orientation = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    # Duplicate position (geometry fails) AND duplicate InstanceNumber
    # (InstanceNumber fails too): genuinely unusable.
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=orientation,
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=orientation,
    )

    result = validate_and_order_series(series_dir)

    assert result == OrderingValidation(usable=False, method=None, ordered_paths=None)


def test_validate_and_order_series_raises_on_empty_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty_series"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError, match=r"No \.dcm files"):
        validate_and_order_series(empty_dir)


def test_validate_and_order_series_unusable_on_unreadable_file(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    (series_dir / "1.dcm").write_bytes(b"not a real dicom file")

    result = validate_and_order_series(series_dir)

    assert result == OrderingValidation(usable=False, method=None, ordered_paths=None)


def test_validate_and_order_series_rejects_in_plane_rotation_between_slices(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    # Both slices share the same derived normal (0, 0, 1), but the second is
    # rotated 90 degrees in-plane -- a normal-only check would wrongly
    # accept this as one coherent series.
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=1,  # duplicate on purpose to disable the InstanceNumber fallback
        image_position_patient=(0.0, 0.0, 1.0),
        image_orientation_patient=(0.0, 1.0, 0.0, -1.0, 0.0, 0.0),
    )

    result = validate_and_order_series(series_dir)

    assert result == OrderingValidation(usable=False, method=None, ordered_paths=None)


def test_validate_and_order_series_rejects_rotation_about_a_shared_row_axis(tmp_path: Path):
    """Two slices sharing a row direction but rotated about it.

    Round 52 finding 3 required BOTH row and column agreement, precisely
    because comparing derived normals alone accepts an in-plane rotation.
    But the existing in-plane-rotation fixture rotates 90 degrees, which
    changes the row direction too -- so the ROW check alone catches it and
    the COLUMN check is never exercised. Mutation testing confirmed the whole
    column clause could be deleted with the suite still green.

    Here both slices are orthonormal and share row (1,0,0) exactly, so only
    the column comparison can reject them: dot((0,1,0), (0,0,1)) == 0.
    """
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,  # duplicated below to disable the InstanceNumber route
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 1.0),
        image_orientation_patient=(1.0, 0.0, 0.0, 0.0, 0.0, 1.0),
    )

    result = validate_and_order_series(series_dir)

    assert result == OrderingValidation(usable=False, method=None, ordered_paths=None)


def test_slice_normal_returns_a_unit_vector_for_non_unit_inputs(tmp_path: Path):
    """The docstring promises a unit-length normal. For the already-normalized
    inputs the geometry route feeds it the normalization is near-redundant, so
    dropping it left the suite green; pin the documented contract directly.
    """
    normal = slice_normal([3.0, 0.0, 0.0, 0.0, 4.0, 0.0])

    assert np.linalg.norm(normal) == pytest.approx(1.0)
    assert normal == pytest.approx([0.0, 0.0, 1.0])


def test_validate_and_order_series_rejects_non_unit_orientation_vectors(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    # Direction cosines with norm 2.0, not the DICOM-required 1.0.
    non_unit_orientation = (2.0, 0.0, 0.0, 0.0, 2.0, 0.0)
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=non_unit_orientation,
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 1.0),
        image_orientation_patient=non_unit_orientation,
    )

    result = validate_and_order_series(series_dir)

    assert result == OrderingValidation(usable=False, method=None, ordered_paths=None)


def test_validate_and_order_series_rejects_non_orthogonal_orientation_vectors(tmp_path: Path):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    # Row and column direction cosines are not orthogonal (45 degrees apart).
    root_half = 0.7071067811865476
    non_orthogonal_orientation = (1.0, 0.0, 0.0, root_half, root_half, 0.0)
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=non_orthogonal_orientation,
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 1.0),
        image_orientation_patient=non_orthogonal_orientation,
    )

    result = validate_and_order_series(series_dir)

    assert result == OrderingValidation(usable=False, method=None, ordered_paths=None)


def test_validate_and_order_series_accepts_slightly_under_unit_identical_orientation(
    tmp_path: Path,
):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    # Norm 0.995 is within the default 0.01 unit-norm tolerance. Both slices
    # share the exact same (scaled) direction cosines, so a true cosine-
    # similarity comparison between them must be 1.0 regardless of the
    # shared norm -- a raw (non-normalized) dot product would instead
    # compare 0.995**2 == 0.990025 against the 0.999 orientation tolerance
    # and wrongly reject this series (round 55, finding 2).
    scale = 0.995
    orientation = (scale, 0.0, 0.0, 0.0, scale, 0.0)
    _write_synthetic_slice(
        series_dir / "1.dcm",
        instance_number=1,  # duplicate on purpose to disable the InstanceNumber fallback
        image_position_patient=(0.0, 0.0, 0.0),
        image_orientation_patient=orientation,
    )
    _write_synthetic_slice(
        series_dir / "2.dcm",
        instance_number=1,
        image_position_patient=(0.0, 0.0, 1.0),
        image_orientation_patient=orientation,
    )

    result = validate_and_order_series(series_dir)

    assert result.usable is True
    assert result.method == "geometry"

    # A genuinely misaligned orientation -- not merely under-unit-norm --
    # is still correctly rejected once vectors are normalized before the
    # cosine-similarity comparison; see
    # test_validate_and_order_series_rejects_in_plane_rotation_between_slices
    # for that case (exactly unit-norm, orthogonal per-slice, but rotated
    # relative to each other).


@pytest.mark.parametrize(
    "kwargs",
    [
        {"orientation_tolerance": 1.5},
        {"orientation_tolerance": -1.5},
        {"orientation_tolerance": math.inf},
        {"position_tolerance_mm": -0.01},
        {"position_tolerance_mm": 0.0},
        {"position_tolerance_mm": math.inf},
        {"unit_norm_tolerance": -0.01},
        {"unit_norm_tolerance": 1.0},
        {"unit_norm_tolerance": math.inf},
        {"orthogonality_tolerance": -0.01},
        {"orthogonality_tolerance": 1.0},
        {"orthogonality_tolerance": math.inf},
    ],
)
def test_validate_and_order_series_rejects_nonsensical_tolerances(tmp_path: Path, kwargs: dict):
    series_dir = tmp_path / "series"
    series_dir.mkdir()
    _write_synthetic_slice(series_dir / "1.dcm", instance_number=1)

    with pytest.raises(ValueError, match=r"must be (in|finite)"):
        validate_and_order_series(series_dir, **kwargs)


# -- aggregate_group_laterality --


def test_aggregate_group_laterality_consistent_group():
    result = aggregate_group_laterality(["L", "L", "L"])

    assert result == GroupLateralityAgreement(
        total=3, resolved=3, consistent=True, consensus_call="L"
    )


def test_aggregate_group_laterality_flags_disagreement():
    result = aggregate_group_laterality(["L", "R", "L"])

    assert result.consistent is False
    assert result.consensus_call is None
    assert result.resolved == 3


def test_aggregate_group_laterality_ignores_unresolved_series():
    result = aggregate_group_laterality(["L", None, "L", None])

    assert result.total == 4
    assert result.resolved == 2
    assert result.consistent is True
    assert result.consensus_call == "L"


def test_aggregate_group_laterality_all_unresolved():
    result = aggregate_group_laterality([None, None])

    assert result == GroupLateralityAgreement(
        total=2, resolved=0, consistent=True, consensus_call=None
    )
