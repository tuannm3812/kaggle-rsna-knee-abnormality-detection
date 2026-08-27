from __future__ import annotations

import math

import numpy as np
import pytest

from knee_mri.laterality import (
    DOMINANCE_GATE,
    AlreadyCanonicalizedError,
    SeriesLateralityEvidence,
    canonicalization_axis,
    canonicalize_study,
    canonicalize_volume,
    study_laterality,
)

AXIS_TO_NUMPY = {"slices": 0, "rows": 1, "columns": 2}

# Orientations whose left/right-controlled array axis is known, in both
# stored sign conventions. Round 67 measured axial/coronal on columns with
# positive patient-X and sagittal on the slice stack with negative.
ORIENTATIONS = {
    ("columns", +1.0): (1, 0, 0, 0, 0, -1),
    ("columns", -1.0): (-1, 0, 0, 0, 0, -1),
    ("rows", +1.0): (0, 1, 0, 1, 0, 0),
    ("rows", -1.0): (0, 1, 0, -1, 0, 0),
    # cross((0,1,0), (0,0,1)) = (+1,0,0), so the +1 case is the one whose
    # column direction is +z. Verified against patient_lr_axis_metrics rather
    # than derived by hand.
    ("slices", +1.0): (0, 1, 0, 0, 0, 1),
    ("slices", -1.0): (0, 1, 0, 0, 0, -1),
}


def _volume_with_medial_marker(orientation, side, shape=(5, 4, 3)):
    """Place a marker at the slice's true medial end of the controlled axis."""
    decision = canonicalization_axis(orientation, side)
    assert decision.array_axis is not None
    medial_sign = +1 if side == "R" else -1
    at_max_index = (decision.signed_x * medial_sign) > 0

    volume = np.zeros(shape, dtype=int)
    axis = AXIS_TO_NUMPY[decision.array_axis]
    index = [slice(None)] * 3
    index[axis] = (shape[axis] - 1) if at_max_index else 0
    volume[tuple(index)] = 1
    return volume, decision


def _marker_position(volume, array_axis):
    axis = AXIS_TO_NUMPY[array_axis]
    low, high = [slice(None)] * 3, [slice(None)] * 3
    low[axis], high[axis] = 0, volume.shape[axis] - 1
    return bool(volume[tuple(low)].any()), bool(volume[tuple(high)].any())


# -- 7.1 axis selection --


def test_gate_is_strictly_greater_than_the_frozen_value():
    assert DOMINANCE_GATE == 0.90

    at_gate = (0.90, 0.0, math.sqrt(1 - 0.81), 0, 1, 0)
    just_above = (0.9001, 0.0, math.sqrt(1 - 0.9001**2), 0, 1, 0)

    assert canonicalization_axis(at_gate, "R").array_axis is None
    assert canonicalization_axis(just_above, "R").array_axis == "columns"


@pytest.mark.parametrize(
    ("label", "orientation"),
    [
        ("exact tie between row and column", (0.5**0.5, 0, 0.5**0.5, 0.5**0.5, 0, -(0.5**0.5))),
        ("degenerate, row parallel to column", (1, 0, 0, 1, 0, 0)),
        ("zero row vector", (0, 0, 0, 0, 1, 0)),
        ("non-finite", (float("nan"), 0, 0, 0, 1, 0)),
        ("wrong length", (1, 0, 0)),
    ],
)
def test_non_canonicalizable_orientations_resolve_to_no_axis(label, orientation):
    decision = canonicalization_axis(orientation, "R")

    assert decision.array_axis is None
    assert decision.signed_x is None
    assert decision.reverse is False


# -- 7.2 the signed rule, across all twelve combinations --


@pytest.mark.parametrize("expected_axis", ["columns", "rows", "slices"])
@pytest.mark.parametrize("stored_sign", [+1.0, -1.0])
@pytest.mark.parametrize("side", ["L", "R"])
def test_canonicalization_puts_medial_at_decreasing_index(expected_axis, stored_sign, side):
    orientation = ORIENTATIONS[(expected_axis, stored_sign)]
    volume, decision = _volume_with_medial_marker(orientation, side)
    assert decision.array_axis == expected_axis

    result = canonicalize_volume(volume, orientation, side)
    at_low, at_high = _marker_position(result.array, expected_axis)

    assert at_low is True
    assert at_high is False
    assert result.canonicalized is True


@pytest.mark.parametrize("expected_axis", ["columns", "rows", "slices"])
def test_paired_left_and_right_acquisitions_land_in_the_same_convention(expected_axis):
    orientation = ORIENTATIONS[(expected_axis, +1.0)]
    right_volume, _ = _volume_with_medial_marker(orientation, "R")
    left_volume, _ = _volume_with_medial_marker(orientation, "L")

    right = canonicalize_volume(right_volume, orientation, "R")
    left = canonicalize_volume(left_volume, orientation, "L")

    assert np.array_equal(right.array, left.array)


def test_the_target_is_not_expressible_as_a_left_knee_convention():
    """Section 7.4: the canonical unreversed state is a LEFT knee for
    axial/coronal but a RIGHT knee for sagittal, because the two groups store
    opposite axis signs. Any restatement in left/right terms is wrong.
    """
    axial_like = ORIENTATIONS[("columns", +1.0)]
    sagittal_like = ORIENTATIONS[("slices", -1.0)]

    assert canonicalization_axis(axial_like, "R").reverse is True
    assert canonicalization_axis(axial_like, "L").reverse is False
    assert canonicalization_axis(sagittal_like, "R").reverse is False
    assert canonicalization_axis(sagittal_like, "L").reverse is True


# -- the non-idempotence hazard (round 79) --


def test_canonicalizing_twice_raises_rather_than_silently_reverting():
    """Flipping the array leaves the DICOM tags unchanged, so a second pass
    reads the same geometry, reverses again, and silently restores the
    original orientation -- undetectably, since nothing about the array
    records that it was transformed.
    """
    orientation = ORIENTATIONS[("columns", +1.0)]
    volume, _ = _volume_with_medial_marker(orientation, "R")

    once = canonicalize_volume(volume, orientation, "R")

    with pytest.raises(AlreadyCanonicalizedError):
        canonicalize_volume(once, orientation, "R")


# -- 7.3 study-level consensus --


def _evidence(tag=None, geometry=None, cross_tag_conflict=False):
    return SeriesLateralityEvidence(
        tag=tag, geometry=geometry, cross_tag_conflict=cross_tag_conflict
    )


def test_a_single_resolved_source_resolves_the_series():
    assert study_laterality([_evidence(tag="L")]).call == "L"
    assert study_laterality([_evidence(geometry="R")]).call == "R"


def test_two_agreeing_sources_resolve_the_series():
    result = study_laterality([_evidence(tag="L", geometry="L")])

    assert result.call == "L"
    assert result.reliable is True


def test_no_resolved_call_anywhere_is_unreliable():
    result = study_laterality([_evidence(), _evidence()])

    assert result.call is None
    assert result.reliable is False


def test_tag_geometry_disagreement_makes_the_whole_study_unreliable():
    """Conservative by design: a conflict is never resolved by precedence."""
    result = study_laterality([_evidence(tag="L", geometry="R"), _evidence(tag="L")])

    assert result.reliable is False


def test_cross_tag_conflict_makes_the_whole_study_unreliable():
    result = study_laterality([_evidence(tag="L", cross_tag_conflict=True), _evidence(tag="L")])

    assert result.reliable is False


def test_disagreement_between_series_makes_the_study_unreliable():
    result = study_laterality([_evidence(tag="L"), _evidence(tag="R")])

    assert result.reliable is False


def test_a_non_selected_series_can_veto_the_study():
    """Round 47 approved consensus from ALL available study headers, so a
    series that never contributes pixels still gets a vote.
    """
    selected = _evidence(tag="L", geometry="L")
    non_selected_conflict = _evidence(tag="R")

    assert study_laterality([selected]).reliable is True
    assert study_laterality([selected, non_selected_conflict]).reliable is False


# -- 7.4 atomic application --


def test_all_planes_are_canonicalized_together_when_everything_resolves():
    orientation = ORIENTATIONS[("columns", +1.0)]
    planes = {
        plane: (_volume_with_medial_marker(orientation, "R")[0], orientation)
        for plane in ("Sagittal", "Coronal", "Axial")
    }

    result = canonicalize_study(planes, study_laterality([_evidence(tag="R")]))

    assert result.laterality_reliable is True
    for plane in planes:
        at_low, at_high = _marker_position(result.planes[plane], "columns")
        assert at_low and not at_high


def test_one_uncanonicalizable_plane_prevents_transforming_any_plane():
    """Mixing canonicalized and raw planes inside one mean is exactly what
    section 7.4's atomic rule exists to prevent.
    """
    good = ORIENTATIONS[("columns", +1.0)]
    oblique = (0.5**0.5, 0, 0.5**0.5, 0.5**0.5, 0, -(0.5**0.5))
    good_volume, _ = _volume_with_medial_marker(good, "R")
    planes = {
        "Sagittal": (good_volume, good),
        "Coronal": (np.zeros((5, 4, 3), dtype=int), oblique),
    }

    result = canonicalize_study(planes, study_laterality([_evidence(tag="R")]))

    assert result.laterality_reliable is False
    assert np.array_equal(result.planes["Sagittal"], good_volume)


def test_an_unreliable_study_call_transforms_nothing():
    orientation = ORIENTATIONS[("columns", +1.0)]
    volume, _ = _volume_with_medial_marker(orientation, "R")
    planes = {"Sagittal": (volume, orientation)}

    unreliable = study_laterality([_evidence(tag="L"), _evidence(tag="R")])
    result = canonicalize_study(planes, unreliable)

    assert result.laterality_reliable is False
    assert np.array_equal(result.planes["Sagittal"], volume)
