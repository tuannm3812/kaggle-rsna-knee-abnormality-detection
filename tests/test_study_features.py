from __future__ import annotations

import numpy as np
import pytest
import torch

from knee_mri.laterality import SeriesLateralityEvidence, study_laterality
from knee_mri.study_features import (
    EMBEDDING_DIM,
    PLANES,
    STUDY_VECTOR_DIM,
    PlaneInput,
    build_study_features,
)

ORIENTATION = (1.0, 0.0, 0.0, 0.0, 0.0, -1.0)  # patient-X on columns, positive
SPACING = (0.5, 0.4)


class StubEncoder:
    """Records what it was handed and returns a deterministic embedding."""

    def __init__(self, value: float | None = None):
        self.value = value
        self.batches: list[torch.Tensor] = []

    def __call__(self, batch: torch.Tensor) -> torch.Tensor:
        self.batches.append(batch.clone())
        if self.value is not None:
            return torch.full((batch.shape[0], EMBEDDING_DIM), self.value)
        # Deterministic per-slice signature so means are checkable.
        signatures = batch.reshape(batch.shape[0], -1).mean(dim=1, keepdim=True)
        return signatures.expand(batch.shape[0], EMBEDDING_DIM).clone()


def _plane(slice_count: int = 5, fill: float | None = None) -> PlaneInput:
    rng = np.random.default_rng(0)
    images = tuple(
        (np.full((16, 12), fill, dtype=np.float32) if fill is not None
         else rng.random((16, 12)).astype(np.float32))
        for _ in range(slice_count)
    )
    return PlaneInput(
        images=images, image_orientation_patient=ORIENTATION, pixel_spacing=SPACING
    )


def _reliable():
    return study_laterality([SeriesLateralityEvidence(tag="R")])


def _all_planes():
    return {plane: _plane() for plane in PLANES}


# -- dimensionality --


def test_study_vector_is_exactly_388_dimensions():
    assert EMBEDDING_DIM == 384
    assert STUDY_VECTOR_DIM == 388
    assert STUDY_VECTOR_DIM == EMBEDDING_DIM + len(PLANES) + 1

    features = build_study_features(_all_planes(), _reliable(), StubEncoder())

    assert features.vector.shape == (STUDY_VECTOR_DIM,)


def test_the_trailing_four_values_are_the_presence_and_reliability_flags():
    planes = _all_planes()
    del planes["Axial"]

    features = build_study_features(planes, _reliable(), StubEncoder())

    assert features.vector[EMBEDDING_DIM:].tolist() == [1.0, 1.0, 0.0, 1.0]
    assert features.planes_present == {"Sagittal": True, "Coronal": True, "Axial": False}
    assert features.laterality_reliable is True


# -- means: within plane, then across present planes only --


def test_absent_planes_are_excluded_from_the_mean_not_zero_filled():
    """A zero-filled absent plane would drag the study embedding toward zero;
    section 8 excludes it from the denominator instead.
    """
    only_one = {"Sagittal": _plane(fill=1.0)}
    two = {"Sagittal": _plane(fill=1.0), "Coronal": _plane(fill=1.0)}

    one_features = build_study_features(only_one, _reliable(), StubEncoder(value=7.0))
    two_features = build_study_features(two, _reliable(), StubEncoder(value=7.0))

    assert one_features.vector[:EMBEDDING_DIM] == pytest.approx(
        two_features.vector[:EMBEDDING_DIM]
    )
    assert one_features.vector[:EMBEDDING_DIM] == pytest.approx(np.full(EMBEDDING_DIM, 7.0))


def test_the_study_embedding_is_the_mean_of_present_plane_embeddings():
    encoder = StubEncoder()
    planes = _all_planes()

    features = build_study_features(planes, _reliable(), encoder)

    per_plane = [
        build_study_features({name: plane}, _reliable(), StubEncoder()).vector[:EMBEDDING_DIM]
        for name, plane in planes.items()
    ]
    assert features.vector[:EMBEDDING_DIM] == pytest.approx(np.mean(per_plane, axis=0))


def test_a_plane_with_three_slices_is_meaned_over_three():
    encoder = StubEncoder()

    build_study_features({"Sagittal": _plane(slice_count=3)}, _reliable(), encoder)

    assert encoder.batches[0].shape[0] == 3


def test_a_study_with_no_present_planes_is_reported_rather_than_averaged():
    features = build_study_features({}, _reliable(), StubEncoder())

    assert features.has_any_plane is False
    assert features.vector[:EMBEDDING_DIM] == pytest.approx(np.zeros(EMBEDDING_DIM))
    assert features.vector[EMBEDDING_DIM:].tolist() == [0.0, 0.0, 0.0, 1.0]


# -- encoder contract --


def test_the_encoder_receives_three_channel_target_size_batches():
    encoder = StubEncoder()

    build_study_features({"Sagittal": _plane()}, _reliable(), encoder)

    batch = encoder.batches[0]
    assert batch.shape == (5, 3, 336, 336)
    assert batch.dtype == torch.float32


def test_a_frozen_encoder_is_required():
    """Section 8 freezes the encoder; a trainable one is a contract breach
    that would otherwise only show up as an unexplained score.
    """

    class TrainableEncoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(1))

        def forward(self, batch):
            return torch.zeros(batch.shape[0], EMBEDDING_DIM)

    trainable = TrainableEncoder()

    with pytest.raises(ValueError, match="frozen"):
        build_study_features({"Sagittal": _plane()}, _reliable(), trainable)

    for parameter in trainable.parameters():
        parameter.requires_grad_(False)
    trainable.eval()

    features = build_study_features({"Sagittal": _plane()}, _reliable(), trainable)
    assert features.vector.shape == (STUDY_VECTOR_DIM,)


# -- laterality is applied once, before framing --


def test_laterality_is_applied_exactly_once_per_plane():
    """Canonicalization is not idempotent (round 79). If it were applied per
    slice as well as per volume, or twice anywhere, AlreadyCanonicalizedError
    would surface -- this asserts the happy path stays single-application.
    """
    encoder = StubEncoder()

    features = build_study_features(_all_planes(), _reliable(), encoder)

    assert features.laterality_reliable is True
    assert len(encoder.batches) == len(PLANES)


def test_an_unreliable_study_leaves_pixels_untransformed_and_flags_it():
    conflicted = study_laterality(
        [SeriesLateralityEvidence(tag="L"), SeriesLateralityEvidence(tag="R")]
    )
    encoder = StubEncoder()

    features = build_study_features(_all_planes(), conflicted, encoder)

    assert features.laterality_reliable is False
    assert features.vector[-1] == 0.0


def test_canonicalization_changes_the_encoder_input_when_it_reverses():
    """A right knee on a positive-X column axis must be reversed; the encoder
    must therefore see different pixels than an unreliable study would.
    """
    planes = {"Sagittal": _plane()}
    reliable_encoder, unreliable_encoder = StubEncoder(), StubEncoder()

    build_study_features(planes, _reliable(), reliable_encoder)
    unreliable = study_laterality(
        [SeriesLateralityEvidence(tag="L"), SeriesLateralityEvidence(tag="R")]
    )
    build_study_features(planes, unreliable, unreliable_encoder)

    assert not torch.allclose(reliable_encoder.batches[0], unreliable_encoder.batches[0])
