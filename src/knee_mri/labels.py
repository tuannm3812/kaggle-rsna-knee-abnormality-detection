"""Report-derived weak labels and the canonical 12-target label schema."""

from __future__ import annotations

import re

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
# (case-insensitive) counts as a positive weak label for that column.
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


def extract_weak_labels(report_text: str) -> dict[str, int]:
    """Derive weak per-label findings from a free-text radiology report.

    Keyword/regex matching only — a starting point for studies that lack
    a human-annotated label, not a replacement for the annotated subset.
    Case-insensitive; does not attempt negation detection (e.g. "no
    evidence of fracture" still matches "Fracture") — a known limitation
    to refine once real report text has been inspected (see
    docs/3_strategy.md).

    Args:
        report_text: The study's free-text radiology report.

    Returns:
        A dict mapping each of the 12 `LABEL_COLUMNS` to 0 or 1.
    """
    return {
        label: int(any(pattern.search(report_text) for pattern in patterns))
        for label, patterns in _COMPILED_PATTERNS.items()
    }
