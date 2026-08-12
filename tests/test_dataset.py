from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from knee_mri.dataset import (
    PlaneSelection,
    prepare_modeling_inputs,
    rank_candidate_series,
    select_primary_series,
    select_validated_series,
    series_for_study,
    split_labeled_studies,
)
from knee_mri.labels import LABEL_COLUMNS


def _write_synthetic_slice(
    path: Path,
    instance_number: int,
    *,
    image_position_patient: tuple[float, float, float] | None = None,
    image_orientation_patient: tuple[float, ...] | None = None,
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

    pixels = np.full((4, 4), instance_number, dtype=np.uint16)
    ds.PixelData = pixels.tobytes()
    ds.save_as(str(path), write_like_original=False)


def _write_series(series_dir: Path, slice_count: int, *, valid_geometry: bool = True) -> None:
    series_dir.mkdir(parents=True)
    orientation = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0) if valid_geometry else None
    for i in range(slice_count):
        _write_synthetic_slice(
            series_dir / f"{i}.dcm",
            instance_number=i + 1,
            image_position_patient=(0.0, 0.0, float(i)) if valid_geometry else None,
            image_orientation_patient=orientation,
        )


def _series_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_1a",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_1b",
                "Fluid_Sensitive": 1,
                "Fat_Suppression": 1,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_1c",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Axial",
            },
            {
                "StudyInstanceUID": "study_2",
                "SeriesInstanceUID": "series_2a",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Coronal",
            },
        ]
    )


def test_series_for_study_filters_to_one_study():
    result = series_for_study(_series_frame(), "study_1")

    assert set(result["SeriesInstanceUID"]) == {"series_1a", "series_1b", "series_1c"}


def test_select_primary_series_prefers_fluid_sensitive_within_plane():
    chosen = select_primary_series(_series_frame(), "study_1", plane="Sagittal")

    assert chosen == "series_1b"


def test_select_primary_series_returns_none_when_plane_missing():
    chosen = select_primary_series(_series_frame(), "study_2", plane="Sagittal")

    assert chosen is None


# -- rank_candidate_series --


def test_rank_candidate_series_prefers_fluid_sensitive_over_slice_count(tmp_path: Path):
    series_df = pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "fewer_slices_fluid",
                "Fluid_Sensitive": 1,
                "Fat_Suppression": 1,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "more_slices_not_fluid",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
        ]
    )
    _write_series(tmp_path / "study_1" / "fewer_slices_fluid", slice_count=2)
    _write_series(tmp_path / "study_1" / "more_slices_not_fluid", slice_count=10)

    ranked = rank_candidate_series(series_df, tmp_path, "study_1", plane="Sagittal")

    assert ranked == ["fewer_slices_fluid", "more_slices_not_fluid"]


def test_rank_candidate_series_tie_breaks_by_slice_count(tmp_path: Path):
    series_df = pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_a",
                "Fluid_Sensitive": 1,
                "Fat_Suppression": 1,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_b",
                "Fluid_Sensitive": 1,
                "Fat_Suppression": 1,
                "Anatomical_Plane": "Sagittal",
            },
        ]
    )
    _write_series(tmp_path / "study_1" / "series_a", slice_count=5)
    _write_series(tmp_path / "study_1" / "series_b", slice_count=20)

    ranked = rank_candidate_series(series_df, tmp_path, "study_1", plane="Sagittal")

    assert ranked == ["series_b", "series_a"]


def test_rank_candidate_series_final_tie_break_is_series_id(tmp_path: Path):
    series_df = pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_z",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_a",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
        ]
    )
    _write_series(tmp_path / "study_1" / "series_z", slice_count=5)
    _write_series(tmp_path / "study_1" / "series_a", slice_count=5)

    ranked = rank_candidate_series(series_df, tmp_path, "study_1", plane="Sagittal")

    assert ranked == ["series_a", "series_z"]


def test_rank_candidate_series_empty_when_plane_missing(tmp_path: Path):
    ranked = rank_candidate_series(_series_frame(), tmp_path, "study_2", plane="Sagittal")

    assert ranked == []


def test_rank_candidate_series_treats_missing_directory_as_zero_slices(tmp_path: Path):
    series_df = pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "on_disk",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "not_on_disk",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
        ]
    )
    _write_series(tmp_path / "study_1" / "on_disk", slice_count=3)

    ranked = rank_candidate_series(series_df, tmp_path, "study_1", plane="Sagittal")

    assert ranked == ["on_disk", "not_on_disk"]


# -- select_validated_series --


def test_select_validated_series_returns_top_candidate_when_valid(tmp_path: Path):
    series_df = pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_1",
                "Fluid_Sensitive": 1,
                "Fat_Suppression": 1,
                "Anatomical_Plane": "Sagittal",
            },
        ]
    )
    _write_series(tmp_path / "study_1" / "series_1", slice_count=3)

    result = select_validated_series(series_df, tmp_path, "study_1", plane="Sagittal")

    assert result == PlaneSelection(
        plane="Sagittal",
        series_instance_uid="series_1",
        ordering_method="geometry",
        ordered_paths=result.ordered_paths,
        candidates_tried=1,
    )
    assert result.ordered_paths is not None and len(result.ordered_paths) == 3


def test_select_validated_series_retries_next_candidate_when_top_invalid(tmp_path: Path):
    series_df = pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "invalid_fluid",
                "Fluid_Sensitive": 1,
                "Fat_Suppression": 1,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "valid_not_fluid",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
        ]
    )
    # Top-ranked (fluid-sensitive) candidate: no geometry, duplicate
    # InstanceNumber -- unusable under either validation route.
    invalid_dir = tmp_path / "study_1" / "invalid_fluid"
    invalid_dir.mkdir(parents=True)
    _write_synthetic_slice(invalid_dir / "1.dcm", instance_number=1)
    _write_synthetic_slice(invalid_dir / "2.dcm", instance_number=1)
    _write_series(tmp_path / "study_1" / "valid_not_fluid", slice_count=3)

    result = select_validated_series(series_df, tmp_path, "study_1", plane="Sagittal")

    assert result.series_instance_uid == "valid_not_fluid"
    assert result.ordering_method == "geometry"


def test_select_validated_series_retries_when_top_candidate_is_unreadable(tmp_path: Path):
    series_df = pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "unreadable_fluid",
                "Fluid_Sensitive": 1,
                "Fat_Suppression": 1,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "valid_not_fluid",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
        ]
    )
    # Top-ranked (fluid-sensitive) candidate is a malformed .dcm file --
    # this must not crash selection, only make that candidate unusable.
    unreadable_dir = tmp_path / "study_1" / "unreadable_fluid"
    unreadable_dir.mkdir(parents=True)
    (unreadable_dir / "1.dcm").write_bytes(b"not a real dicom file")
    _write_series(tmp_path / "study_1" / "valid_not_fluid", slice_count=3)

    result = select_validated_series(series_df, tmp_path, "study_1", plane="Sagittal")

    assert result.series_instance_uid == "valid_not_fluid"
    assert result.candidates_tried == 2


def test_select_validated_series_missing_plane_when_all_candidates_invalid(tmp_path: Path):
    series_df = pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "invalid_only",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
        ]
    )
    invalid_dir = tmp_path / "study_1" / "invalid_only"
    invalid_dir.mkdir(parents=True)
    _write_synthetic_slice(invalid_dir / "1.dcm", instance_number=1)
    _write_synthetic_slice(invalid_dir / "2.dcm", instance_number=1)

    result = select_validated_series(series_df, tmp_path, "study_1", plane="Sagittal")

    assert result == PlaneSelection(
        plane="Sagittal",
        series_instance_uid=None,
        ordering_method=None,
        ordered_paths=None,
        candidates_tried=1,
    )


def test_select_validated_series_missing_plane_when_no_candidates(tmp_path: Path):
    result = select_validated_series(_series_frame(), tmp_path, "study_2", plane="Sagittal")

    assert result == PlaneSelection(
        plane="Sagittal",
        series_instance_uid=None,
        ordering_method=None,
        ordered_paths=None,
        candidates_tried=0,
    )


def test_split_labeled_studies_separates_missing_labels():
    rows = []
    for i in range(3):
        row = {"StudyInstanceUID": f"labeled_{i}", "PatientSex": "Female", "Report": "text"}
        row.update(dict.fromkeys(LABEL_COLUMNS, 0))
        rows.append(row)
    for i in range(2):
        row = {"StudyInstanceUID": f"unlabeled_{i}", "PatientSex": "Male", "Report": "text"}
        row.update(dict.fromkeys(LABEL_COLUMNS, np.nan))
        rows.append(row)
    train_df = pd.DataFrame(rows)

    labeled, unlabeled = split_labeled_studies(train_df)

    assert len(labeled) == 3
    assert len(unlabeled) == 2
    assert set(labeled["StudyInstanceUID"]) == {"labeled_0", "labeled_1", "labeled_2"}


def _modeling_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_rows = []
    for row_index in range(58):
        row = {
            "StudyInstanceUID": f"train_{row_index}",
            "Report": f"report {row_index}",
        }
        row.update(
            {
                label: float((row_index + label_index) % 2)
                for label_index, label in enumerate(LABEL_COLUMNS)
            }
        )
        train_rows.append(row)

    unlabeled = {"StudyInstanceUID": "train_unlabeled", "Report": "unlabeled report"}
    unlabeled.update(dict.fromkeys(LABEL_COLUMNS, np.nan))
    train_rows.append(unlabeled)

    test_df = pd.DataFrame(
        [
            {"StudyInstanceUID": "test_0", "Report": "test report"},
            {"StudyInstanceUID": "test_1", "Report": "another report"},
        ]
    )
    sample_df = pd.DataFrame(
        {
            "StudyInstanceUID": test_df["StudyInstanceUID"],
            **dict.fromkeys(LABEL_COLUMNS, 0.0),
        }
    )
    return pd.DataFrame(train_rows), test_df, sample_df


def test_prepare_modeling_inputs_normalizes_empty_test_reports() -> None:
    train_df, test_df, sample_df = _modeling_frames()
    test_df["Report"] = [None, "   "]

    result = prepare_modeling_inputs(train_df, test_df, sample_df)

    assert len(result.labeled_studies) == 58
    assert result.test_studies["Report"].tolist() == ["", ""]
    assert result.missing_test_report_count == 2

    result.labeled_studies.loc[0, "ACL"] = 1.0
    result.test_studies.loc[0, "Report"] = "changed"
    assert train_df.loc[0, "ACL"] == 0.0
    assert pd.isna(test_df.loc[0, "Report"])


def test_prepare_modeling_inputs_rejects_wrong_labeled_count() -> None:
    train_df, test_df, sample_df = _modeling_frames()
    train_df = train_df.loc[train_df["StudyInstanceUID"] != "train_0"]

    with pytest.raises(ValueError, match="exactly 58"):
        prepare_modeling_inputs(train_df, test_df, sample_df)


@pytest.mark.parametrize(
    ("frame_name", "missing_column"),
    [("train", "Report"), ("test", "Report"), ("sample", LABEL_COLUMNS[-1])],
)
def test_prepare_modeling_inputs_rejects_missing_required_columns(
    frame_name: str,
    missing_column: str,
) -> None:
    train_df, test_df, sample_df = _modeling_frames()
    frames = {"train": train_df, "test": test_df, "sample": sample_df}
    frames[frame_name] = frames[frame_name].drop(columns=missing_column)

    with pytest.raises(ValueError, match=f"{frame_name}.*missing required columns"):
        prepare_modeling_inputs(frames["train"], frames["test"], frames["sample"])


def test_prepare_modeling_inputs_rejects_noncanonical_sample_columns() -> None:
    train_df, test_df, sample_df = _modeling_frames()
    sample_df = sample_df[["StudyInstanceUID", *reversed(LABEL_COLUMNS)]]

    with pytest.raises(ValueError, match=r"sample.*canonical order"):
        prepare_modeling_inputs(train_df, test_df, sample_df)


@pytest.mark.parametrize("frame_name", ["train", "test", "sample"])
def test_prepare_modeling_inputs_rejects_null_identifiers(frame_name: str) -> None:
    train_df, test_df, sample_df = _modeling_frames()
    frames = {"train": train_df, "test": test_df, "sample": sample_df}
    frames[frame_name].loc[frames[frame_name].index[0], "StudyInstanceUID"] = None

    with pytest.raises(ValueError, match=f"{frame_name}.*null"):
        prepare_modeling_inputs(frames["train"], frames["test"], frames["sample"])


@pytest.mark.parametrize("frame_name", ["train", "test", "sample"])
def test_prepare_modeling_inputs_rejects_duplicate_identifiers(frame_name: str) -> None:
    train_df, test_df, sample_df = _modeling_frames()
    frames = {"train": train_df, "test": test_df, "sample": sample_df}
    frame = frames[frame_name]
    frame.loc[frame.index[1], "StudyInstanceUID"] = frame.loc[
        frame.index[0], "StudyInstanceUID"
    ]

    with pytest.raises(ValueError, match=f"{frame_name}.*duplicate"):
        prepare_modeling_inputs(frames["train"], frames["test"], frames["sample"])


def test_prepare_modeling_inputs_rejects_sample_id_reordering() -> None:
    train_df, test_df, sample_df = _modeling_frames()
    sample_df = sample_df.iloc[::-1].reset_index(drop=True)

    with pytest.raises(ValueError, match="same order"):
        prepare_modeling_inputs(train_df, test_df, sample_df)


def test_prepare_modeling_inputs_rejects_one_class_label() -> None:
    train_df, test_df, sample_df = _modeling_frames()
    train_df.loc[train_df["ACL"].notna(), "ACL"] = 0.0

    with pytest.raises(ValueError, match=r"both classes.*ACL"):
        prepare_modeling_inputs(train_df, test_df, sample_df)


def test_prepare_modeling_inputs_rejects_non_string_test_report() -> None:
    train_df, test_df, sample_df = _modeling_frames()
    test_df["Report"] = test_df["Report"].astype(object)
    test_df.loc[0, "Report"] = 3.5

    with pytest.raises(ValueError, match=r"test.*non-string Report"):
        prepare_modeling_inputs(train_df, test_df, sample_df)
