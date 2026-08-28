"""Study-level feature assembly for Phase 3B.

Implements sections 2 and 8 of the Phase 3B specification
(`docs/superpowers/specs/2026-08-26-phase-3b-image-baseline-design.md`).

Per study, in this order: canonicalize laterality across all contributing
planes atomically, letterbox each slice to its physical aspect ratio,
replicate to three channels, standardize with the attached processor's own
statistics, encode with the frozen DINOv2 encoder, mean within each plane,
then mean across the planes that are actually present.

Canonicalization runs **before** framing so the padding convention stays
consistent: section 5 places an odd padding pixel on the bottom or right, and
flipping after padding would move it to the top or left instead.

**An absent plane is excluded from the mean, never zero-filled into it.** A
zero vector in the numerator with the plane still counted in the denominator
would drag the study embedding toward the origin in proportion to how many
planes were missing, which is a silent, systematic corruption rather than a
graceful degradation.

**The four trailing flags are near-degenerate on this dataset, and the head
must not be relied on to learn from them.** Every audit measured 450/450
study-plane selections resolving, so on 58 training studies all three
presence flags are likely constant `1` -- zero variance, a coefficient
unidentifiable from the intercept, shrunk to approximately zero by L2. At the
frozen `0.90` laterality gate roughly 2.7 to 2.8 of 58 studies are expected
to carry `laterality_reliable = 0`, so for a label of prevalence 0.2 the
expected joint count is about 0.55 -- frequently zero, across twelve separate
one-vs-rest problems. The flags are kept because they are structurally
correct and become informative if the labelled set grows; graceful
degradation comes from excluding absent planes from the mean, not from the
flags.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import torch

from knee_mri.framing import letterbox_slice
from knee_mri.intensity import standardize, to_three_channel
from knee_mri.laterality import StudyLaterality, canonicalize_study

# Frozen by sections 8 and 46's aggregation contract.
PLANES = ("Sagittal", "Coronal", "Axial")
EMBEDDING_DIM = 384
STUDY_VECTOR_DIM = EMBEDDING_DIM + len(PLANES) + 1

# Fallback statistics are deliberately absent: section 6 step 7 forbids
# substituting remembered constants, so the caller must pass the attached
# processor's own values (see `intensity.load_processor_statistics`).
Encoder = Callable[[torch.Tensor], torch.Tensor]


@dataclass(frozen=True)
class PlaneInput:
    """One present plane's decoded slices and the geometry they came from.

    Attributes:
        images: Normalized `[0, 1]` slices in validated anatomical order,
            from `slice_sampling.sample_plane`.
        image_orientation_patient: The winning series' six direction cosines.
        pixel_spacing: That series' `(row_spacing, column_spacing)` in mm.
    """

    images: tuple[np.ndarray, ...]
    image_orientation_patient: Sequence[float]
    pixel_spacing: Sequence[float]


@dataclass(frozen=True)
class StudyFeatures:
    """The 388-dimensional study vector and what went into it.

    Attributes:
        vector: `[embedding (384) | presence flags (3) | reliability (1)]`.
        planes_present: Which of `PLANES` contributed.
        laterality_reliable: Whether canonicalization was actually applied.
        has_any_plane: `False` when every plane was absent -- the caller
            decides what to do, since section 4 treats a labelled training
            study and an unseen test study differently.
        plane_embeddings: Each present plane's own mean embedding, before
            the across-plane mean. Exposed so the pre-registered aggregation
            alternatives -- plane concatenation and per-plane heads, both
            deferred as later experiments rather than silent fallbacks --
            can be evaluated from the same extraction pass, without a second
            decode or a second forward through the encoder.
    """

    vector: np.ndarray
    planes_present: dict[str, bool]
    laterality_reliable: bool
    has_any_plane: bool
    plane_embeddings: dict[str, np.ndarray]


def _require_frozen(encoder: Encoder) -> None:
    """Reject a trainable encoder rather than let it quietly train.

    Only checks what is checkable: a plain callable carries no parameters to
    inspect, so this cannot prove an arbitrary encoder is frozen -- it catches
    the realistic case of a `torch.nn.Module` whose parameters were never
    frozen.
    """
    parameters = getattr(encoder, "parameters", None)
    if not callable(parameters):
        return
    if any(parameter.requires_grad for parameter in encoder.parameters()):
        raise ValueError(
            "encoder must be frozen: section 8 requires requires_grad_(False) "
            "on every parameter"
        )


def _plane_batch(
    images: Sequence[np.ndarray],
    pixel_spacing: Sequence[float],
    mean: Sequence[float],
    std: Sequence[float],
) -> torch.Tensor:
    """Letterbox, replicate, and standardize one plane's slices."""
    prepared = []
    for image in images:
        framed = letterbox_slice(torch.from_numpy(np.asarray(image)), pixel_spacing)
        prepared.append(standardize(to_three_channel(framed.image), mean, std))
    return torch.stack(prepared)


def build_study_features(
    planes: Mapping[str, PlaneInput],
    study: StudyLaterality,
    encoder: Encoder,
    mean: Sequence[float] = (0.0, 0.0, 0.0),
    std: Sequence[float] = (1.0, 1.0, 1.0),
) -> StudyFeatures:
    """Assemble one study's 388-dimensional feature vector.

    Args:
        planes: The present planes only, keyed by name. Absent planes are
            simply omitted.
        study: The conservative laterality consensus for this study.
        encoder: A frozen callable mapping `(N, 3, 336, 336)` to
            `(N, EMBEDDING_DIM)`.
        mean: Channel means from the attached processor's config.
        std: Channel standard deviations from the same config.

    Returns:
        The study vector and the provenance flags describing it.

    Raises:
        ValueError: If the encoder exposes trainable parameters.
    """
    _require_frozen(encoder)

    present = [plane for plane in PLANES if plane in planes]

    # Canonicalization is atomic across contributing planes, so it happens
    # once here rather than per plane -- and before framing, so the padding
    # convention is applied to already-canonical pixels.
    stacked = {
        plane: (
            np.stack([np.asarray(image) for image in planes[plane].images]),
            planes[plane].image_orientation_patient,
        )
        for plane in present
    }
    canonical = canonicalize_study(stacked, study)

    embeddings = []
    plane_embeddings: dict[str, np.ndarray] = {}
    for plane in present:
        volume = canonical.planes[plane]
        batch = _plane_batch(
            list(volume), planes[plane].pixel_spacing, mean, std
        )
        with torch.no_grad():
            encoded = encoder(batch)
        plane_mean = np.asarray(encoded, dtype=np.float64).mean(axis=0)
        plane_embeddings[plane] = plane_mean
        embeddings.append(plane_mean)

    if embeddings:
        study_embedding = np.mean(embeddings, axis=0)
    else:
        # No plane contributed. Report it rather than inventing an embedding;
        # section 4 handles a labelled training study and an unseen test
        # study differently, so that decision does not belong here.
        study_embedding = np.zeros(EMBEDDING_DIM, dtype=np.float64)

    presence_flags = [1.0 if plane in planes else 0.0 for plane in PLANES]
    vector = np.concatenate(
        [
            np.asarray(study_embedding, dtype=np.float64),
            np.asarray(presence_flags, dtype=np.float64),
            np.asarray([1.0 if canonical.laterality_reliable else 0.0], dtype=np.float64),
        ]
    )
    if vector.shape != (STUDY_VECTOR_DIM,):
        raise ValueError(f"study vector must be {STUDY_VECTOR_DIM}-dimensional")

    return StudyFeatures(
        vector=vector,
        planes_present={plane: plane in planes for plane in PLANES},
        laterality_reliable=canonical.laterality_reliable,
        has_any_plane=bool(present),
        plane_embeddings=plane_embeddings,
    )
