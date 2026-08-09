import numpy as np
import pandas as pd

from knee_mri.dataset import select_primary_series, series_for_study, split_labeled_studies
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
        row.update({label: 0 for label in LABEL_COLUMNS})
        rows.append(row)
    for i in range(2):
        row = {"StudyInstanceUID": f"unlabeled_{i}", "PatientSex": "Male", "Report": "text"}
        row.update({label: np.nan for label in LABEL_COLUMNS})
        rows.append(row)
    train_df = pd.DataFrame(rows)

    labeled, unlabeled = split_labeled_studies(train_df)

    assert len(labeled) == 3
    assert len(unlabeled) == 2
    assert set(labeled["StudyInstanceUID"]) == {"labeled_0", "labeled_1", "labeled_2"}
