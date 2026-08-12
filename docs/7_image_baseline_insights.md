# Image Baseline Insights

Append-only log of real measurements informing the Phase 3B image-baseline
pipeline design (see `docs/3_strategy.md` Phase 3, `docs/collaboration/active_task.md`
round 38's finding 3, and the Phase 3B design proposal in round 37). One
section per notebook version/run; never edit a past entry once a later one
supersedes it — append a correction instead.

## 2026-08-11 — Preflight audit v1 (`04_image_baseline_preflight.ipynb`)

**Kernel:** `tuannm3812/rsna-knee-image-baseline-preflight-audit`, version 3
(versions 1–2 hit a title-length rejection and an unhandled GPU-compute-
capability crash respectively — see disposition below). **Code:**
`rsna-knee-mri-src` dataset version published from commit `7455910`
(`src/knee_mri/series_audit.py`). **Data:** full `train_series.csv`
(24,371 series) / `test_series.csv` (15 series across the 3 example test
studies) for the metadata-only checks; a deterministic seed-42 sample of 150
train studies (822 series) for the DICOM geometry/decode audit and a
30-series sub-sample of that for the GPU timing probe. Aggregate counts,
rates, and distributions only — no report text, study/series identifiers, or
per-study predictions left Kaggle.

### `Fluid_Sensitive` / `Fat_Suppression` are perfectly redundant

Agreement rate **1.0** on both train (24,371/24,371 series) and test
(15/15 series): `fluid1_fat0` and `fluid0_fat1` are both exactly 0. The two
columns take the identical value on every single series in this dataset —
not a coincidental correlation, but the same signal recorded twice. This
confirms the open question `docs/2_eda_insights.md` flagged from matching
aggregate means alone. **Design implication:** treat `Fluid_Sensitive` and
`Fat_Suppression` as one signal; `select_primary_series`'s
`prefer_fluid_sensitive` branch and any future fat-suppression-based feature
carry the same information, not independent ones.

### Every study has series in all three planes

`has_all_three_planes` is **1.0** for both train (4,407/4,407 studies) and
test (3/3 studies) — every study has at least one Sagittal, one Coronal, and
one Axial series, with `has_<plane>` also 1.0 individually. **Design
implication:** plane coverage is not a limiting factor for a multi-plane
image baseline; the earlier concern (round 38 finding 4) that a
multi-plane design might need heavy fallback/presence-mask handling for
missing planes is not supported by this measurement — coverage is complete.
This does not by itself decide the single-series-vs-multi-plane scope
question (that also depends on the GPU runtime budget, still open — see
below), but it removes one argument against multi-plane.

### `InstanceNumber` order agrees with true DICOM geometry order

Across all 822 audited series: geometry-tag coverage **1.0** (every slice
has both `ImagePositionPatient` and `ImageOrientationPatient`), order
agreement mean `|r|` **1.0**, fraction with `|r| > 0.99` **1.0**, fraction
with `|r| <= 0.9` **0.0**. `InstanceNumber` order and geometry-derived order
agree on every sampled series, no exceptions. **Design implication:**
round 38's finding 3 correction is now resolved with a direct measurement,
not just the earlier caution about it: `src/knee_mri/dicom_io.py::load_series`'s
existing `InstanceNumber`-based sort does **not** need to change to
geometry-based ordering for this dataset. This reverses the working
assumption carried over from the public reference notebooks (which measured
a different, unreliable ordering — raw filename/SOP-UID order — not
`InstanceNumber`).

### `Laterality` tag: reliable when present, missing ~18% of the time

`Laterality` tag coverage **0.8187** — present on ~82% of the 822 audited
series, absent on the remaining ~18%. Conflict rate among series where
**both** the tag and the geometry-derived call are resolvable: **0.0076** —
the tag agrees with geometry 99.24% of the time when both are available. **Design
implication:** the geometry-derived `laterality_from_geometry` fallback is
needed primarily to *fill* the ~18% of series with no tag at all, not to
*correct* the tag where it exists — the tag itself is not the unreliable
part; its coverage is.

### Decode reliability: 0 failures observed, with one open caveat

Decode failure rate **0.0** across 822 series (5 central-band slices each,
~4,110 full pixel decodes attempted). However, the codec-availability check
found none of `pylibjpeg`, `pylibjpeg-libjpeg`, `pylibjpeg-openjpeg`, or
`gdcm` importable in this kernel environment. Zero failures despite no
checked codec package being present means either the sampled slices'
transfer syntaxes didn't require any of those four packages specifically, or
Kaggle's default image decodes them through a mechanism this check didn't
name. **Not fully explained — flagged rather than assumed.** The measured
0% failure rate stands on its own regardless of which explanation is true,
but this should be re-checked against a larger or differently-sampled
population before being treated as a permanent guarantee.

### Pixel spacing and slice count confirm known constraints

Pixel spacing: mean 0.327mm, std 0.119mm, min 0.137mm, max 1.172mm (a
&gt;8× range) — confirms physical-millimeter cropping is necessary, a fixed
pixel crop would cover meaningfully different real-world extents per study.
Slice count: mean 34.3, median 30, min 11, max 320 — closely replicates
`docs/2_eda_insights.md`'s independent "first 200 studies" sample (mean
35.45, median 30, max 320), a useful cross-check between two different
sampling approaches.

### GPU timing: not measured — a reproducible platform constraint, not a fluke

Both GPU-enabled runs (versions 2 and 3) were allocated a **Tesla
P100-PCIE-16GB** (CUDA compute capability 6.0). The Kaggle image's
preinstalled `torch==2.10.0+cu128` only supports compute capability 7.0+
(`sm_70` and above) — the DINOv2 forward pass cannot run at all on this
hardware/software combination. Version 2's first attempt crashed the whole
kernel run on this (`AcceleratorError: CUDA error: no kernel image is
available for execution on the device`); version 3 added an explicit
compute-capability check so this is now a clean, reported finding
(`GPU compatible with installed PyTorch build: false`) rather than a crash.
Getting the same P100 on two independent runs suggests this may not be
random per-session luck for this account/competition's GPU pool — worth
confirming with a further attempt (or Kaggle's `--accelerator` push flag,
untested) before assuming it is unresolvable. **Open:** the GPU runtime
projection needed to settle the single-series-vs-multi-plane scope decision
does not exist yet.

### Disposition

Kernel push required two corrections before a clean run: version 1 was
rejected server-side (`"The title cannot exceed 50 characters"` — a Kaggle
kernel title hard limit not documented anywhere in this project, now
recorded), and version 2 crashed with the GPU-compute-capability error above
before the resilience fix was added. Both fixes are in
`docs/collaboration/active_task.md` round 39. Every result above comes from
version 3's persisted `/kaggle/working/preflight_audit_summary.json` — the
Kaggle kernel-output API does not expose rendered `display()` output for
notebook-type kernels, only files written to `/kaggle/working` and a plain
stderr/traceback log, discovered only after version 2's crash left nothing
retrievable; version 3 added the persisted-JSON step this project should now
carry forward to future GPU/notebook kernels needing result retrieval.

**Superseded by v2 below**: the "InstanceNumber order agrees with true DICOM
geometry order" and "Laterality tag: reliable when present, missing ~18% of
the time" and "Decode reliability... one open caveat" sections above used
absolute-value order-agreement, first-slice-only laterality checks, and
wrong codec module names respectively — each corrected with materially
different real numbers in v2. This v1 entry is left as-written (not edited)
per this file's own append-only convention; treat v2's numbers as
authoritative for design decisions.

## 2026-08-12 — Preflight audit v2 (`04_image_baseline_preflight.ipynb`)

**Why this round exists:** Codex's round-40 review of v1 found five real
problems — absolute-value order-agreement can't show slice direction,
laterality was only checked on each series' first slice (contradicting
`SeriesAudit`'s own docstring) and never validated tag values, the codec
probe used two module names that don't exist, the GPU timing projection
targeted all 4,407 train studies instead of the actual workload, and
several documentation/prose issues (detailed in
`docs/collaboration/active_task.md` round 40). All five are fixed in
`src/knee_mri/series_audit.py` and the notebook (round 41). Two of the
"fixes" turned out to change the substantive conclusion, not just its
precision — flagged explicitly below.

**Kernel:** `tuannm3812/rsna-knee-image-baseline-preflight-audit`, version 4,
pushed with `scripts/push_kaggle_kernel.sh image-baseline-preflight
NvidiaTeslaT4` (an explicit accelerator request, per round 40 finding 4 —
this got a compatible Tesla T4 instead of another P100). **Code:**
`rsna-knee-mri-src` dataset version **8**, published from commit `7e814ef`
(exact version number now recorded per round 40 finding 5's ask). **Data:**
same sampling as v1 — full `train_series.csv`/`test_series.csv` for the
metadata checks, the same seed-42 150-study/822-series sample for the
geometry/decode audit, the same 30-series sub-sample for GPU timing.

### Correction — `InstanceNumber` order is monotonic per series, but its physical direction varies across series

Signed order agreement: mean **0.2506** (not the ~1.0 v1's `|r|` framing
implied), fraction monotonic (`|r| > 0.99`) **1.0** (unchanged — every
individual series is still perfectly internally ordered, in one direction
or its exact reverse), fraction same-direction (`r > 0`) **0.6253**,
fraction reversed (`r < 0`) **0.3747**. **This changes the practical
conclusion, not just its precision**: `InstanceNumber` does **not**
reliably indicate a fixed physical direction (e.g. "always superior-to-
inferior") across series — about 3 in 8 sampled series have it running the
opposite way from the rest. **Design implication:** for a symmetric
central-band slice sample pooled by an order-invariant operation (e.g. mean
pooling — the round-37 proposal's plan), this doesn't matter, since a
central band around the middle of the stack is the same set of slices
regardless of direction. It would matter for anything that assumes a
consistent physical direction across series (e.g. directional attention
over ordered positions, or stacking slices as ordered channels) — that kind
of design would need geometry-based ordering, not `InstanceNumber`, per
series.

### Correction — laterality coverage is lower than v1 measured, but geometry fills nearly all of the gap

`Laterality`/`ImageLaterality` tag coverage (validated `L`/`R` values, every
slice checked): **0.5255** — materially lower than v1's 0.8187, because v1
only checked the first slice and counted *any* value (including empty/
invalid ones) as "present"; v2 checks every slice and rejects anything but
a valid `L`/`R`. Tag-internal consistency **1.0** (includes series with no
valid tag at all, trivially consistent). The number that actually answers
"does geometry fill the gap": **`laterality_filled_by_geometry` among
tag-missing series is 0.9692** — of the ~47% of series without a usable
tag, geometry resolves 96.9% of them. Combined effective coverage
(tag-or-geometry) is therefore ≈98.5%. Conflict rate among series where
both are resolvable: **0.0118** (comparable to v1's 0.0076 — the tag
remains reliable when present). **Design implication:** the geometry
fallback is not a minor supplement, it's doing the majority of the work for
the ~47% of series the tag alone can't call — a tag-plus-geometry pipeline
needs the geometry path to be correct and always attempted, not treated as
a rare edge case.

### Correction — decode reliability is now fully explained, not just observed

`decode_by_transfer_syntax` shows **every single one of the 4,110 attempted
decodes used transfer syntax `1.2.840.10008.1.2.1` (Explicit VR Little
Endian, uncompressed)** — zero JPEG Lossless or JPEG 2000 slices appeared
in this sample at all. That fully explains v1's "0% failures despite no
codec package available" caveat: no codec was needed because nothing
compressed was encountered, not because decoding compressed data
mysteriously worked. The (corrected) codec-availability check still shows
none of `pylibjpeg`, `libjpeg`, `openjpeg`, or `gdcm` importable in this
Kaggle kernel environment. **Design implication:** this sample says nothing
about whether compressed-syntax slices (which the competition description
says exist) would decode successfully here — if a real pipeline run
encounters one, it would very likely fail given no codec package is
present. A future preflight pass (or the real pipeline itself) should
either sample specifically for compressed syntaxes or vendor a codec
package offline as a precaution, not assume this 0%-observed rate
generalizes.

### New — `PixelSpacing` tag coverage

**1.0** — every one of the 822 audited series carries a `PixelSpacing` tag
(v1 only reported the *range* among series that had it, not whether all did
— now closed).

### Resolved — GPU timing, measured for real

With a Tesla T4 (compute capability 7.5, compatible with the installed
`torch==2.10.0+cu128`): decode 0.0105s/slice, DINOv2-small GPU forward pass
0.0185s/slice, ≈0.145s/series (5 slices) including both. Projected against
the **actual workload** (58 gold-labeled train studies + the documented
~1,300-study hidden test set = 1,358 studies, not all 4,407 train studies —
round 40 finding 4's correction): **one series per study ≈ 0.055 hours
(≈3.3 minutes)**; **three series per study, the compact multi-plane
candidate (one selected series per anatomical plane) ≈ 0.164 hours (≈9.8
minutes)**. Both are a small fraction of the competition's 9-hour budget —
roughly 55× headroom even for the more expensive three-series design. This
is a lower-bound estimate: it measures only DICOM decode and the encoder's
GPU forward pass on already-selected series, not series-selection logic,
a training dataloader, or concurrent I/O contention.

**Design implication — this materially changes the single-series-vs-
multi-plane scope question**: round 37 proposed a minimal single-series
design partly on complexity/speed grounds; that reasoning no longer holds
on the runtime axis specifically. Combined with plane coverage being 1.0
(every study has all three planes — v1 finding, unchanged) and the
compact multi-plane design costing under 10 minutes end to end, runtime is
not a real constraint against choosing the compact three-series design over
the minimal one-series design. This doesn't decide the choice by itself —
model complexity, code complexity, and expected accuracy still matter — but
the runtime argument for staying minimal is gone.

### Disposition

`uv run pytest -q` → `181 passed` (23 in `test_series_audit.py`, up from
18, covering the new laterality/decode-result fields); `uv run ruff check .`
→ clean; kernel version 4 completed (`KernelWorkerStatus.COMPLETE`) on the
first T4-targeted attempt. Returned for the user's and Codex's review —
still no Phase 3B design spec written; the single-series-vs-multi-plane
choice is now well-informed on both plane-coverage and runtime grounds but
remains the user's call to make.
