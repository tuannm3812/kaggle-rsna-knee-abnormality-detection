import numpy as np
import pandas as pd
import pytest

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.submission import build_submission


def _submission_inputs() -> tuple[pd.DataFrame, pd.Series]:
    test_ids = pd.Series(["test_0", "test_1"], name="StudyInstanceUID")
    sample_df = pd.DataFrame(
        {
            "StudyInstanceUID": test_ids,
            **dict.fromkeys(LABEL_COLUMNS, 0.0),
        }
    )
    return sample_df, test_ids


def test_build_submission_preserves_schema_and_identifier_order() -> None:
    sample_df, test_ids = _submission_inputs()
    original_sample = sample_df.copy(deep=True)
    probabilities = np.full((len(test_ids), len(LABEL_COLUMNS)), 0.25)

    result = build_submission(sample_df, test_ids, probabilities)

    assert list(result.columns) == ["StudyInstanceUID", *LABEL_COLUMNS]
    assert result["StudyInstanceUID"].tolist() == test_ids.tolist()
    np.testing.assert_allclose(result[LABEL_COLUMNS], probabilities)
    pd.testing.assert_frame_equal(sample_df, original_sample)


@pytest.mark.parametrize(
    "columns",
    [
        ["StudyInstanceUID", *reversed(LABEL_COLUMNS)],
        ["StudyInstanceUID", *LABEL_COLUMNS[:-1]],
        ["StudyInstanceUID", *LABEL_COLUMNS, "extra"],
    ],
)
def test_build_submission_rejects_wrong_sample_schema(columns: list[str]) -> None:
    sample_df, test_ids = _submission_inputs()
    sample_df = sample_df.reindex(columns=columns)
    probabilities = np.full((len(test_ids), len(LABEL_COLUMNS)), 0.25)

    with pytest.raises(ValueError, match="canonical schema"):
        build_submission(sample_df, test_ids, probabilities)


def test_build_submission_rejects_row_count_mismatch() -> None:
    sample_df, test_ids = _submission_inputs()

    with pytest.raises(ValueError, match="row counts differ"):
        build_submission(sample_df.iloc[:1], test_ids, np.full((2, 12), 0.25))


@pytest.mark.parametrize("source", ["sample", "test"])
def test_build_submission_rejects_null_identifiers(source: str) -> None:
    sample_df, test_ids = _submission_inputs()
    if source == "sample":
        sample_df.loc[0, "StudyInstanceUID"] = None
    else:
        test_ids = test_ids.astype(object)
        test_ids.loc[0] = None

    with pytest.raises(ValueError, match="non-null"):
        build_submission(sample_df, test_ids, np.full((2, 12), 0.25))


@pytest.mark.parametrize("source", ["sample", "test"])
def test_build_submission_rejects_duplicate_identifiers(source: str) -> None:
    sample_df, test_ids = _submission_inputs()
    if source == "sample":
        sample_df.loc[1, "StudyInstanceUID"] = sample_df.loc[0, "StudyInstanceUID"]
    else:
        test_ids.loc[1] = test_ids.loc[0]

    with pytest.raises(ValueError, match="unique"):
        build_submission(sample_df, test_ids, np.full((2, 12), 0.25))


def test_build_submission_rejects_identifier_reordering() -> None:
    sample_df, test_ids = _submission_inputs()
    sample_df = sample_df.iloc[::-1].reset_index(drop=True)

    with pytest.raises(ValueError, match="match test order"):
        build_submission(sample_df, test_ids, np.full((2, 12), 0.25))


@pytest.mark.parametrize("shape", [(1, 12), (2, 11), (2, 13)])
def test_build_submission_rejects_wrong_probability_shape(shape: tuple[int, int]) -> None:
    sample_df, test_ids = _submission_inputs()

    with pytest.raises(ValueError, match="wrong shape"):
        build_submission(sample_df, test_ids, np.full(shape, 0.25))


@pytest.mark.parametrize("invalid_value", [np.nan, np.inf, -0.01, 1.01])
def test_build_submission_rejects_invalid_probability(invalid_value: float) -> None:
    sample_df, test_ids = _submission_inputs()
    probabilities = np.full((2, 12), 0.25)
    probabilities[0, 0] = invalid_value

    with pytest.raises(ValueError, match=r"finite and within \[0, 1\]"):
        build_submission(sample_df, test_ids, probabilities)
