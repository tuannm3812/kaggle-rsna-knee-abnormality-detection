import numpy as np
import pandas as pd
import pytest

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.validation import validate_labeled_studies


def _row(study_id: str | None, report: object, **labels: int) -> dict:
    row = {"StudyInstanceUID": study_id, "Report": report}
    row.update(dict.fromkeys(LABEL_COLUMNS, 0))
    row.update(labels)
    return row


def test_validate_labeled_studies_rejects_missing_column() -> None:
    frame = pd.DataFrame([{"StudyInstanceUID": "s1", "Report": "report"}])

    with pytest.raises(ValueError, match="missing required columns"):
        validate_labeled_studies(frame)


def test_validate_labeled_studies_rejects_empty_frame() -> None:
    frame = pd.DataFrame(columns=["StudyInstanceUID", "Report", *LABEL_COLUMNS])

    with pytest.raises(ValueError, match="zero rows"):
        validate_labeled_studies(frame)


def test_validate_labeled_studies_rejects_duplicate_study_id() -> None:
    frame = pd.DataFrame([_row("s1", "report a"), _row("s1", "report b")])

    with pytest.raises(ValueError, match="duplicate StudyInstanceUID"):
        validate_labeled_studies(frame)


def test_validate_labeled_studies_rejects_null_study_id() -> None:
    frame = pd.DataFrame([_row(None, "report")])

    with pytest.raises(ValueError, match="null or duplicate StudyInstanceUID"):
        validate_labeled_studies(frame)


def test_validate_labeled_studies_rejects_non_binary_label_value() -> None:
    frame = pd.DataFrame([_row("s1", "report", ACL=2)])

    with pytest.raises(ValueError, match="outside"):
        validate_labeled_studies(frame)


def test_validate_labeled_studies_rejects_bool_label_column() -> None:
    frame = pd.DataFrame([_row("s1", "report")])
    frame["ACL"] = frame["ACL"].astype(bool)

    with pytest.raises(ValueError, match="outside"):
        validate_labeled_studies(frame)


def test_validate_labeled_studies_rejects_mixed_object_bool_value() -> None:
    frame = pd.DataFrame([_row("s1", "report"), _row("s2", "report 2")])
    frame["ACL"] = pd.Series([True, 0], dtype=object)

    with pytest.raises(ValueError, match="outside"):
        validate_labeled_studies(frame)


def test_validate_labeled_studies_accepts_clean_float_labels() -> None:
    frame = pd.DataFrame([_row("s1", "report", ACL=1), _row("s2", "report 2")])
    frame["ACL"] = frame["ACL"].astype(float)

    validate_labeled_studies(frame)


def test_validate_labeled_studies_rejects_fractional_label_value() -> None:
    frame = pd.DataFrame([_row("s1", "report")])
    frame["ACL"] = 0.5

    with pytest.raises(ValueError, match="outside"):
        validate_labeled_studies(frame)


@pytest.mark.parametrize("report", [None, 5])
def test_validate_labeled_studies_rejects_missing_or_non_string_report(report: object) -> None:
    frame = pd.DataFrame([_row("s1", report)])

    with pytest.raises(ValueError, match="missing or non-string Report"):
        validate_labeled_studies(frame)


def test_validate_labeled_studies_rejects_whitespace_only_report() -> None:
    frame = pd.DataFrame([_row("s1", "   ")])

    with pytest.raises(ValueError, match="empty after stripping"):
        validate_labeled_studies(frame)


def test_validate_labeled_studies_rejects_numpy_bool_value() -> None:
    frame = pd.DataFrame([_row("s1", "report")])
    frame["ACL"] = pd.Series([np.bool_(True)], dtype=object)

    with pytest.raises(ValueError, match="outside"):
        validate_labeled_studies(frame)
