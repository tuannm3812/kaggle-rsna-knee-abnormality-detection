# Image Baseline Insights

Append-only log of real measurements informing the Phase 3B image-baseline
pipeline design (see `docs/3_strategy.md` Phase 3, `docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md`
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
`docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md` round 39. Every result above comes from
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
`docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md` round 40). All five are fixed in
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
`docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md` round 42; user approval to implement
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
`docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md` round 48.

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

## 2026-08-12 — Preflight audit v5 (`04_image_baseline_preflight.ipynb`)

**Why this round exists:** Codex's round-52 review of v4 reproduced three
real bugs the "100% usable" v4 result had never actually exercised: an
unreadable/malformed `.dcm` file could crash `select_validated_series`
instead of triggering retry; `audit_series` could itself crash on a
degenerate-but-present orientation or a missing `InstanceNumber` (meaning
the true "unusable" rate on real data was genuinely unknown — a crash, not
a graceful "unusable" count, is what a pathological series would have
produced); and the geometry validity check compared only derived slice
normals, which a 90-degree in-plane rotation between slices leaves
unchanged, accepting a case the approved contract should reject. Round 53
independently reproduced all three with the actual project code, fixed
them, and added regression tests (`docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md`
round 53). This round reruns the corrected code against real data — per
the user's explicit workflow change ("test with kaggle running to find any
issue earlier") — before another review round, not after.

**Kernel:** `tuannm3812/rsna-knee-image-baseline-preflight-audit`, version
7, pushed with `scripts/push_kaggle_kernel.sh image-baseline-preflight
NvidiaTeslaT4`. **Code:** `rsna-knee-mri-src` dataset version **11**,
published from commit `3fa0055`. **Data:** identical sampling to v1-v4.

### The stricter validation gate still passes 100% of the real sample

Despite Finding 3's fix meaningfully tightening the geometry route (full
row-and-column orientation consistency, unit-norm, and orthogonality
checks, not just derived-normal agreement), the real-data result is
unchanged from v4: **usable 1.0 (100%), method geometry 1.0, method
`instance_number` 0.0, unusable 0.0** across all 822 sampled series; **all
450 study-plane pairs still resolve with zero retries needed**, unchanged
across every individual plane and combined. **This is a meaningful
confirmation, not a null result**: it shows the tightened check isn't
overly conservative for this dataset's real, legitimately-acquired DICOM
series — genuine acquisitions have internally consistent orientation, so
requiring that consistency doesn't reject real usable data. The three
fixed crash paths (unreadable header, degenerate orientation, missing
`InstanceNumber`) were still not exercised by this sample, same caveat as
before: this proves the fixes don't regress the happy path, not that the
failure paths themselves have been exercised for real. That would need
either a much larger/different sample or a deliberately adversarial one.

### GPU timing: reconfirmed again, materially unchanged

Decode 0.0202s/slice, GPU forward 0.0141s/slice. Lower-bound hours: one
series per study 0.0647, three series per study 0.1942 (≈11.7 minutes) —
still roughly 46× headroom against the 9-hour budget.

### Disposition

`uv run pytest -q` → `218 passed`; `uv run ruff check .` → clean; kernel
version 7 completed (`KernelWorkerStatus.COMPLETE`) on the first attempt.
Returned for Codex's review. The series ranking/validation/retry contract
is now implemented, tested against reproduced adversarial cases locally,
and confirmed not to regress real-data pass rates — the next step remains
drafting the formal Phase 3B design spec (round 47's remaining list).

## 2026-08-13 — Preflight audit v6 (`04_image_baseline_preflight.ipynb`)

**Why this round exists:** Codex's round-55 review of v5 found two residual
validation-contract gaps `audit_series` itself still had its own unguarded
header-read step that crashed on an unreadable `.dcm` file rather than
counting it (round 52's finding 2 was only partially closed for the
selector, not the audit), and the geometry orientation check compared raw,
non-normalized direction-cosine dot products against a cosine-similarity
threshold, producing an asymmetric false rejection within the accepted
unit-norm tolerance — plus a non-blocking gap where tolerance validation
still accepted infinite/degenerate values. Round 56 independently reproduced
and fixed all three (`docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md` round 56) and wired
a new aggregate-only `header_read_failures` stat into this notebook's
persisted summary. Per Codex's own round-55 guidance, this rerun is not
claimed to exercise the fixed failure paths themselves — the fixed 150-study
sample still contains none of their adverse inputs — its purpose is
narrower: confirm the new aggregate reports correctly on well-formed real
data, and confirm nothing else regressed.

**Kernel:** `tuannm3812/rsna-knee-image-baseline-preflight-audit`, version
8, pushed with `scripts/push_kaggle_kernel.sh image-baseline-preflight
NvidiaTeslaT4`. **Code:** `rsna-knee-mri-src` dataset, published from commit
`aee97d7`. **Data:** identical sampling to v1-v5.

### The new header-read-failure aggregate correctly reports zero on real data

`Series with >=1 unreadable header` and `Header read failure rate (of
slices)` are both `0.0` across all 822 sampled series, as expected — this
sample's real DICOM files are all well-formed, so the new code path that
counts and gracefully handles an unreadable header was not itself exercised
by this run, only confirmed not to fire false positives against valid data.
Confirming the failure path actually works still rests on round 56's local
regression tests (a mixed and a wholly-unreadable synthetic series), not on
this real-data rerun.

### Everything else is unchanged from v5

**Usable 1.0 (100%), method geometry 1.0, unusable 0.0** across all 822
sampled series — identical to v5 despite the orientation check now
normalizing vectors before the cosine-similarity comparison (Finding 2's
fix), confirming the earlier raw-dot-product bug happened not to flip any
real series' outcome in this sample even though it was a genuine asymmetry.
**All 450 study-plane pairs still resolve with zero retries needed**,
unchanged across every individual plane and combined.

### GPU timing: reconfirmed again, materially unchanged

Decode 0.0167s/slice, GPU forward 0.0147s/slice. Lower-bound hours: one
series per study 0.0593, three series per study 0.1778 (≈10.7 minutes) —
still roughly 51× headroom against the 9-hour budget.

### Disposition

`uv run pytest -q` → `228 passed`; `uv run ruff check .` → clean; kernel
version 8 completed (`KernelWorkerStatus.COMPLETE`); the downloaded log
contains only debugger/nbconvert warnings, no errors. Returned for Codex's
review. The series ranking/validation/retry/audit contract's three
round-55 gaps are now closed and confirmed not to regress real-data pass
rates; the next step remains drafting the formal Phase 3B design spec
(round 47's remaining list).

## 2026-08-13 — Preflight audit v7: signed patient-X orientation (`04_image_baseline_preflight.ipynb`)

**Why this round exists:** a proposed right-knee horizontal flip was not a
patient-coordinate transform: DICOM patient left/right can align with image
columns, rows, or the slice stack, and the direction-cosine sign determines
whether reversal is needed. This targeted rerun measures those geometry facts
before freezing a laterality-normalization threshold. It reuses the identical
seeded 150-study sample and reports aggregate tables only.

**Kernel:** `tuannm3812/rsna-knee-image-baseline-preflight-audit`, version 9,
private/offline/T4, completed successfully. **Code:** private
`rsna-knee-mri-src` dataset refreshed from commit `8cdfae8`. **Local gate:**
233 tests and Ruff passed before publication.

### Patient-X alignment is strong in all 822 geometry-valid sampled series

| Plane | Series | Minimum dominant \|X\| | 5th percentile | Median | Minimum dominance gap | Below 0.80 | Below 0.85 | Below 0.90 | Below 0.95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Axial | 201 | 0.8603 | 0.9657 | 0.9954 | 0.3518 | 0 | 0 | 1 | 3 |
| Coronal | 292 | 0.8098 | 0.9598 | 0.9941 | 0.2280 | 0 | 3 | 4 | 8 |
| Sagittal | 329 | 0.8692 | 0.9407 | 0.9916 | 0.3775 | 0 | 0 | 8 | 23 |
| All | 822 | 0.8098 | 0.9547 | 0.9937 | 0.2280 | 0 | 3 | 13 | 34 |

Every sampled series has a unique dominant axis and exceeds `0.80`; the
smallest dominant component still exceeds its runner-up by 0.228. A `0.80`
gate therefore retains all measured series while remaining an explicit
fallback boundary for unseen oblique acquisitions. The sample is descriptive,
not proof that all 4,407 studies satisfy the same distribution.

### Axis and sign are plane-dependent

- All 201 axial and 292 coronal series place patient X on increasing image
  columns; all 493 signed components are positive.
- All 329 sagittal series place patient X on the geometry-ordered slice stack;
  all 322 series with a conservative side call have a negative signed
  component. Seven sagittal, six coronal, and four axial series are excluded
  from the side cross-tab by the conservative conflict/unresolved rule.
- No sampled series places patient X on image rows.

This directly supports signed canonicalization rather than “flip every right
knee”: with the proposed medial-toward-decreasing-index convention,
axial/coronal right knees reverse columns while left knees do not; sagittal
left knees reverse slice order while right knees do not. The sagittal reversal
does not change the current symmetric-sample/mean feature, but specifying it
keeps the transform geometrically correct.

### Unrelated preflight measurements remain stable

All 822 series remain geometry-usable with zero decode/header failures, and all
450 study-plane selections resolve without retry. The GPU timing lower bound is
0.2101 hours for the three-series workload; as before, this is not an
end-to-end runtime guarantee.

### Disposition

Recommend freezing a **strictly greater than 0.80** unique-dominant-axis gate,
with below-threshold/tied orientations left untransformed and marked
unreliable. This recommendation still requires Claude and user approval; the
audit itself applies no reflection and authorizes no model implementation or
submission.

> **Superseded by v8 on the threshold value:** Claude's round-68 review and
> Codex's round-69 response converged on **`> 0.90`** instead, and the user
> approved that value in round 70. The measurements in this section are
> unchanged and remain the evidence base; only the recommended gate moved.

## 2026-08-26 — Preflight audit v8: corpus-wide transfer-syntax census (`04_image_baseline_preflight.ipynb`)

**Why this round exists:** round 60 finding 8 required deterministic codec
evidence before the offline-vendoring section could close. Every prior audit
sampled the same seeded 150 studies and saw only uncompressed data, which
says nothing about the other ~97% of the corpus; "sample studies more likely
to be compressed" was explicitly rejected as irreproducible. This round
censuses **storage format across every series in both splits** by reading one
representative slice header per series.

**Kernel:** `tuannm3812/rsna-knee-image-baseline-preflight-audit`, version
10, T4. **Code:** `rsna-knee-mri-src` refreshed from commit `141b327`.

### The corpus is entirely uncompressed

| Transfer syntax | Name | Compressed | Train | Test | Series |
|---|---|---|---:|---:|---:|
| `1.2.840.10008.1.2.1` | Explicit VR Little Endian | No | 24,371 | 15 | **24,386** |

That is the complete table — **one** distinct transfer syntax across the
entire corpus. Coverage was total: 24,386 series censused, **0** with an
unreadable header, **0** with no `.dcm` file, **0** compressed syntaxes
observed. The censused count exactly equals `train_series.csv` (24,371) plus
`test_series.csv` (15), so no study directory was silently missing from disk
and no series was skipped — a clean CSV-to-disk cross-check obtained for
free.

### This contradicts the stated data description

`docs/1_instructions.md` records the competition's own description of the
data as "Mixed transfer syntaxes: uncompressed Explicit VR Little Endian,
JPEG Lossless, JPEG 2000, Implicit VR Little Endian." The census finds
**none** of the three non-uncompressed syntaxes anywhere in the visible
corpus. v2's design note — that this sample "says nothing about whether
compressed-syntax slices (which the competition description says exist)
would decode successfully here" — is now answered for the visible data: no
such slices exist in it. The description is either inaccurate for the
released files, or it describes a broader collection of which only part was
released.

### What this does and does not establish

Establishes: every one of the 24,386 visible series stores its representative
slice uncompressed, and the pipeline needs no codec to read any data this
project can currently see.

Does **not** establish, and must not be read as: (a) that *every slice* is
uncompressed — the census reads one representative header per series, so a
series mixing syntaxes across slices would be recorded by its first readable
slice only; (b) anything about the **~1,300-study hidden test set**, which is
never mounted and cannot be censused. The 15 visible test series are not
that set.

**Design implication.** The second half of round 60 finding 8 — "decode a
fixed, recorded sample for every observed compressed transfer-syntax UID" —
is now **vacuous on evidence**: there are no observed compressed UIDs to
sample, so that sub-requirement should close as not-applicable rather than be
carried as open work. Offline codec vendoring itself should **not** be
retired on this evidence. The cost asymmetry runs the same way it did for the
laterality gate: vendoring costs a few megabytes and a checksum-verified
offline install, while omitting it and being wrong means every compressed
slice in an unobservable hidden test set silently fails to decode and falls
through to the last-resort prevalence row, on data that cannot be inspected
or debugged after scoring. The notebook's own `codec_availability` check
continues to report `pylibjpeg`, `libjpeg`, `openjpeg`, and `gdcm` all
unimportable in this environment, so that failure mode is live, not
hypothetical.

### Unchanged checks

The 150-study sampled audit is unchanged: 822/822 series geometry-usable
with zero header-read and zero decode failures, 450/450 study-plane
selections resolving without retry, and the sampled decode audit again
attributing all 4,110 attempted decodes to `1.2.840.10008.1.2.1` with zero
failures. The kernel log contains no traceback or error marker.

### New — decode time is I/O-contention-sensitive; GPU time is not

The timing probe did **not** reproduce its prior value, and the way it moved
is informative. Across v3-v6 the three-series lower bound held a tight band
of `0.1722`, `0.1749`, `0.1942`, `0.1778` hours. This run reports
**`0.3373` hours** — 1.74x the top of that band, cutting headroom against
the 9-hour budget from roughly 50x to **~27x**.

The component split identifies the cause rather than leaving it as variance:

| Component | v6 | v8 | Change |
|---|---:|---:|---|
| GPU forward per slice | `0.0147 s` | `0.0147 s` | none |
| Decode per slice | `0.0167 s` | `0.0449 s` | **~2.7x** |

GPU cost is identical; **decode alone nearly tripled**. The one material
difference in this kernel is the census's 24,386 header reads competing for
the same shared competition-data storage. **Design implication:** the
encoder-only lower bound measured on an otherwise-idle kernel *understates*
a real pipeline run, which performs sustained feature-extraction I/O
throughout. This is direct measured support for the release gate requiring a
complete decode-preprocess-encoder-head timing sample under representative
load, rather than extrapolating from the idle-kernel bound. The ~27x margin
remains comfortable, but the number that matters has not been measured yet.

## 2026-08-26 — Correction (no rerun): `fraction monotonic` could not distinguish tied `InstanceNumber`

Applies to every prior section that cites `Order agreement -- fraction
monotonic (|r| > 0.99)`, and specifically to v3's sentence above: *"`fraction
monotonic (|r| > 0.99)` remains **1.0** — every individual series is still
perfectly internally ordered, in some direction."*

**That inference does not follow from the statistic as it was computed.** An
independent code review found that `order_agreement` ranked ties with a
double `argsort`, which produces *ordinal* ranks rather than the midranks
Spearman is defined on. Because ordinal ranks always form a permutation of
`0..n-1`, a series whose `InstanceNumber` is **entirely constant** — carrying
no ordering information whatsoever — scored a perfect `±1.0`, and a
partially-tied series scored differently depending only on the arbitrary
filename order of its tied slices. Reproduced: `[1,1,2]` against `[0,1,2]`
scored `1.0` while the same values against `[1,0,2]` scored `0.5`; true
Spearman is `0.866` for both.

So a reported `1.0` meant "either perfectly ordered, **or** `InstanceNumber`
is degenerate and tells us nothing" — and those two cases are exactly what
the cited sentence claimed to have distinguished.

**Fixed** in commit `d04f23e`: midranks, and `None` when either input is
constant, verified against `scipy.stats.spearmanr`. Untied results are
unchanged, so every series with distinct `InstanceNumber` values scores
exactly as before.

**How much of the recorded evidence actually moves is not yet known, and is
deliberately not guessed at here.** The measured runs never exercised the
`InstanceNumber` route — all 822 sampled series validated by geometry — so
those runs never tested `InstanceNumber` uniqueness, and the corpus's real
rate of tied `InstanceNumber` is unmeasured. The true `fraction monotonic`
is `1.0` **only if** no sampled series has tied values. This does not
warrant a Kaggle run of its own: the next authorized run already reports the
statistic, and it will now report it correctly. Until then, treat
`fraction monotonic` in v1-v8 as an upper bound.

**What does not change:** the practical conclusion those sections drew.
Ordering for the frozen design comes from `validate_and_order_series`, which
independently requires unique, parseable `InstanceNumber` values before it
will use that route at all, and which chose geometry for 822/822 sampled
series regardless. `order_agreement` is a diagnostic, never the production
ordering path.

## 2026-08-27 — Image baseline v1, first end-to-end run (`05_image_baseline.ipynb`)

**What this is.** The first execution of the actual Phase 3B pipeline rather
than an audit of its inputs: series selection, ordering validation, decode,
intensity normalization, letterbox framing, signed laterality
canonicalization, frozen DINOv2-small encoding, shared-mean aggregation, and
the regularized multilabel head, evaluated out-of-fold on all 58 human-
labeled studies.

**Kernel:** `tuannm3812/rsna-knee-frozen-image-baseline`, version 1, T4,
`KernelWorkerStatus.COMPLETE`, zero traceback or error markers in the log.

### Result

| Measure | Value |
|---|---|
| **Pooled OOF macro AUC** | **0.6346** |
| Fold macro AUC (mean / min / max) | 0.6246 / 0.5573 / 0.6922 |
| Constant-prediction sanity check | 0.5000 (exact) |
| Selected fold count | 5 |

**Read this narrowly.** `0.6346` is above chance on 58 studies across 12
labels, which is genuine signal rather than noise around 0.5. It is **not**
evidence that the pipeline is good: the fold spread of `0.557` to `0.692` is
wide, exactly as expected when each fold validates roughly a dozen studies,
and no confidence interval was computed. There is also **no report-baseline
number to compare against** — Phase 3A's kernel errored during input
preparation, before it ever reached cross-validation, so a comparison that
was a design goal simply has no counterpart yet.

### Two predictions confirmed by measurement

Both were stated in advance and are now observed rather than assumed:

- **Laterality-unreliable studies: 3 of 58.** Round 88 predicted "roughly
  2.7 to 2.8 of 58" from the audited orientation distribution and the frozen
  `0.90` gate. Measured exactly 3.
- **The presence flags are constant.** Flags 0-2 (Sagittal, Coronal, Axial
  presence) have variance **exactly `0.0`**, and the laterality flag has
  variance `0.0499`, which is `p(1-p)` for `3/58` to four decimals. The
  "near-degenerate flags" claim from rounds 70 and 88 is now measured. The
  388-dimensional vector is, in practice, 384 informative dimensions plus one
  barely-varying flag and three inert ones.

### The complete-path timing overturns the encoder-only estimate

| Estimate | Projected hours for ~1,300 studies | Headroom vs 9 h |
|---|---:|---:|
| Encoder-only lower bound (audit v8) | 0.337 | 26.7x |
| **Measured complete path (this run)** | **1.144** | **7.9x** |

The real pipeline costs **3.4x** the encoder-only bound. This is precisely
why release gate 5 demanded a complete decode-preprocess-encoder-head
measurement instead of extrapolating from the encoder probe, and it retires
the comfortable ~27x figure that bound implied. 7.9x is still ample margin,
but it is a different order of comfort, and the projection is a linear
extrapolation from **three** visible test studies, so it carries real
uncertainty. Decode cost was separately measured to be I/O-contention-
sensitive (audit v8: decode nearly tripled under concurrent load), so a busy
kernel would be slower than this idle-kernel figure.

### Every fallback path stayed unexercised, again

Planes absent `0`; plane retries triggered `0`; header-read failures `0`;
decoded slices per plane mean and minimum both `5.0`; planes with fewer than
five decoded `0`; **studies with no usable plane `0`** (the release-gate
condition). A mean of `1.93` validated candidates per plane means retry had
alternatives available and simply never needed them.

So the retry, minimum-of-three, and missing-plane fallbacks remain implemented
and tested but **never exercised on real data** — the same standing caveat as
every prior round. They exist for the ~1,300-study hidden set, which cannot be
inspected.

### Task 1's `PixelSpacing` precondition changed nothing observable here

Round 86 flagged that enforcing it might reduce the usable-series count, since
the preflight had only ever measured tag *presence*. On these 58 studies no
plane was lost. That does not clear the 4,407-study corpus, which was never
re-audited under the new precondition.

## 2026-08-27 — Image baseline v2: representative timing (`05_image_baseline.ipynb`)

**Why this round exists.** v1's runtime projection extrapolated from the
**three** visible test studies, which is not a representative sample of
anything. Per-study cost scales with how many DICOM files a study holds,
because ordering validation reads every header of every candidate series, not
only the five slices ultimately decoded. This round times **83** studies — the
58 labeled ones, instrumented at no extra cost, plus 25 drawn from five
strata spanning the whole training corpus.

**Kernel:** version 2, T4, `COMPLETE`, zero error markers.

### The small sample was pessimistic, not optimistic

| Sample | Seconds/study | Projected hours (~1,300) |
|---|---:|---:|
| v1 — 3 visible test studies | 3.167 | 1.144 |
| **v2 — 83 stratified studies** | **2.120** | **0.765** |

The three visible test studies were **49% slower per study** than the
stratified population. That direction is worth noting: a tiny sample is
usually assumed to flatter a result, and here it did the opposite. Either
direction would have been wrong to rely on — which is the point of measuring
rather than extrapolating.

### With the safety margin

| Basis | Hours | Headroom vs 9 h |
|---|---:|---:|
| Mean rate | 0.765 | 11.8x |
| Slowest stratum | 1.266 | 7.1x |
| **Mean rate x3 safety margin** | **2.296** | **3.9x** |

The margin covers the separately measured I/O contention effect, where decode
nearly tripled under concurrent load. Even the deliberately pessimistic
reading — slowest stratum, no margin — leaves 7x. Runtime is not a constraint
on this design.

The stratified sample spans a median of **166** DICOM files per study and a
maximum of **572**, so the range the hidden set will contain is represented
rather than assumed. The slowest stratum runs **65%** above the mean, which
confirms cost is slice-count-driven rather than fixed per study.

### The pipeline is deterministic across runs

v1 and v2 produced a **bit-identical** pooled OOF macro AUC of
`0.6345688959` from independent kernel executions. Same folds, same seed, same
frozen contract, same result. That is a real property worth having measured:
it means a future score change is attributable to a deliberate change rather
than to run-to-run drift.

Wall-clock extraction over the same 58 studies varied by `1.31x` between the
two runs (166.6 s versus 127.1 s) while producing identical numbers — I/O
timing is noisy, the computation is not.

### Everything else unchanged

Planes absent `0`; retries `0`; header-read failures `0`; decoded slices per
plane `5.0` mean and minimum; **studies with no usable plane `0`**. Studies
with unreliable laterality `3`, again matching the prediction. The retry,
minimum-of-three, and missing-plane fallbacks remain implemented, tested, and
never exercised on real data.

## 2026-08-27 — Image baseline v3: codecs installed, stratum profile visible

**Kernel:** version 3, T4, `COMPLETE`, zero error markers.

### The vendored codecs load on Kaggle

`Codec plugins importable: ['libjpeg', 'openjpeg', 'pylibjpeg']` — all three
`cp312` wheels installed from the private dataset with `--no-index --no-deps`
and imported successfully. This is the check a checksum cannot make: the
checksum proves the right bytes arrived, the import proves the compiled
extension actually loads on that interpreter. Had the wheels been built for
3.11, as the first download attempt produced, they would have installed
cleanly and failed here.

`Encoder trainable parameters: 0`, again.

### Cost is slice-count driven, and now visibly so

| Stratum | Median DICOM files | Mean seconds/study |
|---|---:|---:|
| 0 | 110 | 2.00 |
| 1 | 130 | 2.41 |
| 2 | 166 | 3.01 |
| 3 | 190 | 3.22 |
| 4 | 273 | **5.46** |

Monotonic across all five bands, with the largest stratum **2.7x** the
smallest. This settles what the single mean could not: per-study cost tracks
how many DICOM files a study holds, because ordering validation reads every
header of every candidate series. A hidden set skewed toward large studies
would cost proportionally more, which is exactly why the projection carries a
margin rather than a point estimate.

### Run-to-run variance is large, which vindicates the margin

The same extraction path measured **2.12 s/study in v2 and 3.23 s/study in
v3** — a `1.52x` swing between consecutive runs. Earlier, v1 and v2 differed
by `1.31x` on wall clock over identical studies.

**Two explanations are consistent with this and one run cannot separate
them:** shared-storage I/O contention, which was independently measured to
nearly triple decode cost under load; or the newly installed codec plugins
adding handler-selection overhead to every decode, even though this corpus is
entirely uncompressed and no plugin should engage. Recorded as unresolved
rather than attributed to the convenient explanation. If it matters later, the
way to separate them is a run with the wheels vendored but not installed.

Either way the practical conclusion holds, and it is the reason the safety
margin was set at 3x rather than something tighter:

| Basis (v3, the slowest run so far) | Hours | Headroom vs 9 h |
|---|---:|---:|
| Mean rate x3 margin | 3.50 | 2.6x |
| Slowest stratum, no margin | 1.97 | 4.6x |

### Determinism holds across three independent runs

Pooled OOF macro AUC is `0.6345688959` in v1, v2 **and** v3 — bit-identical,
while per-study timing swung by half again. The computation is reproducible;
only the clock is noisy. A future score change is therefore attributable to a
deliberate change rather than to drift.

## 2026-08-28 — Image baseline v4: how much to believe 0.6346

**Kernel:** version 4, T4, `COMPLETE`, zero error markers.

Two diagnostics, answering two different questions the point estimate cannot.

### The interval excludes chance, but the estimate is thin

| | Value |
|---|---|
| Pooled OOF macro AUC (frozen seed) | **0.6346** |
| Bootstrap 95% interval (2,000 resamples) | **[0.5704, 0.6973]** |
| Interval width | 0.127 |

The lower bound sits **above 0.5**, so the signal is distinguishable from
chance rather than a plausible-looking accident. It is also `±0.063` wide,
which is the honest cost of 58 studies: the direction is established, the
magnitude is not. A second baseline scoring 0.68 could not be called better
than this one on this evidence.

The concern flagged in advance — that resampling would leave a rare label with
no positives and quietly redefine the macro — **did not materialize**. All
twelve labels were estimable in **100%** of resamples, because the rarest has
9 positives out of 58 and losing all of them is very unlikely. Worth recording
that the guard was unnecessary here rather than quietly dropping the caveat.

### Fold assignment is not the problem; sample size is

| Source of variance | Magnitude |
|---|---|
| Fold assignment (10 seeds) | std **0.0157** |
| Study sampling (bootstrap) | half-width **0.0634** |

Study-sampling uncertainty is **4x** larger than fold-assignment uncertainty.
That has a direct practical consequence: more folds, more repeats, or a
better split will not meaningfully tighten this number. **More labeled
studies would.** Effort spent on the evaluation protocol is effort misplaced.

The frozen seed also turns out not to be a lucky draw — `0.6346` against a
ten-seed mean of `0.6301`, `z = 0.28`. The reported score is an ordinary
member of its own distribution, which is what one wants and not what one is
entitled to assume.

### The macro hides a strongly uneven picture

| Label | Pooled AUC | Positives |
|---|---:|---:|
| Effusion | **0.811** | 35 |
| ACL | **0.786** | 24 |
| Lateral Meniscus | **0.755** | 23 |
| Medial OA | **0.752** | 15 |
| Lateral OA | 0.652 | 11 |
| Contusion | 0.609 | 19 |
| Baker's | 0.585 | 12 |
| Medial Meniscus | 0.570 | 26 |
| Synovitis | 0.570 | 27 |
| PF OA | 0.551 | 21 |
| MCL | 0.519 | 9 |
| Fracture | **0.456** | 18 |

This is the most useful result of the run. The baseline is **not** uniformly
mediocre at 0.63 — it is genuinely informative for four findings and at or
near chance for five. Effusion at `0.811` from a frozen encoder that never saw
a knee is a real result; `MCL` at `0.519` and `PF OA` at `0.551` are not.

`Fracture` at `0.456` is below chance. That is **not** evidence of a wiring
error — the constant-prediction check returns exactly `0.5`, and with 18
positives and no per-label interval, `0.456` is comfortably within noise of
chance. It would only become interesting if it persisted with a tighter
interval.

**Design implication.** A single shared 384-dimension embedding, mean-pooled
across planes, carries effusion and cruciate-ligament signal but evidently not
fine cartilage or patellofemoral detail. That is the expected weakness of
mean-pooling five central-band slices at 336 pixels, and it points at where a
future design would have to change — plane-specific features or higher
resolution — rather than at more regularization tuning.

## 2026-08-28 — Image baseline v5: the deferred aggregation variants, resolved as unresolved

**Kernel:** version 5, T4, `COMPLETE`, zero error markers. Both variants
registered in advance, built from the same per-plane embeddings as the
incumbent, evaluated on the same studies under the same folds.

| Variant | Macro AUC | Paired delta vs V0 | 95% interval | Resolved |
|---|---:|---:|---|---|
| **V0** shared mean (incumbent) | 0.6346 | — | — | — |
| V1 plane concatenation | 0.6301 | −0.0044 | [−0.0352, +0.0276] | **No** |
| V2 per-plane heads | **0.6635** | **+0.0290** | [−0.0061, +0.0648] | **No** |

**By the rule registered before the run, V0 stands.** Neither interval
excludes zero, so neither variant has displaced the incumbent.

### V2 is the interesting result, and it must not be over-read

V2 scores `+0.029` higher, and its interval misses excluding zero by
`0.0061`. That is genuinely suggestive — most of the interval is positive —
and it is **not** a win. The decision rule was fixed in advance precisely so
that a near-miss could not be relabelled a success after the fact; lowering
the confidence level now, or calling this "nearly significant", would be the
exact bias the pre-registration existed to prevent.

Nor is `0.6635` an unbiased estimate of V2's performance. It was read off the
same out-of-fold predictions used to compare it, so it carries selection
optimism. **The project's reported score remains V0's `0.6346`.**

The honest statement is: *per-plane heads are a promising lead that 58 studies
cannot confirm.* If more labelled data ever appears, this is the first thing
to re-test.

### Two things that revise earlier reasoning

**Round 46's capacity worry was half right.** It rejected both variants for
tripling either the feature width or the head count on 58 studies. V1 does
triple the width (1156 features) and did **not** blow up — it landed within
noise of the incumbent, slightly below. So the concatenation was not
catastrophic, it was simply useless: preserving plane identity in the feature
vector buys nothing here. V2, the variant that tripled the head count, is the
one that looks most promising. The concern was reasonable and the direction it
predicted was wrong.

**A prediction of mine was also wrong, in the same direction.** Ahead of the
run I expected both variants to lose. V1 did. V2 did not lose on point
estimate — it gained. What I got right was that neither would resolve at this
sample size.

### The paired comparison earned its place

Marginal intervals are `0.127` wide; the paired deltas are `0.063` and `0.071`
— **1.8x to 2.0x tighter**. Less than the ~3x simulated at high correlation,
which makes sense: V2 is a structurally different model and correlates less
with V0 than two near-identical variants would. Even so, comparing marginal
intervals would have made both comparisons hopeless, where the paired test at
least brought V2 within a hair of resolution.

## 2026-08-28 — Image baseline v8: patch pooling, and a bug that changed two settled numbers

**Kernel:** version 8, Tesla T4 (capability 7.5), `COMPLETE`. Three variants
now share one comparison family, so every interval is Bonferroni-adjusted to
98.33% — including the two reported at v5, so no earlier conclusion is quietly
improved by the correction.

| Variant | Macro AUC | Paired delta vs V0 | 98.33% interval | Resolved |
|---|---:|---:|---|---|
| **V0** shared mean (incumbent) | 0.6346 | — | — | — |
| V1 plane concatenation | 0.6301 | −0.0044 | [−0.0419, +0.0338] | **No** |
| V2 per-plane heads | **0.6635** | **+0.0290** | [−0.0115, +0.0716] | **No** |
| V3 patch-token pooling | 0.6074 | −0.0271 | [−0.0704, +0.0103] | **No** |

**V0 stands.** No interval excludes zero in a variant's favour.

### The patch-pooling hypothesis was wrong, in the direction it was stated

The prediction on record was that patch pooling *should* move: the per-label
result shows the baseline carrying effusion (0.811) and ACL (0.786) but sitting
near chance for MCL (0.519), PF OA (0.551) and fracture (0.456) — small,
localized structures a single global CLS summary would wash out. Mean-pooled
patch tokens retain more spatial evidence, so they should have helped.

They scored **−0.0271**, the largest negative delta of the three.

The interval does not resolve it, so the defensible claim is "no evidence patch
pooling helps, and what evidence exists points the other way" — not "patch
pooling is worse". But the mechanism argued for it was wrong, and it should not
be reused without new support. A plausible reading is that averaging 576 patch
tokens is itself a global summary, and a noisier one than CLS, which was at
least trained to be a summary. Localization would need pooling that is
*selective*, not merely spatial.

### A bug of mine silently changed two numbers that were already settled

Widening the encoder to emit CLS and patch-mean from one forward pass — done so
V0 and V3 could not differ by accident of extraction — redefined the two
variants it was supposed to leave alone. V1 concatenated 768-wide embeddings
(2304 features, not the registered 1152) with its scaler still sized for 1152,
leaving over half the block unstandardized. V2 fitted heads on 768-wide
matrices while scaling only the first 384.

Nothing crashed. V1 read 0.6261 instead of 0.6301, V2 0.6556 instead of 0.6635
— both plausible, both wrong, and both withdrawn.

**What caught it was not a guard.** The V0 reproduction guard passed the whole
time, because V0 was correctly sliced. The bug surfaced only because V1 and V2
*moved* when nothing about them should have, and that signal existed only
because they had been measured once before. Three variants measured together
for the first time would have shipped wrong numbers with nothing to contradict
them. Both now assert their feature width against the registered definition.

The fix is verified rather than asserted: in v8, V1 and V2 returned to exactly
their v5 values (0.6301396031, 0.6635347472) while V3 reproduced its earlier
value bit-identically.

### The accelerator had never been pinned

Version 7 died with `Allocated GPU compute capability unsupported by installed
PyTorch`: Kaggle allocated a Tesla P100 (sm_60) against a PyTorch built for
sm_70 and above. Setting only `enable_gpu` lets Kaggle choose either card, so
every prior run — including the three that established `0.6345688959` as a
reproducibility constant — had been winning a coin flip rather than requesting
its hardware. Both GPU kernels now pin `machine_shape: NvidiaTeslaT4`, asserted
in tests, with the runtime guard kept as the check on the pin itself.

A reproducibility claim that rests on an unpinned accelerator is weaker than it
looks; this one happened to fail loudly, but it could as easily have returned a
number with no explanation attached.

### What the aggregation question has now cost, and why to stop

Three variants, three unresolved comparisons. V2 remains the only point
estimate favouring a change, missing resolution by 0.0115 at the adjusted
level. This matches the variance decomposition already on record: study
sampling contributes about four times the uncertainty of fold assignment, so 58
studies cannot settle differences of this magnitude however the aggregation is
arranged. Further aggregation variants should be expected to return unresolved
and are not worth the runs without a stronger reason than a point estimate.

## 2026-08-28 — Image baseline v9: tripling slice density changes nothing

**Kernel:** version 9, Tesla T4, `COMPLETE`. One comparison, registered in
advance in its own family, so a plain paired 95% interval.

| Variant | Slices/plane | Decoded/plane | Macro AUC | Paired delta | 95% interval | Resolved |
|---|---:|---:|---:|---:|---|---|
| **V0** five slices | 5 | 5.00 | 0.6346 | — | — | — |
| E1 fifteen slices | 15 | 14.40 | 0.6321 | −0.0025 | [−0.0199, +0.0151] | **No** |

Decoded slices per plane rose 5.00 → 14.40, so the density change is real; the
shortfall from 15 is series where the central band collapses duplicate rounded
positions. Study membership, absent planes and feature-matrix shape were all
asserted identical to the baseline, so this compares two densities on one
dataset rather than two datasets.

### This is the most powerful null measured so far

The interval is ±0.017 — about half the width of every aggregation comparison
(±0.035 or wider). Denser sampling yields features strongly correlated with the
baseline's, so the paired bootstrap has more power here than in any earlier
comparison. **It could have detected a smaller effect than anything previously
tested, and still found nothing.**

### Two pre-registered failures now agree: averaging is the bottleneck

- **V3** replaced the CLS token with mean-pooled patch tokens: −0.0271.
- **E1** fed three times as many slices into the same mean: −0.0025.

Both are "average more material" moves. Both failed, and the more powerful of
the two failed most cleanly. The reading supported by both is that the mean is
what destroys focal findings, and adding evidence to a mean that already
washes them out dilutes rather than recovers them.

Stated as a prediction for anyone continuing this: further uniform-pooling
variants — more slices, more planes, wider bands, different token pools — should
be expected to return unresolved. The change that would follow from this
evidence is **selective** pooling, letting the head see which slices matter
instead of committing to a mean before the head is reached. That is a design
change, not a parameter sweep.

### Two consecutive wrong directional predictions

Round 96 predicted patch pooling would help; it was the largest negative delta.
Round 98 predicted denser sampling would give a positive point estimate; it was
negative. Both predicted "unresolved" correctly and both got the sign wrong.

Two consecutive misses from the same underlying model — that the pipeline is
missing *information* — is a signal about the model rather than about luck. The
information is reaching the encoder; the aggregation is discarding it.

### A runtime number from this run is withdrawn

The run reported E1 costing **0.51×** the baseline: three times the slices in
half the time. That is page cache. E1's extraction reads files the baseline's
extraction has just read, so a warm pass was timed against a cold one. The
baseline's own extraction has ranged 118.9s to 178.5s across runs for identical
work, which alone should have been enough to distrust a single-run ratio.

The notebook no longer computes a ratio. It records both times explicitly
flagged non-comparable, so the confound is visible rather than waiting to be
rediscovered. **Any adoption estimate at a new density needs a dedicated cold
run.**

### Scoreboard

Five pre-registered comparisons, five unresolved. V0 stands at 0.6346. The
useful result is not "nothing works" but something sharper: rearranging or
enlarging what gets averaged does not help, and the two experiments that
stressed averaging hardest both came back negative.

## 2026-08-28 — Image baseline v10: the bag-of-slices model earns its keep

**Kernel:** version 10, Tesla T4, `COMPLETE`. Two operators registered in
advance as one family, both compared against the mean **at the same sampling
density**, so the within-plane pooling operator is the only difference.
Bonferroni at α/2, hence 97.5% intervals.

| Variant | Macro AUC | Paired delta vs E1 | 97.5% interval | Resolved |
|---|---:|---:|---|---|
| E1 mean (reference) | 0.6321 | — | — | — |
| **E2 max over slices** | **0.6507** | **+0.0186** | [−0.0082, +0.0492] | **No** |
| E3 mean of top 3 | 0.6431 | +0.0110 | [−0.0117, +0.0340] | **No** |

Both selective operators beat the mean. Neither resolves.

### The per-label signs are the whole result

E2 against E1, sorted:

| Gains | | Losses | |
|---|---:|---|---:|
| Lateral OA | +0.091 | Medial Meniscus | −0.059 |
| Synovitis | +0.076 | Effusion | −0.041 |
| PF OA | +0.066 | ACL | −0.039 |
| Contusion | +0.057 | Baker's | −0.020 |
| Lateral Meniscus | +0.051 | | |
| MCL | +0.020 | | |
| Fracture | +0.018 | | |

**Effusion is the second-largest loser — and effusion is the most diffuse
finding in the panel, at 35 of 58 positives, and the label the baseline scored
highest.** That is precisely what a bag model predicts: where a finding is
genuinely a property of most slices, the mean is the right estimator and
picking the extreme slice throws information away. Where a finding is focal,
the mean dilutes it. The operator improves the focal labels and degrades the
diffuse one.

Three of the four labels that sat near chance under the baseline — PF OA, MCL,
fracture — move up, and the largest single gain is lateral OA at +0.091.

### Why this is evidence and not pattern-hunting

Twelve labels at this noise level will always show some pattern. What lifts
this above post-hoc storytelling is that **the direction was registered before
the run**: the prediction on record said any gain would concentrate in the
focal labels rather than spread across the macro. It did. The breakdown was
also declared diagnostic rather than a decision input, so it cannot be promoted
into one now.

### The noise worry was the wrong worry

Both operators were registered specifically to separate "selectivity does not
help" from "max is too noisy to tell" — a maximum over 384 dimensions being
upward-biased and outlier-dominated. The discrimination came out clean: **max
is not too noisy; it is the better of the two**, ahead of the damped top-3.
That is worth recording because the prediction went the other way.

### E2 is not promoted, deliberately

E2 at 0.6507 is the second-highest score measured and sits +0.0161 above the
reported baseline. It stays unpromoted, because the pre-registration said
displacing the baseline is a separate question needing its own comparison, and
that a winner here is not thereby promoted. Reaching for the promotion now — on
an unresolved delta measured against a *different* reference — is the forking
path the discipline exists to close.

**V0 remains the reported baseline at 0.6346.**

### Scoreboard

Seven pre-registered comparisons, seven unresolved. The recurring lesson is
unchanged: 58 studies cannot resolve differences of this magnitude. What is new
is that there is now a **mechanism with directional evidence behind it** rather
than a run of nulls — the aggregation, not the amount of data or the
representation, is where the focal findings were being lost.

## 2026-08-28 — Image baseline v11: a linear head on 58 studies blends, it does not choose

**Kernel:** version 11, Tesla T4, `COMPLETE`. E4 concatenates the slice mean
and slice max per plane at the same 15-slice density, registered as two
comparisons in one family (Bonferroni α/2, 97.5%).

| Comparison | E4 | Reference | Delta | 97.5% interval | Resolved |
|---|---:|---:|---:|---|---|
| E4 vs E1 (mean) | 0.6349 | 0.6321 | +0.0028 | [−0.0135, +0.0214] | **No** |
| **E4 vs E2 (max)** | 0.6349 | **0.6507** | **−0.0158** | [−0.0353, **+0.0016**] | **No** |

The second interval misses excluding zero by 0.0016 — the closest this project
has come to resolving anything, and it points *against* the wider variant.

### The premise is falsified, and precisely

The idea was that giving the head both statistics would let it weight them per
label — max for focal findings, mean for diffuse ones. It does not.

- Pearson **r = −0.866** between how much max gained on a label and how much E4
  gave back on it.
- **11 of 12 labels** move opposite to max's gain.
- E4 sits a median **55%** of the way from mean to max, label by label.

| | E1 mean | E2 max | E4 both | max gain | E4 gives back |
|---|---:|---:|---:|---:|---:|
| Lateral OA | 0.654 | 0.745 | 0.692 | +0.091 | −0.052 |
| Synovitis | 0.539 | 0.615 | 0.583 | +0.076 | −0.032 |
| PF OA | 0.595 | 0.660 | 0.622 | +0.066 | −0.039 |
| Effusion | 0.805 | 0.764 | 0.783 | −0.041 | **+0.019** |
| Medial Meniscus | 0.575 | 0.516 | 0.525 | −0.059 | **+0.010** |

**E4 is an interpolation, not a selection.** Every label max won is dragged
back toward the mean; the three max lost are recovered. An L2-penalised linear
head on 58 studies cannot learn to read one half of the block for some labels
and the other half for others — it spreads weight across both and lands in
between.

This is worth stating as a general constraint on this dataset: **giving a small
linear head a choice does not make it choose.** Offering two views costs the
width and returns their average. If a per-label operator is wanted, it has to
be imposed by design, not offered and hoped for.

Two explanations survive and this data cannot separate them: the doubled width
costing more under L2 than the second view returns, or the mean features
actively reintroducing the dilution max removed. The per-label pattern fits
both, since max's gains were the largest coefficients and so the most exposed
to shrinkage.

### The harness retrofit is verified

V1 reproduced 0.6301396031 exactly through the shared cross-validation path,
so deleting its hand-rolled fold loop — where the round-97 defect lived —
changed nothing but the safety. That defect class is now closed by a test that
fails on the mistake itself: a widened frame at the default scaler width is
rejected, and at the correct width scores identically to the narrow frame when
the added block carries no information.

### Scoreboard

**Eight pre-registered comparisons, eight unresolved.** (An earlier entry said
seven at a point where the count was six; corrected here.)

The best configuration measured is **E2, max pooling at fifteen slices, at
0.6507** — and this round rules out the obvious route to improving on it.
Whether E2 displaces the reported baseline is a separate registered question,
still open, because every measurement of E2 so far has been against the mean at
its own density rather than against the incumbent.

**V0 remains the reported baseline at 0.6346.**

## 2026-08-28 — Image baseline v12: the baseline stands, and how many studies it would take

**Kernel:** version 12, Tesla T4, `COMPLETE`. Max pooling at fifteen slices
against the reported baseline, reusing existing out-of-fold probabilities so
the studies and folds are unchanged.

| Level | Delta | Interval | Excludes zero | Displaces |
|---|---:|---|---|---|
| Nominal 95% (one comparison) | +0.0161 | [−0.0071, +0.0410] | No | No |
| **Registered 99.44% (family of 9)** | +0.0161 | [−0.0172, +0.0532] | No | **No** |

**V0 stands at 0.6346.** Max pooling scores +0.016 higher and the evidence does
not support changing the reported figure.

It fails at *both* levels, which is a cleaner outcome than the registered rule
anticipated: the nominal interval already contains zero, so there is no
nominal-yes/strict-no gap to argue over.

### How many studies this question actually needed

Interval half-width scales roughly as 1/√n:

| To resolve +0.016 at | Studies needed |
|---|---:|
| Nominal 95% | **~129** |
| Project-wide corrected level | **~276** |

Against 58 available. The aggregation question was never answerable on this
labelled set — nine comparisons established that empirically rather than by
assertion, and this is the number that should have been computed first.

### The nulls are not interchangeable

Nine pre-registered comparisons, nine unresolved. But three of them isolate a
mechanism, and read together they say something specific:

1. **Enlarging what is averaged does not help.** Patch tokens −0.027; tripled
   slice density −0.003, the latter measured with roughly twice the power of
   any other comparison.
2. **Replacing the average with a selection does help, directionally.** Max
   +0.019 over the mean at identical density, with per-label signs a
   bag-of-slices model predicts — focal findings up, effusion (the one diffuse
   finding) down.
3. **Offering the head both does not let it choose.** r = −0.866 between a
   label's max-gain and its loss under concatenation; it lands a median 55%
   between the two operators.

The aggregation step is where focal findings are lost; selection is the right
correction; and a small linear head cannot be *given* a choice, only designed
around. None of it resolved at 58 studies, all of it directional evidence for a
design that had more.

### Closing position

**Reported baseline: pooled OOF macro AUC 0.6346, bootstrap 95% [0.5704,
0.6973], over 58 human-labelled studies.** No variant displaced it. The score
work is closed — further variants would spend runs on a question this dataset
has demonstrably answered as "not answerable".
