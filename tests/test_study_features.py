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
    max_pool,
    mean_pool,
    top_k_pool,
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


def test_per_plane_embeddings_are_exposed_for_the_deferred_variants():
    """Plane concatenation and per-plane heads were deferred as predefined
    experiments. Evaluating them must not require a second decode or a second
    forward pass, so the per-plane means are returned alongside the mean of
    means -- and the study embedding must be exactly that mean.
    """
    planes = _all_planes()

    features = build_study_features(planes, _reliable(), StubEncoder())

    assert set(features.plane_embeddings) == set(PLANES)
    for embedding in features.plane_embeddings.values():
        assert embedding.shape == (EMBEDDING_DIM,)
    assert features.vector[:EMBEDDING_DIM] == pytest.approx(
        np.mean(list(features.plane_embeddings.values()), axis=0)
    )


def test_absent_planes_have_no_embedding_entry():
    planes = _all_planes()
    del planes["Axial"]

    features = build_study_features(planes, _reliable(), StubEncoder())

    assert set(features.plane_embeddings) == {"Sagittal", "Coronal"}


def test_a_wider_encoder_is_supported_for_pre_registered_variants():
    """Patch-token pooling needs a second representation of the same slices.

    Computing it in the same forward pass as the CLS token -- rather than a
    second extraction -- is what guarantees the two variants differ only in
    the representation and not in anything upstream of it.
    """
    wide = 2 * EMBEDDING_DIM

    class WideEncoder:
        def __call__(self, batch):
            return torch.arange(wide, dtype=torch.float32).expand(batch.shape[0], wide)

    features = build_study_features(
        {"Sagittal": _plane()}, _reliable(), WideEncoder(), embedding_dim=wide
    )

    assert features.vector.shape == (wide + len(PLANES) + 1,)
    assert features.plane_embeddings["Sagittal"].shape == (wide,)


def test_the_default_width_is_unchanged():
    features = build_study_features(_all_planes(), _reliable(), StubEncoder())

    assert features.vector.shape == (STUDY_VECTOR_DIM,)


# -- the within-plane pooling operator is parameterized --


def test_the_default_pool_is_still_the_mean():
    """The pooling experiment must not disturb the reported baseline."""
    encoder = StubEncoder()
    planes = _all_planes()

    default = build_study_features(planes, _reliable(), encoder)
    explicit = build_study_features(planes, _reliable(), StubEncoder(), slice_pool=mean_pool)

    assert default.vector == pytest.approx(explicit.vector)


def test_max_pool_takes_the_strongest_slice_per_dimension():
    class RampEncoder:
        """Slice i returns the constant vector i, so the max is unambiguous."""

        def __call__(self, batch):
            values = torch.arange(batch.shape[0], dtype=torch.float32).unsqueeze(1)
            return values.expand(batch.shape[0], EMBEDDING_DIM).clone()

    features = build_study_features(
        {"Sagittal": _plane(slice_count=5)}, _reliable(), RampEncoder(), slice_pool=max_pool
    )

    assert features.plane_embeddings["Sagittal"] == pytest.approx(np.full(EMBEDDING_DIM, 4.0))


def test_max_pool_differs_from_mean_pool_on_the_same_slices():
    """Guards against a pool that is silently ignored -- the failure mode
    that would make a pooling comparison return a spurious null.
    """
    planes = {"Sagittal": _plane()}

    meaned = build_study_features(planes, _reliable(), StubEncoder(), slice_pool=mean_pool)
    maxed = build_study_features(planes, _reliable(), StubEncoder(), slice_pool=max_pool)

    assert not np.allclose(meaned.vector[:EMBEDDING_DIM], maxed.vector[:EMBEDDING_DIM])


def test_pooling_changes_only_the_within_plane_step():
    """The across-plane aggregation stays a mean under any slice pool, so a
    pooling experiment changes one operator rather than two.
    """
    planes = _all_planes()

    features = build_study_features(planes, _reliable(), StubEncoder(), slice_pool=max_pool)

    assert features.vector[:EMBEDDING_DIM] == pytest.approx(
        np.mean(list(features.plane_embeddings.values()), axis=0)
    )


def test_a_pool_returning_the_wrong_width_is_rejected():
    with pytest.raises(ValueError, match="dimensional"):
        build_study_features(
            {"Sagittal": _plane()},
            _reliable(),
            StubEncoder(),
            slice_pool=lambda embeddings: embeddings.mean(axis=0)[:10],
        )


def test_top_k_pool_averages_the_k_strongest_slices():
    class RampEncoder:
        def __call__(self, batch):
            values = torch.arange(batch.shape[0], dtype=torch.float32).unsqueeze(1)
            return values.expand(batch.shape[0], EMBEDDING_DIM).clone()

    features = build_study_features(
        {"Sagittal": _plane(slice_count=5)},
        _reliable(),
        RampEncoder(),
        slice_pool=top_k_pool(3),
    )

    # Slices 0..4; the three strongest are 2, 3, 4, averaging to 3.
    assert features.plane_embeddings["Sagittal"] == pytest.approx(np.full(EMBEDDING_DIM, 3.0))


def test_top_k_pool_degrades_to_the_mean_when_fewer_slices_survive():
    """MINIMUM_DECODED_SLICES permits a plane with three slices, so k=5 must
    not fail there -- it averages what exists.
    """
    class RampEncoder:
        def __call__(self, batch):
            values = torch.arange(batch.shape[0], dtype=torch.float32).unsqueeze(1)
            return values.expand(batch.shape[0], EMBEDDING_DIM).clone()

    features = build_study_features(
        {"Sagittal": _plane(slice_count=3)},
        _reliable(),
        RampEncoder(),
        slice_pool=top_k_pool(5),
    )

    assert features.plane_embeddings["Sagittal"] == pytest.approx(np.full(EMBEDDING_DIM, 1.0))


def test_top_k_pool_with_k_of_one_is_max_pool():
    planes = {"Sagittal": _plane()}

    top_one = build_study_features(planes, _reliable(), StubEncoder(), slice_pool=top_k_pool(1))
    maxed = build_study_features(planes, _reliable(), StubEncoder(), slice_pool=max_pool)

    assert top_one.vector == pytest.approx(maxed.vector)


def test_top_k_pool_rejects_a_non_positive_k():
    with pytest.raises(ValueError, match="positive"):
        top_k_pool(0)
