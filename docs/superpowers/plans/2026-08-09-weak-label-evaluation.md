# Weak-Label Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved weak-label evaluation design: a 3-state, clause-scoped, assertion-aware `extract_weak_labels`; a `weak_label_metrics` scoring function with a Wilson-interval-gated per-label allowlist; and the Kaggle-only evaluation notebook that measures both the old and new extractor against the 58 real labeled studies.

**Architecture:** Two extractor functions (`extract_weak_labels_naive` frozen as the historical baseline, `extract_weak_labels` the new fixed version) coexist in `src/knee_mri/labels.py`, both built on the same `_LABEL_PATTERNS` keyword list. `weak_label_metrics` (new module `weak_label_evaluation.py`) takes an extractor as an explicit parameter so the same scoring function evaluates both from one published package in one Kaggle run. All logic is tested locally against synthetic fixtures; the notebook that touches real report text is Kaggle-only and committed output-free.

**Tech Stack:** Python 3.11+, existing `uv`/`pyproject.toml` project (no new dependencies — the Wilson interval is a directly-implemented closed-form calculation).

## Global Constraints

- Package: `knee_mri`; all new code lives in `src/knee_mri/`.
- `LABEL_COLUMNS` order is unchanged: `ACL, MCL, Medial Meniscus, Lateral Meniscus, Medial OA, Lateral OA, PF OA, Effusion, Synovitis, Baker's, Contusion, Fracture`.
- `extract_weak_labels_naive` is the **frozen, unmodified** historical extractor (`dict[str, int]`) — do not change its logic, only its name.
- `extract_weak_labels` is the **new** 3-state extractor (`dict[str, int | None]`), a thin projection over the internal `_resolve_weak_labels` resolver.
- Cue lists (negation/normal-assertion/uncertain) are intentionally English-only for this pass — do not add other languages.
- No new runtime dependencies — Wilson interval is a direct closed-form implementation, not `statsmodels`.
- Frozen decision-rule constants: `MIN_SUPPORT = 5`, `MIN_PRECISION_LOWER_BOUND = 0.55`.
- `weak_label_metrics`'s per-label gate (`passes_gate`) is independent per label — never averaged across labels.
- The error taxonomy is purely observational (`resolution_signature`, `prediction_error`) — never attach a causal label to a bucket.
- Kaggle-only execution: tests use only small synthetic fixtures, never real competition data. The notebook this plan scaffolds is not executed as part of this plan — that's an interactive follow-up (same pattern as `01_eda.ipynb`).
- The notebook is committed **output-free**, always — unlike `01_eda.ipynb`, this rule has no "once trusted" exception, because its cells touch real report text.

---

### Task 1: `src/knee_mri/labels.py` — 3-state extractor with clause-scoped assertion detection

**Files:**
- Modify: `src/knee_mri/labels.py`
- Modify: `tests/test_labels.py`

**Interfaces:**
- Produces: `LABEL_COLUMNS` (unchanged), `extract_weak_labels_naive(report_text: str) -> dict[str, int]` (renamed, unchanged logic), `extract_weak_labels(report_text: str) -> dict[str, int | None]` (new), `MentionDiagnostic`, `LabelResolution` dataclasses, `_resolve_weak_labels(report_text: str) -> dict[str, LabelResolution]`, `_resolution_signature(mentions: tuple[MentionDiagnostic, ...]) -> str`. Consumed by Task 2 (`weak_label_metrics` takes `extract_weak_labels_naive`/`extract_weak_labels` as its `extractor` parameter) and Task 3 (notebook imports `extract_weak_labels_naive`, `extract_weak_labels`, `_resolve_weak_labels`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_labels.py`:

```python
from knee_mri.labels import (
    LABEL_COLUMNS,
    LabelResolution,
    MentionDiagnostic,
    _resolution_signature,
    _resolve_value,
    _resolve_weak_labels,
    extract_weak_labels,
    extract_weak_labels_naive,
)


def test_label_columns_matches_submission_header():
    assert LABEL_COLUMNS == [
        "ACL",
        "MCL",
        "Medial Meniscus",
        "Lateral Meniscus",
        "Medial OA",
        "Lateral OA",
        "PF OA",
        "Effusion",
        "Synovitis",
        "Baker's",
        "Contusion",
        "Fracture",
    ]


# -- extract_weak_labels_naive: frozen baseline, unchanged behavior --


def test_extract_weak_labels_naive_detects_multiple_findings():
    report = (
        "There is a complete tear of the ACL. Moderate joint effusion is "
        "present. Medial meniscus appears intact. No fracture."
    )

    labels = extract_weak_labels_naive(report)

    assert labels["ACL"] == 1
    assert labels["Effusion"] == 1
    assert labels["Medial Meniscus"] == 1  # regex has no negation handling
    assert labels["Fracture"] == 1  # regex has no negation handling


def test_extract_weak_labels_naive_returns_all_columns_even_with_no_matches():
    labels = extract_weak_labels_naive("Normal knee MRI, no significant findings.")

    assert set(labels.keys()) == set(LABEL_COLUMNS)
    assert all(value in (0, 1) for value in labels.values())
    assert sum(labels.values()) == 0


# -- extract_weak_labels: new assertion-aware behavior --


def test_extract_weak_labels_unqualified_mention_is_positive():
    labels = extract_weak_labels("There is a complete tear of the ACL.")

    assert labels["ACL"] == 1


def test_extract_weak_labels_negated_mention_is_negative():
    labels = extract_weak_labels("No fracture is seen.")

    assert labels["Fracture"] == 0


def test_extract_weak_labels_post_match_cue_heading_colon():
    # The exact "ACL: intact" case round-6 review found broken by naive
    # ':'-splitting -- the cue follows the keyword, in the same "clause"
    # only because ':' is not a clause boundary.
    labels = extract_weak_labels("ACL: intact.")

    assert labels["ACL"] == 0


def test_extract_weak_labels_uncertain_cue_abstains():
    labels = extract_weak_labels("Rule out fracture in this region.")

    assert labels["Fracture"] is None


def test_extract_weak_labels_substring_trap_does_not_trigger_negation():
    # "notable" must never match the "no" cue -- no word boundary
    # between "no" and "table" inside "notable".
    labels = extract_weak_labels("Effusion is notable in the joint.")

    assert labels["Effusion"] == 1


def test_extract_weak_labels_cue_does_not_leak_across_clause_boundary():
    labels = extract_weak_labels("No fracture is seen. ACL is torn.")

    assert labels["Fracture"] == 0
    assert labels["ACL"] == 1


def test_extract_weak_labels_repeated_concordant_mentions_stay_positive():
    labels = extract_weak_labels(
        "The ACL is torn. Findings of ACL tear are confirmed."
    )

    assert labels["ACL"] == 1


def test_extract_weak_labels_abstains_on_all_labels_with_no_mentions():
    labels = extract_weak_labels("Normal knee MRI, no significant findings.")

    assert set(labels.keys()) == set(LABEL_COLUMNS)
    assert all(value is None for value in labels.values())


# -- _resolve_weak_labels: internal resolver, full LabelResolution detail --


def test_resolve_weak_labels_unqualified_mention():
    resolution = _resolve_weak_labels("There is a complete tear of the ACL.")["ACL"]

    assert resolution == LabelResolution(
        value=1, mentions=(MentionDiagnostic(kind="unqualified", clause_index=0),)
    )


def test_resolve_weak_labels_negated_mention():
    resolution = _resolve_weak_labels("No fracture is seen.")["Fracture"]

    assert resolution == LabelResolution(
        value=0,
        mentions=(MentionDiagnostic(kind="qualified_negation", clause_index=0),),
    )


def test_resolve_weak_labels_normal_assertion_mention():
    resolution = _resolve_weak_labels("ACL: intact.")["ACL"]

    assert resolution == LabelResolution(
        value=0,
        mentions=(MentionDiagnostic(kind="qualified_normal_assertion", clause_index=0),),
    )


def test_resolve_weak_labels_uncertain_mention():
    resolution = _resolve_weak_labels("Rule out fracture in this region.")["Fracture"]

    assert resolution == LabelResolution(
        value=None,
        mentions=(MentionDiagnostic(kind="qualified_uncertain", clause_index=0),),
    )


def test_resolve_weak_labels_no_mention():
    resolution = _resolve_weak_labels("Normal knee MRI, no significant findings.")["ACL"]

    assert resolution == LabelResolution(value=None, mentions=())


# -- _resolution_signature / _resolve_value: the invariant the error
# taxonomy in the evaluation notebook depends on --


def test_resolution_signature_and_value_are_consistent_for_every_signature():
    """For every one of the six resolution_signature values, confirm the
    value is consistent with exactly one direction of error:
    unqualified_only is the only signature that can ever produce
    value=1 (and therefore a false positive); every other signature
    produces 0 or None (and therefore, when wrong, only a false
    negative). A future change to the resolution order must not
    silently invalidate this without breaking this test."""
    no_mention: tuple[MentionDiagnostic, ...] = ()
    only_unqualified = (MentionDiagnostic(kind="unqualified", clause_index=0),)
    only_negation = (MentionDiagnostic(kind="qualified_negation", clause_index=0),)
    only_normal = (MentionDiagnostic(kind="qualified_normal_assertion", clause_index=0),)
    only_uncertain = (MentionDiagnostic(kind="qualified_uncertain", clause_index=0),)
    mixed = (
        MentionDiagnostic(kind="unqualified", clause_index=0),
        MentionDiagnostic(kind="qualified_negation", clause_index=1),
    )

    cases = [
        (no_mention, "no_mention"),
        (only_unqualified, "unqualified_only"),
        (only_negation, "negation_qualified"),
        (only_normal, "normal_qualified"),
        (only_uncertain, "uncertain_qualified"),
        (mixed, "mixed_qualification"),
    ]

    for mentions, expected_signature in cases:
        signature = _resolution_signature(mentions)
        value = _resolve_value(mentions)

        assert signature == expected_signature
        if signature == "unqualified_only":
            assert value == 1
        else:
            assert value != 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_labels.py -v`
Expected: FAIL — `ImportError` (`extract_weak_labels_naive`, `LabelResolution`, etc. don't exist yet) or `AttributeError`/wrong-return-type failures against the current `extract_weak_labels`.

- [ ] **Step 3: Rewrite `src/knee_mri/labels.py`**

```python
"""Report-derived weak labels and the canonical 12-target label schema."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

LABEL_COLUMNS: list[str] = [
    "ACL",
    "MCL",
    "Medial Meniscus",
    "Lateral Meniscus",
    "Medial OA",
    "Lateral OA",
    "PF OA",
    "Effusion",
    "Synovitis",
    "Baker's",
    "Contusion",
    "Fracture",
]

# One or more regex patterns per label; a match anywhere in the report
# (case-insensitive) counts as a mention of that label.
_LABEL_PATTERNS: dict[str, list[str]] = {
    "ACL": [r"\bacl\b", r"anterior cruciate ligament"],
    "MCL": [r"\bmcl\b", r"medial collateral ligament"],
    "Medial Meniscus": [r"medial meniscus"],
    "Lateral Meniscus": [r"lateral meniscus"],
    "Medial OA": [r"medial.{0,20}(osteoarthritis|compartment.{0,10}oa)"],
    "Lateral OA": [r"lateral.{0,20}(osteoarthritis|compartment.{0,10}oa)"],
    "PF OA": [r"patellofemoral.{0,20}(osteoarthritis|oa)", r"\bpf oa\b"],
    "Effusion": [r"effusion"],
    "Synovitis": [r"synovitis"],
    "Baker's": [r"baker'?s? cyst", r"popliteal cyst"],
    "Contusion": [r"contusion", r"bone bruise"],
    "Fracture": [r"fracture"],
}

_COMPILED_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    label: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for label, patterns in _LABEL_PATTERNS.items()
}

# Clause boundaries for assertion-detection scoping. ':' is deliberately
# excluded -- it would incorrectly split a common heading form like
# "ACL: intact" into two clauses, leaving the keyword's own clause with
# no cue to find.
_CLAUSE_SPLIT_RE = re.compile(r"[.;\n]")

# How far (in characters, each direction, within the same clause) to
# search around a keyword match for a qualifying cue.
_WINDOW_RADIUS = 40

# Cue lists are intentionally English-only for this pass -- see
# docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md,
# "Out of scope". All patterns are word/phrase-bounded so a cue can
# never match as a substring of an unrelated word (e.g. "no" inside
# "notable").
_NEGATION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [r"\bno\b", r"\bnot\b", r"\bwithout\b", r"\bnegative for\b", r"\babsence of\b"]
]
_NORMAL_ASSERTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bintact\b",
        r"\bpreserved\b",
        r"\bunremarkable\b",
        r"\bnormal\b",
        r"\bwithin normal limits\b",
    ]
]
_UNCERTAIN_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [r"\brule out\b", r"\br/o\b", r"\bquestion of\b", r"\bpossible\b", r"\bcannot exclude\b"]
]

MentionKind = Literal[
    "unqualified",
    "qualified_negation",
    "qualified_uncertain",
    "qualified_normal_assertion",
]


@dataclass(frozen=True)
class MentionDiagnostic:
    """One keyword match for a label, classified by nearby assertion cues.

    No clause text, matched text, character offsets, study identifiers,
    or the specific cue string are retained -- only the abstract `kind`
    and which clause (by index, not content) it came from.
    """

    kind: MentionKind
    clause_index: int


@dataclass(frozen=True)
class LabelResolution:
    """A label's resolved weak-label value plus the mentions behind it."""

    value: int | None
    mentions: tuple[MentionDiagnostic, ...]


def extract_weak_labels_naive(report_text: str) -> dict[str, int]:
    """Derive weak per-label findings from a free-text radiology report.

    Frozen historical baseline: the original weak-label extractor,
    unchanged. Keyword/regex matching only, no assertion detection --
    "no evidence of fracture" still matches "Fracture" as positive.
    Kept as-is so it can serve as the "before" measurement in the
    weak-label evaluation notebook (both this and extract_weak_labels
    are scored by knee_mri.weak_label_evaluation.weak_label_metrics from
    the same published package, in the same run). Superseded by
    extract_weak_labels for all other purposes.

    Args:
        report_text: The study's free-text radiology report.

    Returns:
        A dict mapping each of the 12 LABEL_COLUMNS to 0 or 1.
    """
    return {
        label: int(any(pattern.search(report_text) for pattern in patterns))
        for label, patterns in _COMPILED_PATTERNS.items()
    }


def _classify_mention(clause: str, start: int, end: int) -> MentionKind:
    """Classify one keyword match by searching a bounded window around it
    for a negation, normal-assertion, or uncertainty cue. Negation and
    normal-assertion are checked before uncertainty, matching the
    confident-qualification-dominates philosophy of the overall
    resolution order in _resolve_value.
    """
    window = clause[max(0, start - _WINDOW_RADIUS) : min(len(clause), end + _WINDOW_RADIUS)]
    if any(pattern.search(window) for pattern in _NEGATION_PATTERNS):
        return "qualified_negation"
    if any(pattern.search(window) for pattern in _NORMAL_ASSERTION_PATTERNS):
        return "qualified_normal_assertion"
    if any(pattern.search(window) for pattern in _UNCERTAIN_PATTERNS):
        return "qualified_uncertain"
    return "unqualified"


def _resolve_value(mentions: tuple[MentionDiagnostic, ...]) -> int | None:
    """Resolve a label's final value from its collected mention kinds.

    Resolution order (first matching rule wins):
    1. No mentions -> None (abstain).
    2. Any qualified_negation or qualified_normal_assertion mention
       present -> 0 (a confident qualification dominates everything
       else, including an unqualified mention elsewhere in the report).
    3. Else, any qualified_uncertain mention present -> None (abstain;
       uncertainty is not forced into a confident answer).
    4. Else (only unqualified mentions) -> 1.
    """
    if not mentions:
        return None
    kinds = {mention.kind for mention in mentions}
    if "qualified_negation" in kinds or "qualified_normal_assertion" in kinds:
        return 0
    if "qualified_uncertain" in kinds:
        return None
    return 1


def _resolution_signature(mentions: tuple[MentionDiagnostic, ...]) -> str:
    """Collapse a label's mention kinds into one of six mechanical
    signature values.

    Used by the weak-label evaluation notebook's error taxonomy. Purely
    a fact about which mention kinds were observed -- never asserts a
    cause for a mismatch; see
    docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md
    section 5.
    """
    if not mentions:
        return "no_mention"
    kinds = {mention.kind for mention in mentions}
    if len(kinds) > 1:
        return "mixed_qualification"
    (kind,) = kinds
    return {
        "unqualified": "unqualified_only",
        "qualified_negation": "negation_qualified",
        "qualified_normal_assertion": "normal_qualified",
        "qualified_uncertain": "uncertain_qualified",
    }[kind]


def _resolve_weak_labels(report_text: str) -> dict[str, LabelResolution]:
    """Same matching/clause logic as extract_weak_labels, but returns the
    full LabelResolution (value + mention diagnostics) per label instead
    of projecting to just the value. Internal -- imported directly by the
    evaluation notebook's diagnostic cell, not part of
    extract_weak_labels's public contract.

    Args:
        report_text: The study's free-text radiology report.

    Returns:
        A dict mapping each of the 12 LABEL_COLUMNS to its LabelResolution.
    """
    clauses = _CLAUSE_SPLIT_RE.split(report_text)
    resolutions: dict[str, LabelResolution] = {}
    for label, patterns in _COMPILED_PATTERNS.items():
        mentions: list[MentionDiagnostic] = []
        for clause_index, clause in enumerate(clauses):
            for pattern in patterns:
                for match in pattern.finditer(clause):
                    kind = _classify_mention(clause, match.start(), match.end())
                    mentions.append(MentionDiagnostic(kind=kind, clause_index=clause_index))
        resolutions[label] = LabelResolution(
            value=_resolve_value(tuple(mentions)), mentions=tuple(mentions)
        )
    return resolutions


def extract_weak_labels(report_text: str) -> dict[str, int | None]:
    """Derive weak per-label findings from a free-text radiology report.

    Clause-scoped, bidirectional, word-bounded assertion detection: a
    label's keyword match is checked for a nearby (same clause, within
    40 characters) negation, normal-assertion, or uncertainty cue.
    Confident qualification (negation/normal-assertion) resolves to 0;
    uncertainty resolves to abstain (None), same as no mention at all;
    an unqualified mention resolves to 1. See
    docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md
    section 2 for the full mechanism and its rationale.

    Cue lists are intentionally English-only for this pass -- see the
    design spec's "Out of scope" section.

    Args:
        report_text: The study's free-text radiology report.

    Returns:
        A dict mapping each of the 12 LABEL_COLUMNS to 1 (unqualified
        positive mention), 0 (confidently negated/normal), or None
        (abstain: no mention, or only uncertain evidence).
    """
    return {
        label: resolution.value for label, resolution in _resolve_weak_labels(report_text).items()
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_labels.py -v`
Expected: PASS (18 passed)

- [ ] **Step 5: Commit**

```bash
git add src/knee_mri/labels.py tests/test_labels.py
git commit -m "feat: add 3-state, clause-scoped assertion-aware extract_weak_labels"
```

---

### Task 2: `src/knee_mri/weak_label_evaluation.py` — Wilson interval, scoring, orthographic buckets

**Files:**
- Create: `src/knee_mri/weak_label_evaluation.py`
- Create: `tests/test_weak_label_evaluation.py`

**Interfaces:**
- Consumes: `LABEL_COLUMNS` from `knee_mri.labels` (Task 1). Callers pass `extract_weak_labels_naive`/`extract_weak_labels` as the `extractor` argument (Task 1), but this module has no direct import dependency on them.
- Produces: `MIN_SUPPORT: int`, `MIN_PRECISION_LOWER_BOUND: float`, `weak_label_metrics(true_df: pd.DataFrame, extractor: Callable[[str], Mapping[str, int | None]]) -> pd.DataFrame`, `orthographic_bucket(text: str) -> str`. Consumed by Task 3's notebook.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_weak_label_evaluation.py`:

```python
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
    assert orthographic_bucket("Prikazane koštane strukture") == "latin_with_south_slavic_diacritics"


def test_orthographic_bucket_mixed_latin_diacritics():
    assert orthographic_bucket("ö and š together") == "mixed_latin_diacritics"


def test_orthographic_bucket_ascii_only():
    assert orthographic_bucket("Normal knee MRI, no significant findings.") == "ascii_only"


def test_orthographic_bucket_other_latin_undetermined():
    assert orthographic_bucket("Café résumé naïve") == "other_latin_undetermined"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_weak_label_evaluation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'knee_mri.weak_label_evaluation'`

- [ ] **Step 3: Write `src/knee_mri/weak_label_evaluation.py`**

```python
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


def _validate_true_df(true_df: pd.DataFrame) -> None:
    required_columns = {"StudyInstanceUID", "Report", *LABEL_COLUMNS}
    missing = required_columns - set(true_df.columns)
    if missing:
        raise ValueError(f"true_df is missing required columns: {sorted(missing)}")
    if len(true_df) == 0:
        raise ValueError("true_df has zero rows")
    if true_df["StudyInstanceUID"].duplicated().any():
        raise ValueError("true_df has duplicate StudyInstanceUID values")
    for label in LABEL_COLUMNS:
        if not true_df[label].isin([0, 1]).all():
            raise ValueError(f"true_df column '{label}' has values outside {{0, 1}}")
    is_string = true_df["Report"].apply(lambda value: isinstance(value, str))
    if true_df["Report"].isna().any() or not is_string.all():
        raise ValueError("true_df has a missing or non-string Report value")


def _validate_extractor_output(prediction_map: Mapping[str, int | None]) -> None:
    if set(prediction_map.keys()) != set(LABEL_COLUMNS):
        raise ValueError(
            f"extractor output keys {sorted(prediction_map.keys())} do not match LABEL_COLUMNS"
        )
    for value in prediction_map.values():
        if value not in (0, 1, None):
            raise ValueError(f"extractor output contains invalid value: {value!r} (expected 0, 1, or None)")


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
      - a duplicate StudyInstanceUID
      - any LABEL_COLUMNS value that isn't exactly 0 or 1 (including NaN)
      - a missing or non-string Report value
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
    _validate_true_df(true_df)

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
            predicted_positive_support >= MIN_SUPPORT and precision_ci_low >= MIN_PRECISION_LOWER_BOUND
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
_TURKISH_CHARS_RE = re.compile(r"[ğşıİ]", re.IGNORECASE)
_GERMAN_TURKISH_UMLAUT_RE = re.compile(r"[äöüß]", re.IGNORECASE)
_SOUTH_SLAVIC_DIACRITICS_RE = re.compile(r"[čćđšž]", re.IGNORECASE)
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_weak_label_evaluation.py -v`
Expected: PASS (21 passed)

- [ ] **Step 5: Run the full suite and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: all tests pass (39 total: 18 in test_labels.py + 21 in test_weak_label_evaluation.py, plus the pre-existing test_dataset.py/test_dicom_io.py/test_metrics.py); ruff reports `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/knee_mri/weak_label_evaluation.py tests/test_weak_label_evaluation.py
git commit -m "feat: add weak_label_metrics (Wilson-gated per-label scoring) and orthographic_bucket"
```

---

### Task 3: `notebooks/02_weak_label_evaluation.ipynb` — evaluation notebook scaffold

**Files:**
- Create: `notebooks/02_weak_label_evaluation.ipynb`
- Create: `notebooks/kernels/weak-label-evaluation/kernel-metadata.json`

**Interfaces:**
- Consumes: `knee_mri.dataset.split_labeled_studies`, `knee_mri.labels.{extract_weak_labels_naive, extract_weak_labels, _resolve_weak_labels}` (Task 1), `knee_mri.weak_label_evaluation.{weak_label_metrics, orthographic_bucket}` (Task 2).
- Produces: the notebook Task 4 verifies is valid JSON, and that a human later pushes to Kaggle (not part of this plan — see "Out of scope" below).

- [ ] **Step 1: Write `notebooks/02_weak_label_evaluation.ipynb`**

```json
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Weak-Label Evaluation\n",
    "\n",
    "Measures `extract_weak_labels` (assertion-aware) against\n",
    "`extract_weak_labels_naive` (the original, unmodified extractor) on the\n",
    "58 human-labeled studies, and produces a per-label allowlist of which\n",
    "labels are trustworthy enough to weak-label the remaining 4349\n",
    "report-only studies with. Full design:\n",
    "`docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md`.\n",
    "\n",
    "**This notebook is committed output-free, always** (not just until a\n",
    "trusted run) -- its cells process real report text directly. Only\n",
    "aggregate counts/metrics are ever printed; no report excerpts, no\n",
    "per-study prediction tables, no study-identifier lists."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import random\n",
    "import sys\n",
    "from pathlib import Path\n",
    "\n",
    "import numpy as np\n",
    "import pandas as pd\n",
    "\n",
    "NOTEBOOK_VERSION = \"v1\"\n",
    "SEED = 42\n",
    "random.seed(SEED)\n",
    "np.random.seed(SEED)\n",
    "\n",
    "IS_KAGGLE = Path(\"/kaggle/input\").exists()\n",
    "\n",
    "if IS_KAGGLE:\n",
    "    DATA_DIR = Path(\"/kaggle/input/competitions/rsna-knee-abnormality-detection\")\n",
    "\n",
    "    SRC_DATASET_DIR = Path(\"/kaggle/input/datasets/tuannm3812/rsna-knee-mri-src\")\n",
    "    _src_candidates = (SRC_DATASET_DIR / \"src\", SRC_DATASET_DIR)\n",
    "    _src_root = next((c for c in _src_candidates if (c / \"knee_mri\").is_dir()), None)\n",
    "    if _src_root is None:\n",
    "        raise RuntimeError(\n",
    "            f\"knee_mri package not found under any of {[str(c) for c in _src_candidates]} \"\n",
    "            \"-- check the rsna-knee-mri-src dataset's actual mounted layout \"\n",
    "            \"(see docs/0_coding_standards.md, 'Pushing Notebooks To Kaggle') \"\n",
    "            \"and record it in docs/6_kaggle_troubleshooting.md.\"\n",
    "        )\n",
    "    sys.path.insert(0, str(_src_root))\n",
    "else:\n",
    "    raise RuntimeError(\n",
    "        \"This notebook only runs on Kaggle -- see docs/0_coding_standards.md \"\n",
    "        \"('Data & Compute'): the competition dataset is never downloaded \"\n",
    "        \"locally.\"\n",
    "    )\n",
    "\n",
    "print(f\"NOTEBOOK_VERSION={NOTEBOOK_VERSION}\")\n",
    "print(f\"IS_KAGGLE={IS_KAGGLE}\")\n",
    "print(f\"DATA_DIR={DATA_DIR}\")\n",
    "print(f\"SRC_ROOT={_src_root}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 1. Load the 58 labeled studies"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from knee_mri.dataset import split_labeled_studies\n",
    "\n",
    "train_df = pd.read_csv(DATA_DIR / \"train.csv\")\n",
    "labeled_df, unlabeled_df = split_labeled_studies(train_df)\n",
    "\n",
    "print(f\"Labeled studies: {len(labeled_df)}\")\n",
    "print(f\"Unlabeled (report-only) studies: {len(unlabeled_df)}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 2. Baseline measurement (naive, pre-fix extractor)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from knee_mri.labels import extract_weak_labels, extract_weak_labels_naive\n",
    "from knee_mri.weak_label_evaluation import weak_label_metrics\n",
    "\n",
    "baseline_metrics = weak_label_metrics(labeled_df, extract_weak_labels_naive)\n",
    "print(baseline_metrics)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "**Insight:** pending first Kaggle run."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 3. Fixed measurement (assertion-aware extractor)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "fixed_metrics = weak_label_metrics(labeled_df, extract_weak_labels)\n",
    "print(fixed_metrics)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "**Insight:** pending first Kaggle run."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 4. Error taxonomy (resolver diagnostics, counts only)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from collections import Counter\n",
    "\n",
    "from knee_mri.labels import LABEL_COLUMNS, _resolve_weak_labels, _resolution_signature\n",
    "from knee_mri.weak_label_evaluation import orthographic_bucket\n",
    "\n",
    "taxonomy_counts = Counter()\n",
    "for _, row in labeled_df.iterrows():\n",
    "    bucket = orthographic_bucket(row[\"Report\"])\n",
    "    resolutions = _resolve_weak_labels(row[\"Report\"])\n",
    "    for label in LABEL_COLUMNS:\n",
    "        resolution = resolutions[label]\n",
    "        truth = row[label]\n",
    "        prediction = resolution.value\n",
    "        is_error = (prediction == 1 and truth == 0) or (prediction != 1 and truth == 1)\n",
    "        if not is_error:\n",
    "            continue\n",
    "        prediction_error = \"false_positive\" if prediction == 1 else \"false_negative\"\n",
    "        signature = _resolution_signature(resolution.mentions)\n",
    "        taxonomy_counts[(label, bucket, signature, prediction_error)] += 1\n",
    "\n",
    "# Counts only -- never report text, matched text, or per-study identifiers.\n",
    "for key, count in sorted(taxonomy_counts.items()):\n",
    "    print(key, count)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "**Insight:** pending first Kaggle run. Any causal hypothesis about these\n",
    "counts belongs in `docs/4_experiments.md`, explicitly hedged as\n",
    "unconfirmed -- `resolution_signature` and `prediction_error` are\n",
    "directly observed facts, not an explanation of why the human label\n",
    "disagrees."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 5. Orthographic-bucket comparison (labeled vs. all unlabeled studies)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "labeled_buckets = labeled_df[\"Report\"].dropna().apply(orthographic_bucket).value_counts(normalize=True)\n",
    "unlabeled_buckets = unlabeled_df[\"Report\"].dropna().apply(orthographic_bucket).value_counts(normalize=True)\n",
    "\n",
    "comparison = pd.DataFrame({\"labeled\": labeled_buckets, \"unlabeled\": unlabeled_buckets}).fillna(0.0)\n",
    "print(comparison)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "**Insight:** pending first Kaggle run. If the labeled set's bucket mix\n",
    "doesn't resemble the unlabeled set's, that's a caveat on how far the\n",
    "allowlist below generalizes -- not assumed to transfer automatically."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 6. Per-label allowlist"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "allowlist = fixed_metrics[fixed_metrics[\"passes_gate\"]].index.tolist()\n",
    "print(f\"Allowlist ({len(allowlist)}/{len(LABEL_COLUMNS)}): {allowlist}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "**Insight:** pending first Kaggle run. This allowlist -- not a single\n",
    "GO/NO-GO flag -- is this notebook's deliverable: any future work that\n",
    "applies weak labels to expand a training set must only use labels on\n",
    "this list."
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.11"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
```

- [ ] **Step 2: Verify the notebook JSON is well-formed**

Run: `uv run python -c "import json; json.load(open('notebooks/02_weak_label_evaluation.ipynb')); print('OK')"`
Expected: prints `OK`

- [ ] **Step 3: Write `notebooks/kernels/weak-label-evaluation/kernel-metadata.json`**

```json
{
  "id": "tuannm3812/rsna-knee-weak-label-evaluation",
  "title": "rsna-knee-weak-label-evaluation",
  "code_file": "02_weak_label_evaluation.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": false,
  "enable_tpu": false,
  "enable_internet": true,
  "dataset_sources": ["tuannm3812/rsna-knee-mri-src"],
  "competition_sources": ["rsna-knee-abnormality-detection"],
  "kernel_sources": []
}
```

- [ ] **Step 4: Commit**

```bash
git add notebooks/02_weak_label_evaluation.ipynb notebooks/kernels/weak-label-evaluation/kernel-metadata.json
git commit -m "feat: add weak-label evaluation notebook stub and its Kaggle kernel metadata"
```

---

### Task 4: Final verification

**Files:** none (verification only).

**Interfaces:** none — confirms Tasks 1-3's deliverables work together.

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests pass — 18 in `test_labels.py`, 21 in `test_weak_label_evaluation.py`, plus the pre-existing `test_dataset.py`/`test_dicom_io.py`/`test_metrics.py` (13 from the repo-setup plan) — 52 total, 0 failures.

- [ ] **Step 2: Run the linter**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: Confirm notebook JSON validity**

Run: `uv run python -c "import json; json.load(open('notebooks/02_weak_label_evaluation.ipynb')); print('OK')"`
Expected: prints `OK`

- [ ] **Step 4: Review git status**

Run: `git status --short`
Expected: clean (empty output) — every file from Tasks 1-3 was committed at the end of its own task.

- [ ] **Step 5: Confirm the commit history is coherent**

Run: `git log --oneline -5`
Expected: 4 commits, one per task, each with a clear Conventional Commits message.

## Out of scope for this plan

- Actually running `02_weak_label_evaluation.ipynb` on Kaggle — requires publishing `src/knee_mri` (`scripts/publish_code_dataset.sh version "..."`) with this plan's finished code first, then `scripts/push_kaggle_kernel.sh weak-label-evaluation`. A follow-up interactive step (same pattern as `01_eda.ipynb`'s first real run), not part of this code-implementation plan.
- Writing `docs/4_experiments.md`'s and `docs/3_strategy.md`'s real-numbers entries — those require the actual Kaggle run's output; fabricating placeholder numbers here would violate this project's own no-placeholder discipline.
- Everything already listed in the design spec's own "Out of scope for this pass" section (multilingual cue expansion, a more sophisticated mention-conflict resolver, human-in-the-loop triage, applying weak labels to a training set, any change to `metrics.py`).
