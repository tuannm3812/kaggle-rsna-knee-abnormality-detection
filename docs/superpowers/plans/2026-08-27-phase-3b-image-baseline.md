# Phase 3B Image Baseline Implementation Plan (Approved Sections Only)

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Scope — read this before anything else.** This plan implements **only
specification sections 2-9**, the sections the user has approved
(`docs/superpowers/specs/2026-08-26-phase-3b-image-baseline-design.md`, whose
authority table is definitive). It deliberately **excludes**:

| Excluded | Why |
|---|---|
| §10 codec disposition | Recommended in round 75, never confirmed — Codex was withdrawn before replying |
| §11 notebook structure | No round records user approval |
| §12 telemetry | Individual items trace to rounds; the section does not |
| §13 release gates | Round 75 states plainly they "remain open" |

**Those four sections gate everything after Task 8.** No notebook, no Kaggle
run, and no submission is in scope here. When Tasks 1-8 are complete the
pipeline exists as tested library code and stops there, awaiting the user's
decision on §10-§13.

**Goal:** Build the study-level image feature pipeline and evaluation harness
as small, independently tested `knee_mri` modules — series selection through
frozen-encoder features to a fold-local classifier — with every constraint
discovered during design validation enforced by a test rather than a comment.

**Tech stack:** Python 3.13, NumPy, pandas, pydicom, PyTorch, Transformers
(optional extra), scikit-learn, pytest, Ruff.

## Global constraints

- Work on the shared `main` checkout. Small, self-contained commits; never
  commit a red gate. `uv run pytest -q` and `uv run ruff check .` must pass
  before every commit.
- **No Phase 3B modeling code runs on Kaggle under this plan.** No kernel
  push, dataset refresh, publication, or submission.
- Every frozen constant comes from the specification, not from memory. The
  four ordering tolerances are `0.999`, `0.01 mm`, `0.01`, `0.01`; the
  laterality gate is `dominant_abs_x > 0.90`; the image size is `336`;
  `C = 0.1`; folds are `candidate_splits=(5, 4, 3, 2)`, `seed=42`.
- **The `0.90` gate must be described in code comments and docs as a
  cost-asymmetry safety choice supported by measured coverage, not an
  empirical separation point** (round 69's required wording).
- Reuse existing validated helpers rather than reimplementing:
  `validate_and_order_series`, `central_band_indices`,
  `patient_lr_axis_metrics`, `laterality_from_geometry`,
  `aggregate_group_laterality`, `select_multilabel_folds`, `macro_auc`,
  `per_label_auc`.
- Never display or persist report text, study or series identifiers, pixel
  data, or row-level predictions.
- Absent planes are excluded from means, never imputed. Nothing is silently
  reordered, guessed, or filename-sorted.

---

### Task 1: Enforce the `PixelSpacing` precondition (§5, currently unimplemented)

**Why first:** §5 states a candidate with unusable `PixelSpacing` is
`unusable`, and cross-references §3 — but `validate_and_order_series` reads
**no** `PixelSpacing` at all. Verified in round 78: a two-slice series with
the tag **absent**, **negative**, or **zero** returns
`usable=True, method="geometry"`. Framing cannot be trusted until this holds.

**Files:** modify `src/knee_mri/series_audit.py`, `tests/test_series_audit.py`.

**Steps:**
- [x] Write failing tests: spacing absent, zero, negative, non-finite,
      wrong VM (1 element), and inconsistent across slices must each give
      `usable=False`.
- [x] Write a passing test: consistent positive finite spacing still
      validates by geometry, so no existing behavior regresses.
- [x] Add the check to the validation path under the existing narrow
      exception policy (`InvalidDicomError`, `OSError`, `ValueError`,
      `TypeError`, `AttributeError`, `IndexError`).
- [x] Re-run the full suite. NOTE: existing geometry fixtures omitted
      `PixelSpacing` entirely, so both slice writers now supply a realistic
      default; two round-77 assertions changed by design. This may also change
      the real-data 822/822 result, since the audit measured tag *presence*
      only (round 86).

**Verification:** all new tests pass; `uv run pytest -q` green; the retry
loop in `dataset.py` needs no change because unusable candidates already
trigger it.

---

### Task 2: Vendor the DINOv2 preprocessor config

**Why:** §6 mandates a **local** test comparing the manual pipeline against
the Transformers image processor. Round 82 established that cannot run:
`transformers` is an uninstalled optional extra and `preprocessor_config.json`
ships with the Kaggle model mount. The test needs only `image_mean` /
`image_std`, not the weights.

**Files:** create `vendor/dinov2-small-preprocessor_config.json` and its
license note; modify `pyproject.toml`, `scripts/publish_code_dataset.sh`,
`tests/test_vendor_assets.py`.

**Steps:**
- [x] Vendor the config verbatim with its **CC BY-NC 4.0** attribution (the pinned artifact's actual licence; round 86).
- [x] Test that the vendored file parses and exposes `image_mean` and
      `image_std` as 3-element numeric lists, pinned by SHA-256.
- [x] Test that `publish_code_dataset.sh` stages it, mirroring the existing
      wheel-staging assertion. (No script change needed -- it copies `vendor/`
      wholesale.)
- [x] Add `transformers` to the **dev** extra (a required local test is not
      optional). Installed: transformers 5.15.0 alongside torch 2.13.0.

**Verification:** vendor tests pass; `importlib.util.find_spec("transformers")`
is not `None` in the dev environment.

---

### Task 3: Physical framing — letterbox (§5)

**Files:** create `src/knee_mri/framing.py`, `tests/test_framing.py`.

**Steps:**
- [x] Failing test: output is exactly `336 x 336` for square, portrait,
      landscape, and both extreme aspect ratios.
- [x] Failing test: the longer physical side maps to `336`; the shorter is
      `floor(value + 0.5)` clamped to `[1, 336]`.
- [x] Failing test: padding splits evenly with the **extra pixel on the
      bottom or right**.
- [x] Failing test: no anatomy is cropped — corner markers survive inside
      the resized region.
- [x] Implement using `F.interpolate(..., mode="bilinear", antialias=True)`
      (confirmed available on torch 2.13.0) and `F.pad(..., value=0.0)`.
- [x] Document in the module docstring that padding is **36-50% of the input
      for ordinary anisotropic acquisitions** and maps to roughly `-2.12`
      after §6 standardization — i.e. it is not neutral. Do **not** change
      the pad value; §5 is approved and this is recorded for the user.

**Verification:** DONE -- 21 framing tests pass; worst relative aspect error
`0.5714%` across the realistic band; padding share measured at 36.0% / 36.0% /
50.0% and pad-`0` at `-2.118 / -2.036 / -1.804` against the *vendored* config,
matching rounds 81 and 86 exactly.

---

### Task 4: Intensity contract (§6)

**Files:** create `src/knee_mri/intensity.py`, `tests/test_intensity.py`.

**Steps:**
- [x] Failing test: the padding mask is built in the **stored-value domain
      before** the modality transform, including the inclusive interval when
      both `PixelPaddingValue` and `PixelPaddingRangeLimit` are present.
      Round 82 measured that a post-transform mask catches **0 of 2** padding
      pixels under `slope=2, intercept=-1024`.
- [x] Failing test: `MONOCHROME1` is inverted so higher means brighter.
- [x] Failing test: **`p99 <= p1` is the insufficient-variation criterion**
      (§6 step 4 leaves "insufficient" undefined; pin it). Constant,
      all-padding, and sparse-bright slices must all raise the
      decode-failure signal; a normal slice must not.
- [x] Failing test: per-slice `p1`/`p99` clip and rescale to `[0, 1]`, with
      excluded padding mapped to `0`.
- [x] Failing test: **processor equivalence** — the final tensor matches the
      Transformers image processor built from the Task 2 vendored config with
      `do_resize=False, do_rescale=False`, **and `do_center_crop=False`** --
      the real config enables centre-crop to 224, which would crop the 336x336
      letterboxed input and compare a different image (round 86).
- [x] Failing test: missing or malformed processor metadata raises a hard
      error; assert no ImageNet constant appears anywhere in the module.
- [x] Implement steps 1-7 in the specified order.
- [x] Add a comment recording that the `MONOCHROME1` inversion reference is
      immaterial **only because** step 5 is per-slice percentile
      normalization — the equivalence breaks if bounds ever become
      per-series pooled or VOI-driven (round 82).

**Verification:** DONE -- 26 intensity tests pass, including processor
equivalence running **locally** at `atol=1e-5` (measured max difference
`3.7e-07`). Confirmed the centre-crop guard is load-bearing: leaving
`do_center_crop` on yields `(3, 224, 224)` instead of `(3, 336, 336)`.

---

### Task 5: Laterality canonicalization (§7)

**Files:** create `src/knee_mri/laterality.py`, `tests/test_laterality.py`.

**Steps:**
- [x] Failing tests, axis selection: `dominant_abs_x > 0.90` strictly —
      exactly `0.90` rejected, `0.9001` accepted; exact ties, degenerate,
      zero, and non-finite orientations all non-canonicalizable.
- [x] Failing tests, signed rule: reverse exactly when
      `medial_x_sign * selected_axis_x > 0`, covering **all 12** combinations
      of {columns, rows, slices} x {L, R} x {stored +X, -X}. Assert medial
      ends at decreasing index in every case, and that paired L/R
      acquisitions produce identical canonical volumes.
- [x] Failing test: the canonical target is `medial-toward-decreasing-index`
      and is **not** expressible as "make everything look like a left knee" —
      unreversed is a left knee for axial/coronal but a **right** knee for
      sagittal.
- [x] Failing tests, consensus: conservative resolver over **all** study
      series (not only selected ones); any cross-tag or tag/geometry conflict
      anywhere makes the study unreliable; a **non-selected** series can veto.
- [x] Failing test, atomic application: if any contributing plane cannot be
      canonicalized, **no** plane is transformed and `laterality_reliable = 0`.
- [x] **Failing test, single application (round 79's hazard):**
      canonicalization is **not idempotent** — flipping the array leaves the
      DICOM tags unchanged, so a second pass reverses again and silently
      restores the original orientation, undetectably. Implement an explicit
      applied-flag carried with the volume (preferred: it makes double
      application raise rather than corrupt) and test that a second call
      raises instead of flipping.
- [x] Implement, reusing `patient_lr_axis_metrics` and
      `aggregate_group_laterality`.

**Verification:** DONE -- 33 laterality tests pass. The double-application
guard raises `AlreadyCanonicalizedError` rather than silently reverting.
Note: the first run exposed a bug in the *test* fixture (inverted sign labels
for the `slices` orientations), not the implementation -- the 12-combination
test derives its expectation from the code under test rather than trusting
the labels, which is why it passed while the hand-written one failed.

---

### Task 6: Slice sampling, decode, and per-plane fallback (§4)

**Files:** create `src/knee_mri/slice_sampling.py`,
`tests/test_slice_sampling.py`.

**Steps:**
- [x] Failing test: five deterministic central-band indices from the
      validated order via `central_band_indices`.
- [x] Failing test: **at least three successful decodes required**; mean over
      the 3-5 that succeeded.
- [x] Failing test: below three, the series fails and the next ranked
      same-plane candidate is tried; the plane is absent only after
      exhaustion.
- [x] Failing test: **stacks of exactly 1, 2, or 4 slices can never satisfy
      the minimum** — rounding collapses duplicate positions. NOT monotonic:
      3 slices yield `[0, 1, 2]` and CAN meet it, 4 yield only `[1, 2]` and
      cannot. Round 83's "four or fewer" was wrong; corrected round 87.
      Unreachable on observed data (shortest corpus series has 11 slices).
- [x] Failing test: counters for attempted, decoded, retried, and absent are
      returned as aggregates with **no identifiers**.
- [x] Implement.

**Verification:** DONE -- 19 sampling tests pass; `counters()` exposes only
`{attempted, decoded, candidates_tried, absent}` and a test asserts no path,
directory name, or `.dcm` string appears in its repr.

---

### Task 7: Study feature assembly (§2 flow, §8 embedding)

**Files:** create `src/knee_mri/study_features.py`,
`tests/test_study_features.py`.

**Steps:**
- [ ] Failing test: the study vector is **exactly 388** dimensions — 384
      embedding + 3 plane-presence flags + 1 `laterality_reliable`.
- [ ] Failing test: within-plane mean over decoded slices, then mean over
      **present planes only**; an absent plane is excluded from the
      denominator, never zero-filled into it.
- [ ] Failing test: encoder is frozen — no parameter has `requires_grad`, and
      the module is in `eval()` mode.
- [ ] Failing test: the pipeline order is framing → intensity → laterality →
      encode, and laterality is applied exactly once per study.
- [ ] Implement against a stub encoder in tests so no model download is
      needed; the real encoder is injected.
- [ ] Document that with 58 studies the four flags are near-degenerate
      (all-450/450 plane resolution measured, so presence flags are likely
      constant `1`; ~2.75 of 58 expected `laterality_reliable = 0`), so the
      head **cannot** be relied on to learn plane compensation.

**Verification:** all feature tests pass; dimensionality asserted exactly.

---

### Task 8: Classifier and evaluation protocol (§9)

**Files:** create `src/knee_mri/image_model.py`,
`tests/test_image_model.py`.

**Steps:**
- [ ] Failing test: fold identity — assert the ordered 58 study IDs and label
      matrix match the Phase 3A input, and persist/compare a fold-assignment
      signature. `select_multilabel_folds` is row-order-sensitive, so exact
      membership must not be inferred from labels alone.
- [ ] Failing test: **fold-locality of the scaler and classifier.** Round 80
      found the harness had **no** classifier-leakage test at all: fitting on
      every row left the suite green while inflating pooled OOF AUC. Assert
      per-fold training row counts equal the training-fold sizes and are
      always strictly less than the total.
- [ ] Failing test: `StandardScaler` is fitted **inside** each outer training
      fold, on the 384 continuous dimensions only, with the four binary flags
      left unscaled.
- [ ] Failing test: `C = 0.1` frozen before evaluation; assert no code path
      selects `C` from OOF scores.
- [ ] Failing test: pooled OOF macro AUC is primary; per-label and per-fold
      are diagnostic; a constant `0.5` prediction frame scores exactly `0.5`.
- [ ] Failing test: full-58 refit of scaler and classifier for inference.
- [ ] Implement, reusing `select_multilabel_folds`, `macro_auc`,
      `per_label_auc`, and the frozen estimator shape with `C = 0.1`.

**Verification:** all model tests pass; a deliberately leaked fit is caught
by the fold-locality test (confirm by temporary mutation, then revert).

---

## Stop here

After Task 8 the pipeline exists as tested library code with no Kaggle
surface. **Do not proceed to a notebook, a kernel run, a timing sample, or a
submission** — those live in §11-§13, which are unapproved proposals. Return
to the user with the completed tasks and the §10-§13 decision outstanding.

## Self-review

Checked before commit: no `TBD`/`TODO` placeholders; every task names its
verification; no task depends on an unapproved section; Task 2 precedes Task
4 because the equivalence test needs the vendored config; Task 1 precedes
Task 3 because framing depends on validated spacing; no task instructs a
Kaggle action; and every constraint discovered in rounds 79-84 appears in the
task that must enforce it.
