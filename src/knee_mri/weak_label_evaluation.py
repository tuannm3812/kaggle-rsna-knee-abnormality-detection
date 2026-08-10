"""Score weak-label extractors against ground truth.

Scores a 3-state (positive/negative/abstain) weak-label extractor
against the 58 human-labeled studies, producing a per-label
precision/recall/coverage table gated by a Wilson-interval-based
per-label allowlist. See
docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md for
the full design and the reasoning behind every threshold below.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping

import pandas as pd

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.validation import validate_labeled_studies

# Frozen decision-rule constants -- set before any real result was
# viewed (see the design spec's "Decision rule" section for the
# reasoning, including why 0.55 and not a rounder number).
MIN_SUPPORT = 5
MIN_PRECISION_LOWER_BOUND = 0.55

_Z = 1.959963985  # 95% two-tailed


def _wilson_interval(k: int, n: int) -> tuple[float, float]:
    """95% Wilson score confidence interval for a proportion k/n.

    Closed-form calculation (no statsmodels dependency). Returns
    (0.0, 0.0) when n == 0 (undefined), matching this module's
    convention of returning 0.0 rather than raising for zero-support
    metrics.

    Args:
        k: Number of successes.
        n: Number of trials.

    Returns:
        A (lower, upper) tuple.
    """
    if n == 0:
        return 0.0, 0.0
    p_hat = k / n
    denom = 1 + _Z**2 / n
    center = (p_hat + _Z**2 / (2 * n)) / denom
    margin = (_Z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + _Z**2 / (4 * n**2))
    return center - margin, center + margin


def _validate_extractor_output(prediction_map: Mapping[str, int | None]) -> None:
    if set(prediction_map.keys()) != set(LABEL_COLUMNS):
        raise ValueError(
            f"extractor output keys {sorted(prediction_map.keys())} do not match LABEL_COLUMNS"
        )
    for value in prediction_map.values():
        # `type(value) is int` (not `isinstance`/`in`) so bool (a subclass
        # of int, `True in (0, 1, None)` == True) and float (`1.0 in (0,
        # 1, None)` == True too, via `==`) are rejected, not silently
        # accepted.
        if value is not None and (type(value) is not int or value not in (0, 1)):
            raise ValueError(
                f"extractor output contains invalid value: {value!r} (expected 0, 1, or None)"
            )


def weak_label_metrics(
    true_df: pd.DataFrame,
    extractor: Callable[[str], Mapping[str, int | None]],
) -> pd.DataFrame:
    """Score a weak-label extractor against ground-truth labels.

    For each of the 12 LABEL_COLUMNS, runs `extractor` on every row's
    Report and compares the result to that row's true label.

    Per-row prediction is one of {1, 0, None}; truth is {0, 1}.
    Confusion counts:
        tp = predicted 1, true 1
        fp = predicted 1, true 0
        tn = predicted 0, true 0
        fn_confident = predicted 0, true 1
        abstained_on_positive = predicted None, true 1
        abstained_on_negative = predicted None, true 0

    Reported support quantities (kept separate and unambiguous, each
    used as the correct denominator for its own metric/interval):
        actual_positive_support = tp + fn_confident + abstained_on_positive
        predicted_positive_support = tp + fp
        non_abstained_count = tp + fp + tn + fn_confident
        total_rows = len(true_df)

    precision = tp / predicted_positive_support
    recall = tp / actual_positive_support
    coverage = non_abstained_count / total_rows

    Precision/recall/coverage are 0.0 (not an error) when their
    denominator is 0 -- unlike metrics.py::per_label_auc, which
    intentionally raises on a degenerate single-class column (a
    different metric with a different degenerate case).

    Also computes a Wilson score 95% confidence interval for precision
    (n=predicted_positive_support, k=tp) and recall
    (n=actual_positive_support, k=tp) per label, and a boolean
    `passes_gate`: True iff predicted_positive_support >= MIN_SUPPORT
    and the Wilson lower bound of precision is >=
    MIN_PRECISION_LOWER_BOUND. Gated per label, never averaged.

    Validates true_df before scoring anything, and raises ValueError on:
      - true_df missing StudyInstanceUID, Report, or any LABEL_COLUMNS
        column
      - true_df has zero rows
      - a null or duplicate StudyInstanceUID
      - any LABEL_COLUMNS value that isn't exactly 0 or 1 (including NaN)
      - a missing, non-string, or whitespace-only Report value
    Also validates `extractor`'s output on every call: raises ValueError
    if the returned mapping's keys are not exactly LABEL_COLUMNS, or if
    any value is not in {0, 1, None}.

    Args:
        true_df: A frame with StudyInstanceUID, Report, and all 12
            LABEL_COLUMNS as ground-truth 0/1 values (e.g. the labeled
            subset of train.csv from split_labeled_studies).
        extractor: A weak-label extractor function with the same
            signature as extract_weak_labels (e.g.
            extract_weak_labels_naive or extract_weak_labels itself) --
            passed explicitly so the same function can score either
            extractor from the same published package in the same run.

    Returns:
        A DataFrame indexed by label, one row per LABEL_COLUMNS entry,
        with columns tp, fp, tn, fn_confident, abstained_on_positive,
        abstained_on_negative, actual_positive_support,
        predicted_positive_support, non_abstained_count, total_rows,
        precision, recall, coverage, precision_ci_low,
        precision_ci_high, recall_ci_low, recall_ci_high, passes_gate.

    Raises:
        ValueError: On any of the schema violations above, for either
            true_df or the extractor's output.
    """
    validate_labeled_studies(true_df)

    counts = {
        label: {
            "tp": 0,
            "fp": 0,
            "tn": 0,
            "fn_confident": 0,
            "abstained_on_positive": 0,
            "abstained_on_negative": 0,
        }
        for label in LABEL_COLUMNS
    }

    for _, row in true_df.iterrows():
        prediction_map = extractor(row["Report"])
        _validate_extractor_output(prediction_map)
        for label in LABEL_COLUMNS:
            prediction = prediction_map[label]
            truth = row[label]
            c = counts[label]
            if prediction == 1 and truth == 1:
                c["tp"] += 1
            elif prediction == 1 and truth == 0:
                c["fp"] += 1
            elif prediction == 0 and truth == 0:
                c["tn"] += 1
            elif prediction == 0 and truth == 1:
                c["fn_confident"] += 1
            elif prediction is None and truth == 1:
                c["abstained_on_positive"] += 1
            elif prediction is None and truth == 0:
                c["abstained_on_negative"] += 1

    total_rows = len(true_df)
    records = []
    for label in LABEL_COLUMNS:
        c = counts[label]
        actual_positive_support = c["tp"] + c["fn_confident"] + c["abstained_on_positive"]
        predicted_positive_support = c["tp"] + c["fp"]
        non_abstained_count = c["tp"] + c["fp"] + c["tn"] + c["fn_confident"]

        precision = c["tp"] / predicted_positive_support if predicted_positive_support else 0.0
        recall = c["tp"] / actual_positive_support if actual_positive_support else 0.0
        coverage = non_abstained_count / total_rows

        precision_ci_low, precision_ci_high = _wilson_interval(c["tp"], predicted_positive_support)
        recall_ci_low, recall_ci_high = _wilson_interval(c["tp"], actual_positive_support)

        passes_gate = (
            predicted_positive_support >= MIN_SUPPORT
            and precision_ci_low >= MIN_PRECISION_LOWER_BOUND
        )

        records.append(
            {
                "label": label,
                "tp": c["tp"],
                "fp": c["fp"],
                "tn": c["tn"],
                "fn_confident": c["fn_confident"],
                "abstained_on_positive": c["abstained_on_positive"],
                "abstained_on_negative": c["abstained_on_negative"],
                "actual_positive_support": actual_positive_support,
                "predicted_positive_support": predicted_positive_support,
                "non_abstained_count": non_abstained_count,
                "total_rows": total_rows,
                "precision": precision,
                "recall": recall,
                "coverage": coverage,
                "precision_ci_low": precision_ci_low,
                "precision_ci_high": precision_ci_high,
                "recall_ci_low": recall_ci_low,
                "recall_ci_high": recall_ci_high,
                "passes_gate": passes_gate,
            }
        )

    return pd.DataFrame(records).set_index("label")


_GREEK_SCRIPT_RE = re.compile(r"[Ͱ-Ͽἀ-῿]")
# Explicit case variants, not re.IGNORECASE: Python's Unicode case-folding
# treats Turkish dotted-capital "İ" (U+0130) as fold-equivalent to plain
# ASCII "i"/"I", which made re.IGNORECASE match ordinary English text
# (e.g. "MRI") -- caught by an implementer's test run, not reasoned out
# in review. Turkish's dotted/dotless I pairs aren't the simple ASCII
# casing relationship anyway, so IGNORECASE was never semantically right
# here.
_TURKISH_CHARS_RE = re.compile(r"[ğĞşŞıİ]")
_GERMAN_TURKISH_UMLAUT_RE = re.compile(r"[äöüßÄÖÜ]")
_SOUTH_SLAVIC_DIACRITICS_RE = re.compile(r"[čćđšžČĆĐŠŽ]")
_ASCII_ONLY_RE = re.compile(r"^[\x00-\x7F]*$")


def orthographic_bucket(text: str) -> str:
    """Classify text into a coarse, honestly-named character-set bucket.

    Explicitly NOT language identification -- bucket names describe
    observed character sets, not claimed languages (e.g. German and
    Turkish share the umlaut characters this checks for). See
    docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md
    section 5 for the full reasoning.

    Args:
        text: Any text (report text on Kaggle; never committed here).

    Returns:
        One of: "greek_script", "latin_with_turkish_chars",
        "latin_with_german_turkish_umlaut",
        "latin_with_south_slavic_diacritics", "mixed_latin_diacritics",
        "ascii_only", "other_latin_undetermined".
    """
    if _GREEK_SCRIPT_RE.search(text):
        return "greek_script"

    matched = []
    if _TURKISH_CHARS_RE.search(text):
        matched.append("latin_with_turkish_chars")
    if _GERMAN_TURKISH_UMLAUT_RE.search(text):
        matched.append("latin_with_german_turkish_umlaut")
    if _SOUTH_SLAVIC_DIACRITICS_RE.search(text):
        matched.append("latin_with_south_slavic_diacritics")

    if len(matched) > 1:
        return "mixed_latin_diacritics"
    if len(matched) == 1:
        return matched[0]

    if _ASCII_ONLY_RE.match(text):
        return "ascii_only"

    return "other_latin_undetermined"
