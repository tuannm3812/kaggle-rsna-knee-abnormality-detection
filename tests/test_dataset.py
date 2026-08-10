import numpy as np
import pandas as pd
import pytest

from knee_mri.dataset import (
    prepare_modeling_inputs,
    select_primary_series,
    series_for_study,
    split_labeled_studies,
)
from knee_mri.labels import LABEL_COLUMNS


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
