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
