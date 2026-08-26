# Phase 3B — Image Baseline Design Specification

**Status:** drafted 2026-08-26. Every contract below was approved section by
section by the user across `docs/collaboration/active_task.md` rounds 46-75.
This document consolidates those decisions into one frozen reference; it
introduces no new choice that was not already approved, except where a
subsection is explicitly marked **OPEN**.

**Review caveat.** Rounds 1-75 were produced under two-sided review: Claude
proposed or implemented, Codex independently verified, and the user approved.
From round 76 the user withdrew Codex from this project. This specification
therefore has **not** had the adversarial second read every prior contract
received. Treat the consolidation as reliable where it cites an approved
round, and treat the synthesis, ordering, and any wording not traceable to a
round as unreviewed. The user should read this document before it is used to
authorize implementation.

**Authorization.** This document authorizes nothing on its own. Implementation
requires a separate approved implementation plan; a competition submission
requires explicit user sign-off on the exact kernel version, which has never
been given and is not requested here.

---

## 1. Objective and scope

Build a submittable, reproducible image-based multilabel baseline for the RSNA
knee abnormality competition: 12 binary labels (`ACL`, `MCL`,
`Medial Meniscus`, `Lateral Meniscus`, `Medial OA`, `Lateral OA`, `PF OA`,
`Effusion`, `Synovitis`, `Baker's`, `Contusion`, `Fracture`) predicted per
study from MRI pixel data alone.

Training data is the **58 gold-labeled studies**. The remaining ~4,349 train
studies carry no human label and are not used: Phase 2 returned an explicit
No-go on weak-label training (`docs/collaboration/archive/`). Inference runs
against the documented **~1,300-study hidden test set**.

Non-goals for this baseline, each deferred as a separately reviewed experiment
rather than a silent fallback: plane-embedding concatenation, independent
per-plane heads, patch-token pooling, augmentation, test-time augmentation,
and any fine-tuning of the encoder.

## 2. Architecture and data flow

Approved round 47. Per study, in order:

1. Select at most one series per anatomical plane (Sagittal, Coronal, Axial).
2. Derive a conservative study-level laterality consensus from **all**
   available series headers in the study.
3. Order each selected series by validated geometry, with a validated
   `InstanceNumber` fallback.
4. Sample five symmetric central-band slices per selected series.
5. Letterbox to physical aspect ratio, normalize intensity, and conditionally
   canonicalize laterality.
6. Encode each slice with frozen DINOv2-small.
7. Mean the slice embeddings within each plane, then mean the available plane
   embeddings; append presence and reliability flags.
8. Fit one strongly regularized multilabel linear head on the established
   folds; refit on all 58; infer through the identical image path.
9. Build the submission inside the Kaggle notebook.

**Resilience principle (round 47), applied at every level below:** a component
that cannot be validated is *excluded and flagged*, never guessed at, never
silently substituted, and never a reason to abort the run.

## 3. Series selection: ranking, validation, retry

Approved round 50; implemented and measured in rounds 51-58
(`src/knee_mri/dataset.py`, `src/knee_mri/series_audit.py`).

**Ranking** within a plane: prefer `Fluid_Sensitive == 1`, then most slices,
then `SeriesInstanceUID` ascending as a deterministic final tie-break.

**Validation gate** (`validate_and_order_series`) — a series is usable only if
one of these holds:

- *Geometry route*: every slice has finite, parseable `ImagePositionPatient`
  and `ImageOrientationPatient`; row and column direction cosines are
  unit-length within `unit_norm_tolerance`; they are mutually orthogonal
  within `orthogonality_tolerance` after normalization; every slice's row
  **and** column direction agrees with the first slice's at cosine similarity
  ≥ `orientation_tolerance`; and projected slice positions are pairwise
  separated by ≥ `position_tolerance_mm`.
- *InstanceNumber route*: every slice has an `InstanceNumber`, parseable as an
  integer, with no duplicates.

Otherwise the series is **unusable**. Filename order is never presented as
anatomical.

**Frozen tolerances** (rounds 53, 57). These are the reviewed production
contract; the four arguments are keyword-only and exist for tests and
diagnostics. Values inside each stated range are *validated*, not
*requirement-preserving* — e.g. `orientation_tolerance=0.0` re-admits the
90-degree in-plane rotation the default rejects.

| Constant | Value | Guards against |
|---|---|---|
| `orientation_tolerance` | `0.999` | ~2.6° misalignment budget; rejects in-plane rotation between slices |
| `position_tolerance_mm` | `0.01` | Duplicate / indistinguishable slice positions |
| `unit_norm_tolerance` | `0.01` | Non-unit direction cosines |
| `orthogonality_tolerance` | `0.01` | Non-orthogonal row/column axes |

**Retry:** on an unusable series, try the next ranked same-plane candidate.
Only when every candidate is exhausted is the plane **absent**.

**Unreadable members:** a malformed or unreadable `.dcm` makes the candidate
unusable (not a crash), and the retry loop handles it like any other
validation failure.

**Measured:** 822/822 sampled series validated by geometry, and all 450
study-plane selections resolved on the first candidate, with zero retries
(`docs/7_image_baseline_insights.md` v4-v8). Retry and the missing-plane
fallback are therefore implemented and tested but never exercised on real
sampled data — they exist for the hidden set, which cannot be inspected.

## 4. Slice sampling, decode, and per-plane fallback

Approved round 60 finding 7, refined rounds 70 and 75.

- Sample **five deterministic central-band slices** from the validated order
  (`central_band_indices`).
- Attempt a full pixel decode of each. Require **at least three successes**.
- Mean only the successfully decoded slices' embeddings (3 to 5 of them).
- Below three successes, the series fails: retry the next ranked same-plane
  candidate.
- The plane is **absent** only when every candidate fails this rule.

Equal plane weighting is intentional even when one plane contributes three
decoded slices and another five; variance weighting would add capacity this
58-study budget cannot support.

**Study-level exhaustion.** For a **labeled training study** with all three
planes absent: **fail the release gate and diagnose the data path.** Do not
construct a feature from its targets. For an **unseen test study** with all
planes absent: emit the full-58 training prevalence vector as a last-resort
row-preserving fallback, and count it. If an OOF fallback is ever permitted
instead of fail-fast, it must use the **outer-training-fold** prevalence,
never full-58 prevalence, or it leaks.

**Measured:** zero decode failures across 4,110 attempted decodes.

## 5. Physical framing

Approved round 61. Rejected alternatives: an unmeasured 90% center crop (no
evidence the discarded margin is background) and a fixed-mm crop (needs an
anatomical extent this project has not measured).

1. Compute the physical footprint as `Rows * row_spacing` by
   `Columns * column_spacing` millimetres.
2. Set the **longer** resized dimension to `336`. Compute the shorter by
   nearest-integer rounding, `floor(value + 0.5)`, clamped to `[1, 336]`.
3. Resize with **bilinear interpolation and antialiasing**.
4. Pad the shorter dimension to `336 x 336`, splitting padding evenly and
   placing any extra pixel on the **bottom or right**.
5. The pad value is `0` **in the locally normalized `[0, 1]` intensity
   domain**, i.e. after §6 step 6 and before §6 step 7's channel
   standardization.

`PixelSpacing` must be present, finite, positive, and consistent under §3's
validation. A candidate that cannot satisfy this is **unusable**; retry the
next ranked same-plane series; the plane is absent only after exhaustion.

These are tested constants in the package, not notebook-local behavior.

**Evidence:** measured pixel spacing spans 0.137-1.172 mm (mean 0.327), so a
pixel-only resize would encode a different real-world extent per study —
which is what letterboxing on physical aspect ratio removes. `336` is evenly
divisible by DINOv2's 14-pixel patch size (24x24 = 576 patches) and is the
resolution already exercised in the GPU timing probe.

## 6. Intensity contract: DICOM to DINOv2 input

Approved rounds 61-62, with round 64's padding-domain clarification. Applied
per slice, **in this order**:

1. Build the **pixel-padding mask in the stored-value domain, before the
   modality transform** — including the inclusive interval when both
   `PixelPaddingValue` and `PixelPaddingRangeLimit` are present. Masked
   values remain excluded after transformation.
2. Apply the DICOM **modality transform** where present:
   `RescaleSlope`/`RescaleIntercept`, or the modality LUT.
3. Invert for **`MONOCHROME1`** polarity, so higher final intensity always
   means brighter, consistent with `MONOCHROME2`.
4. If the remaining finite, non-padding pixel variation is insufficient for a
   meaningful clip, treat the slice as a **decode failure** (subject to §4's
   minimum-three-of-five rule).
5. Estimate **p1/p99 independently per slice** from its finite, non-padding,
   post-modality-transform values. Clip to those bounds and linearly rescale
   to `[0, 1]`. Map excluded padding to normalized `0`.
6. Replicate the single-channel `[0, 1]` image to **3 channels**.
7. Apply `image_mean` / `image_std` loaded from the **attached model's own
   `preprocessor_config.json`**. Missing or malformed processor metadata is a
   **hard environment error** — there is no remembered-constant fallback and
   no substitution of ImageNet values.

**Required test:** compare this manual pipeline's final tensor against the
attached Transformers image processor, configured **not** to resize or
rescale again, and assert agreement. The preflight probe established runtime
and tensor-shape compatibility only, never semantic equivalence to the
pretrained processor.

Per-slice (rather than per-series-pooled) bounds were chosen because MRI has
no calibrated absolute intensity scale, per-slice estimation is robust to
slice-level gain variation, and it isolates one abnormal slice from the other
four. The tradeoff — losing between-slice absolute differences — is
acceptable precisely because those differences are not physical quantities.

## 7. Laterality canonicalization

Approved rounds 64-65 (algorithm), 67 (evidence), 70 (threshold). This section
replaced an earlier proposal that applied a blanket horizontal flip; that
proposal was wrong, because the patient left/right axis is not always the
image column axis.

### 7.1 Axis selection

From the validated, normalized geometry, three orthogonal vectors map to three
array axes:

| Vector | Controls | Array axis |
|---|---|---|
| `row_direction` (`ImageOrientationPatient[:3]`) | increasing **column** index | columns |
| `column_direction` (`ImageOrientationPatient[3:]`) | increasing **row** index | rows |
| `slice_normal` (their cross product) | increasing geometry-ordered **slice** index | slices |

Select the vector whose **absolute patient-X component is uniquely dominant**
and exceeds the gate. An exact tie, a non-finite or invalid orientation, or a
below-gate dominant magnitude is **non-canonicalizable**. Never infer the axis
from anatomical-plane labels or filenames.

**Frozen gate: `dominant_abs_x > 0.90`.**

This is a **cost-asymmetry safety choice supported by measured coverage, not
an empirical separation point** — that framing is required wording (round 69)
and must not be strengthened. Justification: the measured distribution is a
smooth tail (3 series in `[0.81, 0.85)`, 10 in `[0.85, 0.90)`, 21 in
`[0.90, 0.95)`, 788 at or above `0.95`) with no natural break, so no threshold
is empirically privileged. `0.90` bounds accepted obliquity below 25.8°,
versus 35.9° at the observed minimum, where a reversal would transpose
substantial anterior-posterior or superior-inferior content rather than
mirroring left/right. It rejects 13 of 822 audited series. A false accept
corrupts an input silently; a false reject is visible and falls through to the
flagged no-transform path.

### 7.2 Signed reversal

Define `medial_x_sign` as `+1` for a right knee and `-1` for a left knee.
Freeze the canonical array convention as **"medial lies toward decreasing
index on the left/right-controlled axis."**

**Reverse the selected axis exactly when `medial_x_sign * selected_axis_x > 0`;
otherwise leave it unchanged.**

The sign is essential, not decorative: the orientation audit measured all 201
axial and all 292 coronal series selecting array **columns** with **positive**
patient-X, while all 329 sagittal series selected geometry-ordered **slices**
with **negative** patient-X. Side alone therefore cannot determine whether to
reverse; canonicalizing both sides requires the signed rule.

For the stack-normal case, reversal means reversing the geometry-ordered slice
list. Symmetric sampling followed by mean pooling makes the current feature
invariant to that reversal, so it is a deliberate no-op on the final vector —
specified and tested anyway, to preserve the declared convention for any
later order-sensitive use.

### 7.3 Study-level consensus

Derive per-series calls with a **conservative pure resolver**, not the
audit-only tag-over-geometry precedence in `laterality_resolved_call`:

- A series with unreadable or internally inconsistent laterality headers
  contributes **no call**.
- Any `Laterality`/`ImageLaterality` cross-tag conflict, or any tag/geometry
  disagreement, is **explicit conflict** — never resolved by precedence.
- Otherwise the series resolves if exactly one valid source (tag or geometry)
  gives a call, or if two sources agree.

Aggregate the non-conflicting calls from **every available series in the
study**, not only the selected ones (round 47 approved all-header consensus so
it is not coupled to which sequence wins image selection). The study call is
reliable only if there is **at least one call** and **unanimous agreement**,
and **conservatively, any observed conflict anywhere in the study makes the
study unreliable even if the remaining calls agree.**

### 7.4 Atomic application

After retry has determined the actual feature-contributing series: only when
the study call is reliable **and every present contributing plane has a
reliable signed-axis decision** are **all** planes canonicalized and
`laterality_reliable = 1`. Otherwise **no plane is transformed** and the flag
is `0`. This prevents mixing canonicalized and raw planes inside one mean.

Canonical target orientation is left-knee convention; the choice is arbitrary
but fixed and documented.

### 7.5 Required tests

Cover L and R for each of the column-, row-, and normal-controlled axes, with
both positive and negative direction signs, proving paired acquisitions map to
the same canonical convention. Cover exact ties and below-gate obliquity.
Create a study conflict using a **non-selected** series. Cover cross-tag,
within-tag, tag/geometry, and cross-series conflicts. Verify atomic
no-transform behavior when one contributing plane cannot be canonicalized.
A single fixture per axis is insufficient — it cannot expose a sign error.

## 8. Encoder and study feature vector

Approved round 60 finding 4.

- **Encoder:** `facebook/dinov2-small`, attached offline as the Kaggle Model
  `metaresearch/dinov2` (`PyTorch/small`, Apache 2.0), 22,056,576 parameters,
  fully frozen (`requires_grad_(False)`, `.eval()`).
- **Embedding:** the CLS token, `last_hidden_state[:, 0, :]`, 384 dimensions,
  with `interpolate_pos_encoding=True` (336 differs from the native training
  resolution).
- **Within plane:** mean the 3-5 decoded slice embeddings.
- **Across planes:** mean the embeddings of **present planes only**. An absent
  plane is excluded from the mean — never imputed, never a zero vector inside
  the denominator.
- **Study vector: 388 dimensions** — 384 embedding + 3 plane-presence flags
  (Sagittal, Coronal, Axial) + 1 `laterality_reliable` flag.

**Known limitation, stated so it is not rediscovered later.** Every audit
measured 450/450 study-plane selections resolving, so on 58 training studies
all three presence flags are likely **constant `1`**: zero variance, a
coefficient unidentifiable from the intercept, shrunk to ~0 by L2. At the
frozen `0.90` gate roughly 2.7-2.8 of 58 studies are expected to carry
`laterality_reliable = 0`, so for a label of prevalence 0.2 the expected joint
count of (flag 0, label 1) is about 0.55 — frequently zero, across twelve
separate one-vs-rest problems. A constant presence flag genuinely carries zero
information; the near-constant laterality flag can technically be fit but its
effect **cannot be estimated reliably at this sample size**.

The flags are kept regardless: they are structurally correct, they become
informative if the labeled set grows, and they are cheap. They are left
**unscaled** (§9) because standardizing a near-constant column divides by a
near-zero standard deviation and manufactures a single high-leverage outlier,
which is the worse failure. **The specification does not claim, and the
implementation must not depend on, the head learning to compensate for a
missing plane.** Graceful degradation comes from excluding absent planes from
the mean, not from the flags.

## 9. Classifier and evaluation protocol

Approved round 60 findings 5-6, closed round 75.

**Estimator.** Reuse Phase 3A's shape
(`src/knee_mri/report_model.py::build_report_classifier`):
`OneVsRestClassifier(LogisticRegression(penalty="l2", solver="liblinear",
class_weight="balanced", max_iter=2000, random_state=42), n_jobs=1)` — but
with **`C = 0.1`**, not Phase 3A's `C = 1.0`. That value was tuned for a
50,000-feature sparse TF-IDF input; this is ~388 dense features on the same 58
studies, a much higher per-feature overfitting risk.

**`C` is frozen before evaluation.** Selecting `C` by maximizing pooled OOF
macro AUC and then reporting that maximum uses validation outcomes for
selection and yields an optimistic estimate — explicitly rejected. If the
first honest OOF run shows severe overfitting, the correct response is
**pre-registered nested CV** (choose `C` only inside each outer training fold,
with a corresponding inner selection on all 58 for the final refit), never
post-hoc re-tuning against the same OOF predictions.

**Scaling.** Fit a `StandardScaler` **inside each outer training fold**, on
the **384 continuous embedding dimensions only**; leave the four binary flags
unscaled. The frozen encoder has no fitted state, so global DINOv2 features
may be extracted **once** outside the fold loop; the scaler and classifier
must remain strictly fold-local.

**Folds.** Call `select_multilabel_folds` with Phase 3A's exact arguments —
`candidate_splits=(5, 4, 3, 2)`, `seed=42`. Fold assignment depends only on
`y`, but the algorithm is **row-order-sensitive**, so exact membership must
not be inferred from labels alone: **assert that the ordered 58 study IDs and
the label matrix match the Phase 3A input**, and persist and compare the fold
assignment signature. Only then is the image baseline's macro AUC directly
comparable to the report baseline's on identical validation studies.

**Metrics.** Pooled OOF macro AUC is the **primary** metric. Per-label and
per-fold AUC are **diagnostic only** — small-sample fold scores are noisy and
a score below 0.5 is not by itself evidence of a wiring error. Include Phase
3A's constant-prediction sanity assertion (a constant 0.5 prediction frame
must score exactly 0.5) to catch metric miswiring.

**Refit.** After evaluation, refit scaler and classifier on all 58 labeled
studies for inference.

## 10. Codec delivery

Approved round 60 finding 8; evidence closed round 75.

The corpus-wide census (kernel v10) read one representative header per series
across **all 24,386 series in both splits** and found a **single** transfer
syntax: `1.2.840.10008.1.2.1`, Explicit VR Little Endian, uncompressed. Zero
compressed syntaxes, zero unreadable headers, zero unclassifiable series.

This **contradicts** the competition's own data description recorded in
`docs/1_instructions.md` ("Mixed transfer syntaxes: uncompressed Explicit VR
Little Endian, JPEG Lossless, JPEG 2000, Implicit VR Little Endian"). None of
the three non-uncompressed syntaxes appears anywhere visible.

**Frozen disposition:**

- The requirement to *decode-test a sample of every observed compressed
  transfer-syntax UID* is **closed as not-applicable on evidence** — no such
  UID exists to sample.
- **Offline codec vendoring is retained.** The census reads one header per
  series, not every slice, and it cannot see the ~1,300-study hidden test set
  at all. All four codec packages (`pylibjpeg`, `libjpeg`, `openjpeg`, `gdcm`)
  remain unimportable in the Kaggle environment, so an unexpected compressed
  slice would fail to decode and silently fall through to the last-resort row,
  on data that cannot be inspected after scoring. Vendoring costs a few
  megabytes; the cost asymmetry mirrors §7.1's.

Vendoring follows Phase 3A's proven offline pattern: attach wheels as a
private dataset, verify **SHA-256** before install, install with `--no-index`,
check the return code explicitly (never `check=True`, which would embed the
resolved path in the exception), suppress stderr, and assert the installed
version afterwards. Freeze wheel filenames, versions, Python/platform
compatibility, checksums, and licenses in the implementation plan, plus an
**import smoke test**.

## 11. Notebook structure

Mirrors `notebooks/03_baseline_modeling.ipynb`'s reviewed skeleton:

1. Environment guard (`IS_KAGGLE`, `SEED`, `RuntimeError` on non-Kaggle).
2. Offline package verification — checksum, install, return code, version —
   then `sys.path` insertion, then the first `knee_mri` import, **in that
   order**.
3. DINOv2 discovery and GPU compatibility check.
4. Frozen-contract display: every constant in this document, so the run's
   exact configuration is visible and cannot silently diverge.
5. Per-study feature extraction (§3-§8).
6. CV with the reused folds, plus the constant-prediction sanity assertion.
7. Full-58 refit.
8. Identical test-time inference through the same code path.
9. Exactly **one** `to_csv("/kaggle/working/submission.csv")` call.
10. Persisted aggregate-only JSON summary.

**Privacy rules, enforced by `tests/test_notebooks.py`:** no `print`; no raw
report text, study identifiers, or row-level data displayed or persisted; only
allowlisted aggregate objects passed to `display()`; every displayed result
followed by an `Interpretation` markdown cell; committed output-free with null
execution counts; no internal workflow language in public prose.

## 12. Telemetry

Aggregate-only, no identifiers, persisted to the JSON summary. Required
because several contracts above are provably unexercised on sampled data and
can only be observed on the real run:

- Per-plane: candidates attempted, decoded-slice count distribution, retries
  triggered, planes absent.
- Selected-series and joint-study laterality fallback rates (the round-69
  substitute for another threshold-selection audit).
- The four **training-set flag variances** (§8), which directly test the
  constant-flag prediction.
- Count of test studies that hit the all-planes-absent prevalence fallback.
- Header-read failures, decode failures by transfer syntax.
- Complete end-to-end wall-clock timing (§13).

## 13. Release gates

All must pass before submission authorization is **requested**:

1. Full local suite green (`uv run pytest -q`), `uv run ruff check .` clean,
   `git diff --check` clean, notebooks output-free.
2. The §6 processor-equivalence test passes against the attached model.
3. No labeled training study reaches the all-planes-absent state (§4) — if one
   does, this gate **fails** and the data path is diagnosed.
4. A private full-pipeline dry run completes on the visible test studies.
5. A **representative private timing sample** spanning study, series, and
   slice-count strata measures the **complete** decode → preprocess → encoder
   → head path, extrapolated to the documented hidden-set size with a stated
   safety margin. The measured encoder-only lower bound is **not** sufficient
   evidence for this gate: it excludes selection logic, model loading,
   embedding materialization, the head's training and CV, and I/O contention.

   **This is not a theoretical objection — it was measured.** Across audits
   v3-v6 the three-series lower bound sat in a tight `0.172-0.194 h` band. In
   v8, which ran the corpus-wide census in the same kernel, it rose to
   `0.337 h` (1.74x the top of that band). The split is diagnostic: GPU
   forward time was unchanged at `0.0147 s/slice` (v6: `0.0147`), while
   **decode rose from `0.0167` to `0.0449 s/slice`, roughly 2.7x**. The
   census's 24,386 header reads contended for the same storage. Decode cost
   is therefore I/O-contention-sensitive and GPU cost is stable, so any bound
   measured on an otherwise-idle kernel **understates** a real run doing
   sustained feature-extraction I/O. Headroom against the 9-hour budget fell
   from ~50x to ~27x on that single change alone.
6. The private kernel completes successfully end to end.
7. Explicit user sign-off on the **exact kernel version**. Submission is
   kernel-native under coding standard section 11; no local CSV-only path.

## 14. Open items

- **OPEN — vendored codec wheel manifest.** Exact filenames, versions,
  Python/platform tags, SHA-256 checksums, and licenses are not yet chosen
  (§10). Belongs in the implementation plan.
- **OPEN — safety margin for gate 5.** The multiplier applied to the measured
  full-path extrapolation has not been fixed.
- **UNREVIEWED — this document's synthesis.** See the review caveat at the
  top.

## 15. Provenance

| Section | Approved in |
|---|---|
| Aggregation (shared-mean three-plane) | Round 46 |
| Architecture and data flow | Round 47 |
| Series ranking, validation, retry | Round 50; implemented 51-58 |
| Physical framing | Round 61 |
| Intensity contract | Rounds 61-62, 64 |
| Laterality algorithm | Rounds 64-65 |
| Laterality threshold `> 0.90` | Rounds 67-70 |
| Embedding, folds, decode/retry, notebook, release gates | Round 60 |
| Classifier and decode/retry closure | Rounds 70, 75 |
| Codec evidence and disposition | Round 75 |

Measured evidence: `docs/7_image_baseline_insights.md` v1-v8.
