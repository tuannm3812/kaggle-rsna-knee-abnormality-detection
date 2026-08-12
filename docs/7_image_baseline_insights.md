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

**Superseded by v3 below**: Codex's round-42 review found the "same
direction"/"reversed" order-agreement labels above imply a cross-series-
comparable physical direction the measurement doesn't establish (each
series' sign is relative to its own geometry-derived normal); the
"filled by geometry" and "conflict rate" laterality numbers omitted a
possible `Laterality`-vs-`ImageLaterality` silent disagreement and never
aggregated to the study level round 40 originally asked for; and "under 10
minutes end to end" overstates what was actually measured (decode + GPU
forward pass only). v3 corrects all three and adds the study-level
laterality result. This v2 entry is left as-written per this file's
append-only convention; treat v3's numbers and framing as authoritative.

## 2026-08-12 — Preflight audit v3 (`04_image_baseline_preflight.ipynb`)

**Why this round exists:** Codex's round-42 review of v2 found the signed
order-agreement result still over-interpreted as a shared physical
direction, a silent `Laterality`/`ImageLaterality` cross-tag conflict case,
missing study-level laterality aggregation (round 40's original ask, not
yet delivered in v2), an overstated "end to end" runtime claim, and several
stale/broad public claims (wrong round citation, "the approved design" for
an unapproved proposal, an Phase 4 lever assuming test-time report access,
an unscoped "every study has all three planes" claim). Full findings:
`docs/collaboration/active_task.md` round 42; user approval to implement
and rerun: round 43.

**Kernel:** `tuannm3812/rsna-knee-image-baseline-preflight-audit`, version
5, pushed with `scripts/push_kaggle_kernel.sh image-baseline-preflight
NvidiaTeslaT4`. **Code:** `rsna-knee-mri-src` dataset version **9**,
published from commit `756f7f5`. **Data:** identical sampling to v1/v2
(seed 42, 150 studies, 822 series, 30-series GPU timing sub-sample).

### Correction — the order-agreement sign is not a cross-series-comparable direction

The v2 numbers (mean signed r 0.2506, 62.5%/37.5% positive/negative split)
are unchanged in value, but the framing was wrong: `order_agreement`'s sign
is relative to each series' own `ImageOrientationPatient`-derived normal
(`row_direction × column_direction`), which is not canonicalized to one
shared anatomical axis across series or planes. Reporting positive/negative
fractions as "same direction"/"reversed" implied a cross-series comparison
the measurement doesn't make. **The narrower, actually-supported
conclusion, unchanged from v2's practical guidance**: `InstanceNumber` is
adequate for a symmetric central-band slice sample pooled by an order-
invariant operation (mean pooling), since `fraction monotonic (|r| > 0.99)`
remains **1.0** — every individual series is still perfectly internally
ordered, in some direction. It would not be adequate for any design
assuming a consistent physical direction across series without first
canonicalizing geometry to a fixed axis.

### Correction — no cross-tag conflicts found, but the check now actually exists

`Laterality tag coverage` is now reported in three buckets: **complete
(every slice) 0.5255**, **partial (some slices) 0.0**, **none 0.4745** — no
series in this sample had a tag on only some of its slices; it's an
all-or-nothing property per series here. New:
**`Laterality cross-tag conflict rate` (a single slice with both a valid
`Laterality` and a disagreeing valid `ImageLaterality`) is 0.0** — not
found in this sample, but this is now a real, explicit check rather than a
silent precedence choice hiding the possibility (`_slice_laterality_tag`
picking `Laterality` over a disagreeing `ImageLaterality` with no
visibility into whether that happened, round 42's finding 2). `Laterality
filled by geometry (of tag-missing series)` **0.9692** and `Laterality
conflict rate (resolvable)` **0.0118** are unchanged from v2 (correct
already).

### New — study-level and per-plane laterality agreement

The number round 40 originally asked for and v2 didn't deliver: across the
150 sampled studies, grouping by study (ephemerally, in-memory only —
never persisted), **100% of studies (150/150) have at least one resolved
laterality call**, and **100% of resolved studies are internally
consistent** — every series within a study that resolves a call agrees
with every other. Restricted to just the first sampled series encountered
per plane (**not** the actual frozen series selector, which prefers
`Fluid_Sensitive == 1` within a plane — round 42's finding 2, corrected
after round 45 caught the mislabeling): **98.7% (148/150) have at least
one resolved call**, still **100% consistent** among those. **Design
implication**: no internal laterality contradiction was found anywhere in
this sample, at either the series or study level. The all-series result is
the more directly applicable one for the now-approved architecture (round
47): laterality consensus is derived from every available series header at
the study level, not coupled to which specific series an image selector
picks.

### Correction — GPU timing reframed as a measured-component lower bound

Re-measured on a fresh T4-targeted run: decode 0.0161s/slice, GPU forward
0.0144s/slice (both close to v2's numbers; some run-to-run hardware
variance is expected). Lower-bound hours: one series per study **0.0574**,
three series per study **0.1722** (≈10.3 minutes) — materially the same
conclusion as v2, still roughly 52× headroom against the 9-hour budget for
the three-series design. **What changed is the framing, not the numbers**:
this measures only DICOM decode and the frozen encoder's GPU forward pass
on already-selected series — not series-selection logic, host-to-device
transfer beyond the timed batch, model loading, embedding materialization,
classifier-head training/CV, a training dataloader, or concurrent I/O
contention. It supports the narrow conclusion that encoder runtime
specifically doesn't favor the single-series design over the compact
three-series one; it is not an end-to-end guarantee for either.

### Correction — stale/broad claims fixed

`docs/3_strategy.md` now cites round 38 (not round 40) for the Phase 3C
fusion-infeasibility finding, and its Phase 4 lever no longer suggests a
test-time text-plus-image ensemble (test reports don't exist) — reworded to
diverse image representations/planes or a separately gated report-derived
teacher role. The notebook's GPU-timing comment no longer calls the
unapproved Phase 3B proposal "the approved design." Plane coverage's exact
scope: **1.0 across all 4,407 observed train studies and the 3 visible
test example studies — not confirmed for the actual ~1,300-study hidden
test set**, which the eventual Phase 3B design should still handle with an
explicit missing-plane fallback rather than assuming universal coverage
holds there too.

### Disposition

`uv run pytest -q` → `193 passed` (`test_series_audit.py` grew from 23 to
35 tests, covering cross-tag-conflict detection, the resolved-call field,
`anatomically_ordered_paths`, and `aggregate_group_laterality`); `uv run
ruff check .` → clean; kernel version 5 completed
(`KernelWorkerStatus.COMPLETE`) on the first attempt. Returned for the
user's and Codex's review. Codex's round-42 disposition, if v3 is accepted,
recommends drafting a compact three-plane Phase 3B design (symmetric
five-slice sampling, order-invariant pooling, explicit missing-plane
masks/fallbacks, frozen DINOv2-small, a low-capacity multilabel head on the
established folds, and offline compressed-DICOM codec support planned for,
since this sample never exercised one) — still not started, and still
requiring its own write-up, independent review, and user approval before
any implementation begins.

**Local corrections after round 45 (no rerun needed — Codex's review
confirmed kernel version 5's (preflight v3's) measurements are
unaffected):** `anatomically_ordered_paths`
fell back to filename order when geometry tags were incomplete, contradicting
the very evidence that justified writing it (`InstanceNumber`, not filename
order, is the empirically-reliable proxy in this corpus) — fixed to fall
back to `InstanceNumber` order, with filename order only as a final,
deterministic tie-break for missing/duplicate/invalid instance numbers. This
never affected v3's reported numbers since the audited sample had 1.0
geometry-tag coverage throughout. `laterality_resolved_call`'s docstring
overstated its status as "the call a real pipeline would use" — reworded to
make clear its tag-over-geometry precedence is an audit/reporting
convenience only, not an approved modeling-pipeline policy (the actual
policy is part of the still-unwritten Phase 3B design). Full detail:
`docs/collaboration/active_task.md` round 48.

## 2026-08-12 — Preflight audit v4 (`04_image_baseline_preflight.ipynb`)

**Why this round exists:** round 49 found the round-48 ordering fix only
partial — `InstanceNumber` became the first fallback, but a series with
missing/invalid/duplicate values still silently fell through to filename
order while the helper claimed "anatomical order." Round 50 (user-approved)
froze the actual production contract this needed: series ranking within a
plane, a strict geometry-or-`InstanceNumber` validity gate that marks a
series **unusable** rather than falling back to filename order, same-plane
retry across ranked candidates, and the already-approved missing-plane
fallback only once every candidate is exhausted. This round implements that
contract and measures it directly against real data, rather than asserting
it should work.

**Kernel:** `tuannm3812/rsna-knee-image-baseline-preflight-audit`, version
6, pushed with `scripts/push_kaggle_kernel.sh image-baseline-preflight
NvidiaTeslaT4`. **Code:** `rsna-knee-mri-src` dataset version **10**,
published from commit `4bbd2fb`. **Data:** identical sampling to v1-v3
(seed 42, 150 studies, 822 series) for the series-level ordering-validation
measurement; the same 150 studies × 3 candidate planes (450 study-plane
pairs) for the new ranking/retry measurement.

### New — the strict ordering-validation gate passes on every sampled series

`validate_and_order_series` (geometry route: finite/parseable positions and
orientations, non-degenerate and mutually consistent normals, pairwise-
distinguishable positions; `InstanceNumber` route as fallback only if every
value is parseable and unique; otherwise unusable) was run for real on all
822 sampled series: **usable 1.0 (100%)**, **method geometry 1.0 (100%)**,
**method `instance_number` 0.0**, **unusable 0.0**. Every single sampled
series validated via geometry alone — the `InstanceNumber` fallback route
was never actually needed in this sample, and nothing was rejected as
unusable. **Design implication**: the strict validity gate isn't overly
conservative in a way that would reject usable real data — a legitimate
risk worth checking before adopting a stricter contract, now checked.

### New — series ranking, validation, and retry: the top candidate always won

For all 450 study-plane pairs (150 studies × Sagittal/Coronal/Axial),
`select_validated_series` (rank by fluid-sensitive preference, then slice
count, then `SeriesInstanceUID`; validate each ranked candidate in order;
stop at the first usable one) was run for real: **resolved 1.0 (100%) for
every plane individually and combined**, **retry needed (of resolved) 0.0**,
**method geometry (of resolved) 1.0**. In this sample, the *top-ranked*
candidate for every single plane in every single study validated
immediately — same-plane retry was never actually exercised, and the
missing-plane fallback was never actually triggered. **Design implication**:
this is a real, measured confirmation that the round-50 contract's
robustness mechanisms (retry, missing-plane fallback) are cheap safety nets
for a small-sample or hidden-test edge case, not something the design leans
on for the bulk of studies — reassuring for correctness, though a 150-study
sample doesn't rule out the mechanisms mattering more on the full ~4,407-
study train set or the hidden ~1,300-study test set the design will
actually run against.

Note this measures a different thing from the existing "study laterality
agreement" numbers (unchanged from v3: 98.7% of studies have a resolved
laterality call among their first-per-plane series) — laterality resolution
depends on the 20mm geometric dead-zone and tag validity, independent of
whether a series passes the *ordering* validity gate; a series can be
perfectly usable for slice ordering while still landing in that dead-zone
for laterality. The two are not in tension.

### GPU timing: reconfirmed, materially unchanged

Decode 0.0169s/slice, GPU forward 0.0140s/slice (both close to prior runs —
normal hardware variance). Lower-bound hours: one series per study 0.0583,
three series per study 0.1749 (≈10.5 minutes) — still roughly 51× headroom
against the 9-hour budget for the three-series design.

### Disposition

`uv run pytest -q` → `206 passed` (`test_series_audit.py`: 36 → 39, the old
`anatomically_ordered_paths` suite rewritten, not purely added to;
`test_dataset.py`: 13 → 28; 18 new tests total, covering the strict
validation gate and the ranking/retry contract); `uv run ruff check .` →
clean; kernel version 6 completed (`KernelWorkerStatus.COMPLETE`) on the
first attempt with an explicitly-requested T4. Returned for the user's and
Codex's review. This closes round 49's finding 1 with real measurements,
not just corrected code — the next step is drafting the formal Phase 3B
design spec covering crop dimensions, intensity transform, geometry-aware
laterality reflection, exact DINOv2 token embedding, classifier
regularization, evaluation/refit protocol, codec delivery, notebook
structure, and release gates (round 47's remaining list).
