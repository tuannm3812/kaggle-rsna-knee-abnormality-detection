# EDA Insights

First trusted Kaggle run: `01_eda.ipynb` kernel version 6
(`tuannm3812/rsna-knee-eda`), 2026-08-09, `NOTEBOOK_VERSION=v4`, COMPLETE.
Full log: `docs/6_kaggle_troubleshooting.md` has the mount-path debugging
history that preceded this run.

## Labels are extremely sparse — 58 labeled studies out of 4407

`train.csv` has **4407 studies total, but only 58 (1.3%) carry the 12
human-annotated labels**; the remaining 4349 are report-only. This is a
far more extreme labeled/unlabeled ratio than "a small subset carries
labels" suggested on its own. Weak-label mining from `Report` (via
`knee_mri.labels.extract_weak_labels`, the assertion-aware extractor)
was evaluated against the 58 human labels in Phase 2 — **verdict:
No-go, 0/12 labels clear the allowlist gate** (small-sample confidence
intervals, not a precision ceiling — see `docs/4_experiments.md` and
`docs/3_strategy.md` Phase 2). Phase 3 trains on the 58 human labels
alone rather than an expanded weak-labeled set for now.

## `train.csv` has no `PatientSex` column

Contrary to the competition's data description ("PatientSex - patient sex
... may be blank"), the actual `train.csv` snapshot has exactly 14
columns: `StudyInstanceUID`, `Report`, and the 12 label columns — no
`PatientSex`. `01_eda.ipynb` now checks for the column's presence before
using it rather than assuming it exists. Re-check this if the competition
data is ever refreshed/re-downloaded; the description may simply be
ahead of (or behind) the currently mounted snapshot.

## Series-level composition

24371 series across the 4407 studies (~5.5 series/study on average).
`Anatomical_Plane`: Sagittal 9864, Coronal 8609, Axial 5898 — all three
planes well represented, sagittal most common (expected for knee MRI
protocols). `Fluid_Sensitive` and `Fat_Suppression` have the **identical**
mean (0.574864) across all series — worth confirming whether these two
columns are simply always equal in this dataset (i.e. every fluid-
sensitive sequence here also uses fat suppression) or coincidentally
correlated; if genuinely always equal, `select_primary_series`'s
fluid-sensitive preference and any future fat-suppression-based feature
would carry identical information.

## Report language is genuinely multilingual

Real samples (first 200 studies scanned) included German, Turkish,
Croatian, Greek, and English reports — confirms the data description's
"may be in any of several languages" is not a rare edge case.
`extract_weak_labels`'s keyword vocabulary is English-only; Phase 2's
error taxonomy shows this is a real, if unproven, contributor to its
No-go result — most false negatives are `no_mention` (no keyword matched
at all), concentrated in non-`ascii_only` orthographic buckets. A
multilingual keyword/assertion extractor is recorded as a future
strategy fork in `docs/3_strategy.md` Phase 2, not scoped or implemented
yet.

## Slice count per series roughly matches the documented distribution

Sampled 1109 series across the first 200 studies: mean 35.45, std 33.26,
min 11, median 30 (matches the data description's stated median exactly),
75th percentile 34, max 320 (confirms the "long tail to a few hundred"
claim).
