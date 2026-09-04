# kaggle-rsna-knee-abnormality-detection

Kaggle RSNA Knee Abnormality Detection — predict per-study probabilities for 12
knee MRI findings (ACL/MCL/meniscus injury, three-compartment osteoarthritis,
effusion, synovitis, Baker's cyst, contusion, fracture) from a **569.76 GB**
dataset pairing DICOM series with free-text radiology reports. Scored by
**macro-averaged AUC-ROC**.

## Standards

Follow the master standard at `~/Documents/GitHub/coding-standards/`.
Project-specific rules and deliberate overrides: @docs/0_coding_standards.md

## Deltas from the master

**Execution is Kaggle-only.** The dataset is ~570 GB and is never downloaded
locally. Anything that touches real data runs on Kaggle Kernels where it is
already mounted. Local execution is for tests against small synthetic fixtures
in `tests/`, and for nothing else. A result is trustworthy only if it came from
a kernel run.

**`src/knee_mri/` is written from scratch, not vendored.** Unlike the Biohub
project, no official baseline exists for this competition — the DICOM I/O,
report weak-label mining, study-level dataset assembly and the macro-AUC metric
are all project code, and all covered by `tests/` against synthetic fixtures.
Changing them means updating those tests.

**Scale changes what an experiment costs.** At this dataset size a careless
sweep is not slow, it is unaffordable. Measure before scaling, and prefer a
cheap diagnostic over a speculative kernel run.

## Evidence locations

- `docs/1_instructions.md` — competition spec, data format, submission mechanism
- `docs/2_eda_insights.md` — EDA findings from trusted kernel runs
- `docs/3_strategy.md` — competitive-landscape analysis and the roadmap
- `docs/4_experiments.md` — **every local and Kaggle validation run.** Any claim
  about model behaviour traces to a row here
- `docs/5_submissions.md` — every real submission
- `docs/6_kaggle_troubleshooting.md` — reusable diagnosis for Kaggle CLI/API friction
- `docs/7_image_baseline_insights.md` — the frozen-encoder image baseline

## State

A frozen-encoder image baseline is implemented, run end to end on Kaggle,
evaluated with an uncertainty estimate, and submitted. Two submissions as of the
last README update: mean pooling **0.681** and max pooling **0.687** public LB.

`docs/5_submissions.md` is authoritative; prefer it over this section, and over
the README, if they disagree.

## Open risks

- **Phase 2 (weak-label evaluation) returned a No-go.** That is a recorded
  result, not an oversight — do not re-run it expecting a different answer
  without a new reason, and read `docs/4_experiments.md` first.
- Report text and image signal are separate workstreams; a claim about one is
  not evidence about the other.
- Mutable facts — leaderboard standing, public approaches, GPU quota — are
  re-checked live, never recalled.
