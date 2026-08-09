# Weak-Label Calibration — Design

Date: 2026-08-09
Status: Approved

## Problem

`docs/2_eda_insights.md`'s first trusted EDA run (kernel
`tuannm3812/rsna-knee-eda` v7) found that only **58 of 4407 training
studies (1.3%) carry human-annotated labels**; the remaining 4349 have
only `Report` text. `src/knee_mri/labels.py::extract_weak_labels` exists
to derive weak labels for those 4349 studies, but it is currently a naive,
English-only regex extractor with no negation handling — both documented
as known limitations in its own docstring. The same EDA run confirmed
reports are genuinely multilingual (German, Turkish, Croatian, Greek, and
English observed in a 5-report sample), so the English-only gap is real,
not hypothetical.

This work calibrates that extractor against real ground truth (the 58
labeled studies) and fixes whatever the data actually shows is the
biggest problem, rather than guessing upfront.

## Constraint: competition data never leaves Kaggle

Same "Kaggle-only execution" principle as the rest of this project
(`docs/0_coding_standards.md`), extended to this calibration work
specifically: **no raw report text is copied into this git repo** — not
into notebooks, docs, or test fixtures. Competition data-usage terms don't
permit redistributing the dataset, and copying substantial verbatim
excerpts into git history (especially given the winners' obligation to
eventually open-source solution code) would do exactly that.

Concretely: real report text may be viewed transiently in a Kaggle kernel
log while iterating (same workflow already used debugging the EDA
notebook's mount path), but only **aggregate metrics** (precision/recall/
F1 numbers) and **synthesized, hand-written fixture text** (inspired by
observed patterns, not copied from them) come back into the repository.

## Design

### 1. `src/knee_mri/label_calibration.py` (new)

```python
def weak_label_metrics(true_df: pd.DataFrame) -> pd.DataFrame:
    """Score extract_weak_labels against ground-truth labels.

    For each of the 12 LABEL_COLUMNS, runs extract_weak_labels on every
    row's Report and compares the result to that row's true label,
    returning TP/FP/FN/TN counts plus precision/recall/F1.

    Args:
        true_df: A frame with a Report column and all 12 LABEL_COLUMNS
            as ground-truth 0/1 values (e.g. the labeled subset of
            train.csv from split_labeled_studies).

    Returns:
        A DataFrame indexed by label, one row per LABEL_COLUMNS entry,
        with columns tp, fp, fn, tn, precision, recall, f1.
    """
```

Tested locally with small synthetic report/label fixtures (hand-written
sentences, not real competition data) covering: a clean true positive, a
clean true negative, a false positive (keyword present but should have
been negative — synthetic, not from real data), and a false negative.
Division-by-zero (a label with zero predicted positives, or zero actual
positives in the fixture) must not raise — return `0.0` for the
undefined-but-conventionally-zero case, matching common precision/recall
convention (unlike `metrics.py::per_label_auc`, which intentionally raises
on a degenerate single-class column — that's a different metric with a
different degenerate case).

### 2. `notebooks/02_weak_label_calibration.ipynb` (new)

Kaggle-only, same shape as `01_eda.ipynb`: `IS_KAGGLE` check, deterministic
seed, `NOTEBOOK_VERSION`, real cells (not placeholders):

1. Purpose statement.
2. Config cell (reuse the same mount-path resolution as `01_eda.ipynb`,
   including the `SRC_DATASET_DIR`/`DATA_DIR` fix from
   `docs/6_kaggle_troubleshooting.md`).
3. Load `train.csv`, split via `knee_mri.dataset.split_labeled_studies`,
   keep only the 58 labeled rows.
4. Call `knee_mri.label_calibration.weak_label_metrics` on the labeled
   subset; print the per-label precision/recall/F1 table.
5. **Baseline measurement** — run and record real numbers (this pass,
   before any extractor change).
6. Apply one targeted fix to `extract_weak_labels` (see below), re-run the
   same cell, record the after numbers.
7. Insight cells with real, timeless findings only (no report excerpts).

Needs its own `notebooks/kernels/weak-label-calibration/
kernel-metadata.json`, pushed via `scripts/push_kaggle_kernel.sh
weak-label-calibration`. Since `label_calibration.py` lives in
`src/knee_mri`, this kernel also needs `dataset_sources: ["tuannm3812/
rsna-knee-mri-src"]` — the dataset must be republished (`scripts/
publish_code_dataset.sh version "add label_calibration"`) before this
notebook's first push, or the import fails the same way `01_eda.ipynb`'s
early kernel versions did.

### 3. One targeted extractor fix

Baseline precision/recall (from step 5 above) determines which single fix
is worth making now — decided from real data, not speculated in this
spec. The two candidates already flagged as known gaps:

- **Negation handling**: `extract_weak_labels`'s docstring already
  documents "no evidence of fracture" as a known false-positive case.
  Language-agnostic-ish approaches exist (e.g. a short window-before-match
  check for common negation cues), but "language-agnostic" is itself an
  assumption to verify, not assume.
- **Multilingual keyword coverage**: extend `_LABEL_PATTERNS` with
  keyword variants for languages actually confirmed present, but only
  informed by patterns observed on Kaggle (never copied verbatim) and
  written as new synthesized test fixtures, not real excerpts.

Implement whichever the baseline numbers justify; do not implement both
speculatively in one pass. Document the choice and reasoning in
`docs/4_experiments.md` alongside the before/after numbers.

### 4. `docs/4_experiments.md` entry

Append one entry: baseline per-label precision/recall/F1, the fix applied
and why (grounded in the baseline numbers, not speculation), after
numbers, and a one-line conclusion. This is the "every local/Kaggle
validation run" log the file already exists for — no new doc needed.

## Out of scope for this pass

- Perfecting the extractor across all languages/labels — one targeted,
  data-justified fix per this pass, further iteration is a follow-up.
- Applying weak labels to actually expand the training set for a baseline
  model — that's the next piece of work after this one, not part of it.
- Any change to `metrics.py`'s `per_label_auc`/`macro_auc` — those score
  continuous predictions against ground truth for the competition metric;
  `weak_label_metrics` is a separate concern (scoring a binary weak-label
  *extractor* against ground truth) and must not be confused with or
  merged into the competition metric.
