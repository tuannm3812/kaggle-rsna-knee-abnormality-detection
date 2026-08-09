import pandas as pd
import pytest

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.weak_label_evaluation import (
    MIN_PRECISION_LOWER_BOUND,
    MIN_SUPPORT,
    _wilson_interval,
    orthographic_bucket,
    weak_label_metrics,
)


def _true_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _row(study_id: str, report: str, **labels: int) -> dict:
    row = {"StudyInstanceUID": study_id, "Report": report}
    row.update(dict.fromkeys(LABEL_COLUMNS, 0))
    row.update(labels)
    return row


def _constant_extractor(value):
    def extractor(report_text: str) -> dict[str, int | None]:
        return dict.fromkeys(LABEL_COLUMNS, value)

    return extractor


# -- _wilson_interval --


def test_wilson_interval_reference_value():
    lower, upper = _wilson_interval(k=5, n=5)

    assert lower == pytest.approx(0.5655, abs=1e-3)
    assert upper <= 1.0 + 1e-9
    assert upper > 0.99


def test_wilson_interval_zero_support_returns_zero():
    assert _wilson_interval(k=0, n=0) == (0.0, 0.0)


# -- weak_label_metrics: confusion counts, support, rates --


def test_weak_label_metrics_confusion_counts_and_rates():
    def extractor(report_text: str) -> dict[str, int | None]:
        predictions = dict.fromkeys(LABEL_COLUMNS, None)
        predictions["ACL"] = 1
        return predictions

    true_df = _true_df(
        [
            _row("s1", "report 1", ACL=1),
            _row("s2", "report 2", ACL=0),
        ]
    )

    metrics = weak_label_metrics(true_df, extractor)

    acl = metrics.loc["ACL"]
    assert acl["tp"] == 1
    assert acl["fp"] == 1
    assert acl["tn"] == 0
    assert acl["fn_confident"] == 0
    assert acl["abstained_on_positive"] == 0
    assert acl["abstained_on_negative"] == 0
    assert acl["predicted_positive_support"] == 2
    assert acl["actual_positive_support"] == 1
    assert acl["non_abstained_count"] == 2
    assert acl["total_rows"] == 2
    assert acl["precision"] == pytest.approx(0.5)
    assert acl["recall"] == pytest.approx(1.0)
    assert acl["coverage"] == pytest.approx(1.0)

    other_label = metrics.loc["MCL"]
    assert other_label["abstained_on_negative"] == 2
    assert other_label["coverage"] == pytest.approx(0.0)


def test_weak_label_metrics_zero_support_label_has_zero_metrics_no_exception():
    true_df = _true_df([_row("s1", "report", ACL=0)])

    metrics = weak_label_metrics(true_df, _constant_extractor(None))

    acl = metrics.loc["ACL"]
    assert acl["precision"] == 0.0
    assert acl["recall"] == 0.0
    assert acl["precision_ci_low"] == 0.0
    assert acl["precision_ci_high"] == 0.0
    assert not acl["passes_gate"]


def test_weak_label_metrics_wilson_interval_reference_value():
    def extractor(report_text: str) -> dict[str, int | None]:
        predictions = dict.fromkeys(LABEL_COLUMNS, None)
        predictions["ACL"] = 1
        return predictions

    true_df = _true_df([_row(f"s{i}", f"report {i}", ACL=1) for i in range(5)])

    metrics = weak_label_metrics(true_df, extractor)

    acl = metrics.loc["ACL"]
    assert acl["precision"] == pytest.approx(1.0)
    assert acl["precision_ci_low"] == pytest.approx(0.5655, abs=1e-3)


def test_weak_label_metrics_passes_gate_true_when_support_and_precision_clear():
    def extractor(report_text: str) -> dict[str, int | None]:
        predictions = dict.fromkeys(LABEL_COLUMNS, None)
        predictions["ACL"] = 1
        return predictions

    true_df = _true_df([_row(f"s{i}", f"report {i}", ACL=1) for i in range(MIN_SUPPORT)])

    metrics = weak_label_metrics(true_df, extractor)

    assert metrics.loc["ACL", "passes_gate"]


def test_weak_label_metrics_passes_gate_false_below_min_support():
    def extractor(report_text: str) -> dict[str, int | None]:
        predictions = dict.fromkeys(LABEL_COLUMNS, None)
        predictions["ACL"] = 1
        return predictions

    true_df = _true_df(
        [_row(f"s{i}", f"report {i}", ACL=1) for i in range(MIN_SUPPORT - 1)]
    )

    metrics = weak_label_metrics(true_df, extractor)

    assert not metrics.loc["ACL", "passes_gate"]


def test_weak_label_metrics_passes_gate_false_when_precision_lower_bound_too_low():
    def extractor(report_text: str) -> dict[str, int | None]:
        predictions = dict.fromkeys(LABEL_COLUMNS, None)
        predictions["ACL"] = 1
        return predictions

    true_df = _true_df(
        [_row(f"s{i}", f"report {i}", ACL=1) for i in range(2)]
        + [_row(f"s{i}", f"report {i}", ACL=0) for i in range(2, 5)]
    )

    metrics = weak_label_metrics(true_df, extractor)

    assert not metrics.loc["ACL", "passes_gate"]
    assert metrics.loc["ACL", "precision_ci_low"] < MIN_PRECISION_LOWER_BOUND


# -- weak_label_metrics: true_df schema validation --


def test_weak_label_metrics_raises_on_missing_column():
    true_df = pd.DataFrame([{"StudyInstanceUID": "s1", "Report": "r"}])

    with pytest.raises(ValueError, match="missing required columns"):
        weak_label_metrics(true_df, _constant_extractor(None))


def test_weak_label_metrics_raises_on_empty_input():
    true_df = pd.DataFrame(columns=["StudyInstanceUID", "Report", *LABEL_COLUMNS])

    with pytest.raises(ValueError, match="zero rows"):
        weak_label_metrics(true_df, _constant_extractor(None))


def test_weak_label_metrics_raises_on_duplicate_study_id():
    true_df = _true_df([_row("s1", "report a"), _row("s1", "report b")])

    with pytest.raises(ValueError, match="duplicate StudyInstanceUID"):
        weak_label_metrics(true_df, _constant_extractor(None))


def test_weak_label_metrics_raises_on_non_binary_label_value():
    true_df = _true_df([_row("s1", "report")])
    true_df.loc[0, "ACL"] = 2

    with pytest.raises(ValueError, match="outside"):
        weak_label_metrics(true_df, _constant_extractor(None))


def test_weak_label_metrics_raises_on_missing_report():
    true_df = _true_df([_row("s1", "report")])
    true_df.loc[0, "Report"] = None

    with pytest.raises(ValueError, match="missing or non-string Report"):
        weak_label_metrics(true_df, _constant_extractor(None))


# -- weak_label_metrics: extractor output validation --


def test_weak_label_metrics_raises_on_extractor_wrong_keys():
    true_df = _true_df([_row("s1", "report")])

    def bad_extractor(report_text: str) -> dict[str, int | None]:
        return {"NotALabel": 1}

    with pytest.raises(ValueError, match="do not match LABEL_COLUMNS"):
        weak_label_metrics(true_df, bad_extractor)


def test_weak_label_metrics_raises_on_extractor_invalid_value():
    true_df = _true_df([_row("s1", "report")])

    def bad_extractor(report_text: str) -> dict[str, int | None]:
        predictions = dict.fromkeys(LABEL_COLUMNS, None)
        predictions["ACL"] = 2
        return predictions

    with pytest.raises(ValueError, match="invalid value"):
        weak_label_metrics(true_df, bad_extractor)


# -- orthographic_bucket --


def test_orthographic_bucket_greek_script():
    assert orthographic_bucket("Ευρήματα φυσιολογικά") == "greek_script"


def test_orthographic_bucket_turkish_chars():
    assert orthographic_bucket("SAĞ DİZ MRG bulgular") == "latin_with_turkish_chars"


def test_orthographic_bucket_german_turkish_umlaut():
    # "Kein Hinweis auf Fraktur" was checked and rejected as a fixture --
    # it contains no umlaut characters at all and would actually
    # classify as ascii_only, not this bucket.
    assert orthographic_bucket("Knöchel unauffällig") == "latin_with_german_turkish_umlaut"


def test_orthographic_bucket_south_slavic_diacritics():
    assert (
        orthographic_bucket("Prikazane koštane strukture") == "latin_with_south_slavic_diacritics"
    )


def test_orthographic_bucket_mixed_latin_diacritics():
    assert orthographic_bucket("ö and š together") == "mixed_latin_diacritics"


def test_orthographic_bucket_ascii_only():
    assert orthographic_bucket("Normal knee MRI, no significant findings.") == "ascii_only"


def test_orthographic_bucket_other_latin_undetermined():
    assert orthographic_bucket("Café résumé naïve") == "other_latin_undetermined"
