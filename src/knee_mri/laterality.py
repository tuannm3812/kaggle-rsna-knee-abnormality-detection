"""Signed laterality canonicalization for Phase 3B.

Implements section 7 of the Phase 3B specification
(`docs/superpowers/specs/2026-08-26-phase-3b-image-baseline-design.md`).

The goal is to present every study to the encoder in one orientation, so the
head does not have to spend its 58-study budget learning two mirrored
representations of the same anatomy.

**The rule is signed, and the sign is essential.** An earlier proposal
(round 63) flipped every right knee horizontally; round 64 rejected it,
because the patient left/right axis is not always the image column axis, and
because two acquisitions of opposite sides can already be aligned in
array-index space. The measured evidence settles it: all 201 axial and 292
coronal series in the audited sample place patient-X on array **columns**
with a **positive** component, while all 329 sagittal series place it on the
geometry-ordered **slice stack**, negative on the 322 for which a side could
be conservatively resolved. Side alone therefore cannot decide whether to
reverse.

Canonical convention: **medial lies toward decreasing index on the
left/right-controlled axis.** That is deliberately *not* expressible as "make
everything look like a left knee" -- the unreversed state is a left knee for
axial and coronal but a **right** knee for sagittal, precisely because those
groups store opposite signs.

**Canonicalization is not idempotent, and the failure is silent.** Flipping
the array does not change the DICOM tags, so a second pass reads the same
geometry, decides to reverse again, and restores the original orientation
with no exception, no shape change, and nothing in the pixel data recording
what happened (round 79). `canonicalize_volume` therefore returns a
`CanonicalVolume` carrying an explicit applied-flag and refuses to run on one
that has already been transformed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from knee_mri.series_audit import patient_lr_axis_metrics

# Minimum |patient-X| component the selected axis must have, strictly greater.
#
# This is a cost-asymmetry safety choice supported by measured coverage, not
# an empirical separation point (required wording, round 69). The measured
# distribution is a smooth tail with no natural break -- 3 series in
# [0.80985, 0.85), 10 in [0.85, 0.90), 21 in [0.90, 0.95), 788 at or above
# 0.95 -- so no threshold is empirically privileged. 0.90 bounds accepted
# obliquity below 25.8 degrees, against 35.9 degrees at the observed minimum
# where a reversal would transpose substantial anterior-posterior or
# superior-inferior content rather than mirroring left/right. It rejects 13 of
# 822 audited series. A false accept corrupts an input silently; a false
# reject is visible and falls through to the flagged no-transform path.
DOMINANCE_GATE = 0.90

_AXIS_TO_ARRAY_AXIS = {"slices": 0, "rows": 1, "columns": 2}


class AlreadyCanonicalizedError(RuntimeError):
    """A volume that has already been canonicalized was passed in again.

    Raised rather than silently double-flipping, which would restore the
    original orientation undetectably (round 79).
    """


@dataclass(frozen=True)
class AxisDecision:
    """Which array axis carries patient left/right, and whether to reverse it.

    Attributes:
        array_axis: `"columns"`, `"rows"`, `"slices"`, or `None` when the
            orientation is tied, degenerate, invalid, or below the gate.
        signed_x: The selected axis's signed patient-X component, or `None`.
        reverse: Whether the canonical convention requires reversing that
            axis. Always `False` when `array_axis` is `None`.
    """

    array_axis: str | None
    signed_x: float | None
    reverse: bool


@dataclass(frozen=True)
class CanonicalVolume:
    """A volume plus an explicit record that canonicalization was applied."""

    array: np.ndarray
    canonicalized: bool


@dataclass(frozen=True)
class SeriesLateralityEvidence:
    """One series' laterality evidence, as read from its headers.

    Attributes:
        tag: The validated `Laterality`/`ImageLaterality` call, if any.
        geometry: The geometry-derived call, if any.
        cross_tag_conflict: Whether a single slice carried two disagreeing
            valid laterality tags.
    """

    tag: str | None = None
    geometry: str | None = None
    cross_tag_conflict: bool = False


@dataclass(frozen=True)
class StudyLaterality:
    """The conservative study-level consensus (section 7.3)."""

    call: str | None
    reliable: bool


@dataclass(frozen=True)
class CanonicalStudy:
    """Atomic result: every plane transformed, or none (section 7.4)."""

    planes: dict[str, np.ndarray]
    laterality_reliable: bool


def canonicalization_axis(
    image_orientation_patient: Sequence[float], side: str
) -> AxisDecision:
    """Select the left/right-controlled axis and decide whether to reverse it.

    Args:
        image_orientation_patient: The six direction cosines.
        side: `"L"` or `"R"`, the study's resolved knee.

    Returns:
        The decision. `array_axis` is `None` -- meaning non-canonicalizable,
        never guessed -- for a tied, degenerate, invalid, or below-gate
        orientation.
    """
    try:
        metrics = patient_lr_axis_metrics(image_orientation_patient)
    except ValueError:
        return AxisDecision(array_axis=None, signed_x=None, reverse=False)

    if metrics.array_axis is None or metrics.signed_x is None:
        return AxisDecision(array_axis=None, signed_x=None, reverse=False)
    if not metrics.dominant_abs_x > DOMINANCE_GATE:
        return AxisDecision(array_axis=None, signed_x=None, reverse=False)

    # Medial lies toward patient-left for a right knee and patient-right for
    # a left knee. The canonical state is `medial_x_sign * signed_x < 0`, so
    # reverse exactly when the product is positive.
    medial_x_sign = 1.0 if str(side).strip().upper() == "R" else -1.0
    return AxisDecision(
        array_axis=metrics.array_axis,
        signed_x=metrics.signed_x,
        reverse=(medial_x_sign * metrics.signed_x) > 0,
    )


def canonicalize_volume(
    volume: np.ndarray | CanonicalVolume,
    image_orientation_patient: Sequence[float],
    side: str,
) -> CanonicalVolume:
    """Apply the signed reversal to one plane's volume.

    Args:
        volume: A `(slices, rows, columns)` array. Passing an already
            canonicalized volume is an error, not a no-op.
        image_orientation_patient: The six direction cosines.
        side: `"L"` or `"R"`.

    Returns:
        The canonicalized volume with its applied-flag set.

    Raises:
        AlreadyCanonicalizedError: If `volume` has already been transformed.
        ValueError: If the orientation is non-canonicalizable. Callers should
            consult `canonicalization_axis` first and fall back to leaving
            every plane untransformed (section 7.4).
    """
    if isinstance(volume, CanonicalVolume):
        raise AlreadyCanonicalizedError(
            "volume was already canonicalized; a second pass would silently "
            "reverse it back to its original orientation"
        )

    decision = canonicalization_axis(image_orientation_patient, side)
    if decision.array_axis is None:
        raise ValueError("orientation is not canonicalizable")

    array = np.asarray(volume)
    if decision.reverse:
        # np.flip returns a negative-stride view, which torch.from_numpy
        # rejects outright. Materialize a contiguous array here so no
        # downstream consumer has to know or care.
        array = np.ascontiguousarray(np.flip(array, axis=_AXIS_TO_ARRAY_AXIS[decision.array_axis]))
    return CanonicalVolume(array=array, canonicalized=True)


def _series_call(evidence: SeriesLateralityEvidence) -> tuple[str | None, bool]:
    """Resolve one series conservatively. Returns `(call, conflicted)`.

    Deliberately not `SeriesAudit.laterality_resolved_call`, whose
    tag-over-geometry precedence is documented as audit-only and would
    silently resolve exactly the disagreements this must surface.
    """
    if evidence.cross_tag_conflict:
        return None, True
    sources = [call for call in (evidence.tag, evidence.geometry) if call is not None]
    if not sources:
        return None, False
    if len(set(sources)) > 1:
        return None, True
    return sources[0], False


def study_laterality(
    evidence: Sequence[SeriesLateralityEvidence],
) -> StudyLaterality:
    """Conservative consensus over **every** available series in the study.

    Round 47 approved deriving this from all study headers rather than only
    the series image selection happens to pick, so a series that never
    contributes pixels still gets a vote -- and can veto.

    A study is reliable only when at least one series resolves a call, every
    resolved call agrees, and **no conflict was observed anywhere**, even if
    the remaining calls agree among themselves.
    """
    calls: list[str] = []
    for item in evidence:
        call, conflicted = _series_call(item)
        if conflicted:
            return StudyLaterality(call=None, reliable=False)
        if call is not None:
            calls.append(call)

    if not calls or len(set(calls)) > 1:
        return StudyLaterality(call=None, reliable=False)
    return StudyLaterality(call=calls[0], reliable=True)


def canonicalize_study(
    planes: Mapping[str, tuple[np.ndarray, Sequence[float]]],
    study: StudyLaterality,
) -> CanonicalStudy:
    """Canonicalize every contributing plane, or none of them.

    Args:
        planes: `{plane_name: (volume, image_orientation_patient)}` for the
            planes that actually contribute features, after retry has settled
            which series won.
        study: The consensus from `study_laterality`.

    Returns:
        Transformed planes with `laterality_reliable=True`, or the untouched
        inputs with `laterality_reliable=False`.

    Atomicity is the point: canonicalizing some planes and not others would
    mix conventions inside one mean feature, which is worse than leaving all
    of them raw and flagging the study.
    """
    untouched = CanonicalStudy(
        planes={name: volume for name, (volume, _) in planes.items()},
        laterality_reliable=False,
    )

    if not study.reliable or study.call is None:
        return untouched

    decisions = {
        name: canonicalization_axis(orientation, study.call)
        for name, (_, orientation) in planes.items()
    }
    if any(decision.array_axis is None for decision in decisions.values()):
        return untouched

    return CanonicalStudy(
        planes={
            name: canonicalize_volume(volume, orientation, study.call).array
            for name, (volume, orientation) in planes.items()
        },
        laterality_reliable=True,
    )
