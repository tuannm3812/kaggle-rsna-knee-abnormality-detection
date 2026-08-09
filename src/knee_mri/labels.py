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
    for pattern in [
        r"\brule out\b",
        r"\br/o\b",
        r"\bquestion of\b",
        r"\bpossible\b",
        r"\bcannot exclude\b",
    ]
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
