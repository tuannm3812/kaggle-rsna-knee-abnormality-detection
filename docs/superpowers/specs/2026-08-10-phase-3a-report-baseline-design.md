# Phase 3A Report Baseline — Design

Date: 2026-08-10  
Status: **Approved section by section by the user; awaiting Claude's
whole-spec review and the user's final written-spec approval**

## 1. Purpose

Phase 3A establishes the first leakage-safe competition baseline and the
first kernel-native submission path. It uses only report text and the 58
human-labeled studies, produces deterministic out-of-fold (OOF) evidence,
then refits the identical frozen model on all labeled studies to predict the
test set.

This phase also turns the existing EDA and weak-label notebooks into concise,
publication-ready narratives. All kernels remain private during development;
publication is a separate user decision.

Phase 3A is the first part of the user-approved strategy-A sequence:

1. Phase 3A — report-only baseline and submission pipeline.
2. Phase 3B — frozen image-embedding baseline on the same folds.
3. Phase 3C — one predefined late-fusion rule after both unimodal OOF sets
   exist.

## 2. Scope and exclusions

### In scope

- Deterministic iterative multilabel-stratified cross-validation.
- A frozen character n-gram TF-IDF plus one-vs-rest logistic-regression
  report model.
- Pooled OOF macro/per-label AUC and fold-level diagnostic scores.
- Full-data refit, test prediction, submission validation, and
  `/kaggle/working/submission.csv` generation.
- Kernel-native submission following shared coding standards section 11.
- Public-facing editorial and privacy passes for `01_eda.ipynb` and
  `02_weak_label_evaluation.ipynb`.
- Project-standard, README, strategy, experiment, and submission-log updates
  required by this work.

### Out of scope

- Weak labels, pseudo-labels, or human labels as model inputs.
- MRI pixels, DICOM-derived features, or image embeddings (Phase 3B).
- Multimodal fusion (Phase 3C).
- Hyperparameter sweeps, seed searches, fold searches based on scores,
  calibration, threshold tuning, or leaderboard-driven selection.
- Making kernels or the attached source dataset public.
- Automatically submitting a completed kernel without the user's explicit
  approval of that exact kernel version.

## 3. Notebook portfolio and presentation contract

### `notebooks/01_eda.ipynb`

Rewrite as a professional aggregate-only data story:

1. Competition data overview.
2. Labeled-versus-report-only split and label prevalence.
3. Series, plane, and sequence composition.
4. Aggregate report-length and orthographic evidence.
5. Slice-count distribution.
6. Findings, limitations, and modeling implications.

Remove raw report excerpts, study identifiers, `NOTEBOOK_VERSION`, printed
platform/path diagnostics, troubleshooting prose, and internal workflow
notes. Retain the functional `IS_KAGGLE` fail-fast guard. Replace the current
raw-report spot check with aggregate-only evidence.

### `notebooks/02_weak_label_evaluation.ipynb`

Keep the existing evaluation logic but replace every stale “pending first
Kaggle run” Markdown cell with the trusted Phase 2 evidence already recorded
in `docs/4_experiments.md`:

- Naive versus assertion-aware precision/recall/coverage interpretation.
- Aggregate error-taxonomy interpretation.
- Labeled-versus-unlabeled orthographic comparison.
- Empty allowlist and the 0/12 No-go conclusion.
- Explicit implication: Phase 3A uses only the 58 human labels.

No report text, study identifier, or per-row prediction may be displayed.

### `notebooks/03_baseline_modeling.ipynb`

One linear end-to-end notebook, without separate evaluation/submission modes:

1. Problem and frozen experiment contract.
2. Offline dependency and Kaggle-only setup.
3. Data loading and validation.
4. Deterministic fold construction and preflight evidence.
5. Constant-0.5 sanity baseline.
6. Fold-local report-model OOF evaluation.
7. Pooled and per-label interpretation.
8. Full-data refit and test prediction.
9. Submission validation and artifact creation.
10. Limitations and the Phase 3B next step.

Every important aggregate table or chart has adjacent Markdown explaining
what it shows, why it matters, and what it does not establish. Markdown is
reader-facing; it does not contain housekeeping, local filesystem guidance,
agent notes, or internal handoff prose.

Repository notebook copies remain output-free. Trusted Kaggle runs may show
safe aggregate outputs. Because Phase 3A results do not exist before the first
run, the first output-free scaffold explains how each result will be read
without claiming a value. After that trusted run, transcribe the aggregate
results into Markdown, commit them, push a final candidate kernel, and confirm
the rerun reproduces the same result before submission.

## 4. Kaggle-only setup and offline dependency

All notebooks retain:

```python
IS_KAGGLE = Path("/kaggle/input").exists()
if not IS_KAGGLE:
    raise RuntimeError("This notebook runs on Kaggle only.")
```

Do not print `IS_KAGGLE`, source roots, competition paths, or wheel paths.
Remove `NOTEBOOK_VERSION` entirely.

Pin the stratifier dependency to:

- Package: `iterative-stratification==0.1.9`
- Wheel: `iterative_stratification-0.1.9-py3-none-any.whl`
- Size: 8,515 bytes
- SHA-256:
  `476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80`
- License: BSD 3-Clause
- Declared dependencies: NumPy, SciPy, scikit-learn

Track the exact wheel and a verbatim upstream license copy under `vendor/`.
Extend `scripts/publish_code_dataset.sh` to stage both files into the existing
`tuannm3812/rsna-knee-mri-src` Kaggle dataset. The notebook locates the exact
filename within that attached dataset, verifies its SHA-256, and installs it
with `python -m pip install --no-index <wheel>`. Installation output may be
suppressed after checking the subprocess return code. No URL access or
fallback package version is permitted.

After installation, verify
`importlib.metadata.version("iterative-stratification") == "0.1.9"` before
importing `MultilabelStratifiedKFold`. A missing wheel, checksum mismatch,
installation failure, or version mismatch stops the notebook with a concise
error that does not print the resolved path.

Add `iterative-stratification==0.1.9` to the project's runtime dependencies
and update `uv.lock` so local tests use the same pinned release. The vendored
wheel is the Kaggle-offline transport for that dependency, not a different
package source or version.

The attached source dataset remains private during development. Before any
notebook becomes public, the user must separately authorize making this
dependency public or approve a self-contained replacement.

## 5. Input contract

The modeling boundary validates before constructing folds:

- `train.csv` contains `StudyInstanceUID`, `Report`, and all
  `LABEL_COLUMNS`.
- `test.csv` contains `StudyInstanceUID` and `Report`.
- `sample_submission.csv` has exactly `StudyInstanceUID` followed by
  `LABEL_COLUMNS` in canonical order.
- Study identifiers are non-null and unique within train, test, and sample.
- Sample identifiers exactly equal test identifiers in row order.
- `split_labeled_studies(train_df)` returns exactly 58 fully labeled studies.
  Any different count stops execution because this design's validation
  assumptions would need review.
- Labeled target values are Boolean-free binary `0`/`1`; clean `float64`
  `0.0`/`1.0` values from pandas' NaN-driven CSV upcast remain valid.
- Every label has both classes across the 58 labeled studies.
- Labeled reports are strings and non-empty after stripping. Missing or empty
  labeled reports stop execution.
- Non-missing test reports must be strings. Missing or empty test reports are
  replaced with `""` so the final model produces its intercept-based
  probability; display only their aggregate count. A non-string, non-missing
  value stops execution rather than being silently stringified.

Never print raw reports, study identifiers, row-level labels, OOF
probabilities, or test probabilities.

## 6. Deterministic fold contract

Let `y` be the 58-by-12 target matrix in canonical label order. For each
candidate `n_splits` in `(5, 4, 3, 2)`:

1. Construct exactly one
   `MultilabelStratifiedKFold(n_splits=n_splits, shuffle=True,
   random_state=42)`.
2. Materialize its fold assignments once.
3. Verify every validation fold has at least one positive and one negative
   for every label.
4. Select the first passing candidate and stop.

Do not retry another seed at the same fold count. Do not fit a model or view
a score until the fold count is selected. If every candidate fails, raise a
clear error and stop.

The fold assignment stays at study-row level; no report transform or target
statistic is fit globally. Record only aggregate fold sizes and per-label
class counts.

## 7. Frozen report model

Each fold constructs a fresh pipeline with:

```python
TfidfVectorizer(
    analyzer="char_wb",
    ngram_range=(3, 5),
    min_df=2,
    max_features=50_000,
    sublinear_tf=True,
    lowercase=True,
    strip_accents=None,
)
```

`max_features=50_000` is an intentional frozen capacity and memory ceiling;
it may bind. Aggregate learned-vocabulary sizes may be reported but never
used to change the cap.

The classifier is explicit, not the deprecated logistic-regression
multiclass shorthand:

```python
OneVsRestClassifier(
    LogisticRegression(
        penalty="l2",
        solver="liblinear",
        C=1.0,
        class_weight="balanced",
        max_iter=2_000,
        random_state=42,
    ),
    n_jobs=1,
)
```

Treat any `ConvergenceWarning` as an error. Do not raise `max_iter` or change
another setting after viewing results; a failure returns to design review.
An empty TF-IDF vocabulary or any other estimator-fit error also stops the
run; there is no silent change to `min_df`, n-gram range, feature cap, or
classifier settings.

## 8. Evaluation and refit data flow

1. Create an all-`0.5` prediction frame and verify
   `knee_mri.metrics.macro_auc` returns `0.5`.
2. Allocate an all-missing 58-by-12 OOF frame.
3. For each preselected fold:
   - Fit a fresh vectorizer on training-fold reports only.
   - Transform training and validation reports separately.
   - Fit the explicit one-vs-rest classifier on training-fold labels.
   - Store validation probabilities in their original row positions.
   - Compute fold macro/per-label AUC with the existing
     `knee_mri.metrics` functions.
4. Assert every OOF cell was written exactly once and contains a finite
   probability in `[0, 1]`.
5. Compute the primary pooled OOF macro-AUC across all 58 studies using
   `macro_auc` and pooled per-label AUC using `per_label_auc`.
6. Report fold macro-AUC mean and standard deviation as diagnostics only.
7. Fit the identical fresh vectorizer/classifier on all 58 labeled reports
   and predict the test reports.

This is internal cross-validation on the only labeled sample, not an
independent confirmation set. No configuration is selected by OOF score.

## 9. Reusable package boundaries

New tested logic belongs in focused `src/knee_mri` modules rather than being
duplicated in the notebook:

- `model_selection.py`
  - `select_multilabel_folds(y, candidate_splits=(5, 4, 3, 2), seed=42)`
    returns the selected fold count and index pairs after class preflight.
- `report_model.py`
  - `build_report_vectorizer()` returns the frozen TF-IDF configuration.
  - `build_report_classifier()` returns the frozen explicit OVR classifier.
  - `cross_validate_report_model(reports, y, folds)` returns OOF
    probabilities, pooled/fold metrics, and safe aggregate diagnostics.
  - `fit_report_model(reports, y)` returns the full-data fitted components.
- `submission.py`
  - `build_submission(sample_df, test_ids, probabilities)` validates and
    returns a schema-safe submission frame.

Public interfaces receive type hints and Google-style docstrings. Validation
errors identify the violated aggregate/schema rule without echoing sensitive
values.

## 10. Submission contract

`build_submission` must verify:

- Probability shape is `(len(test_df), 12)`.
- Columns are exactly `StudyInstanceUID` plus `LABEL_COLUMNS`.
- Row count equals both test and sample row counts.
- Submission identifiers equal test identifiers in the original order.
- Identifiers are non-null and unique.
- Every probability is finite and in `[0, 1]`.

Copy the sample submission, replace only its target values, validate, then
write `/kaggle/working/submission.csv`. Display only shape and aggregate
per-label probability summaries.

Kernel-native release follows shared coding standards section 11:

1. Publish the reviewed source dataset containing package code, the exact
   offline wheel, and its license.
2. Push refined EDA and weak-label notebooks and confirm both complete with
   internet disabled.
3. Push the Phase 3A notebook, wait for `KernelWorkerStatus.COMPLETE`, and
   inspect its safe aggregate outputs.
4. Verify the kernel-generated `submission.csv` and the recorded OOF result.
5. Transcribe the trusted aggregate result into notebook Markdown and
   `docs/4_experiments.md`; push the final candidate and confirm the rerun
   reproduces it.
6. Ask the user to approve that exact kernel ID/version for leaderboard
   submission.
7. Submit through `scripts/submit_kaggle.sh`, which calls
   `api.competition_submit_code(...)`; do not upload a separately generated
   CSV.
8. Record the submission date, kernel version, message, status, and score in
   `docs/5_submissions.md` when available.

## 11. Kernel metadata

Create `notebooks/kernels/baseline-modeling/kernel-metadata.json` with:

- ID: `tuannm3812/rsna-knee-baseline-modeling`
- Title: `RSNA Knee Baseline Modeling`
- Code file: `03_baseline_modeling.ipynb`
- Language/type: Python notebook
- Private: `true`
- GPU/TPU: `false`
- Internet: `false`
- Dataset source: `tuannm3812/rsna-knee-mri-src`
- Competition source: `rsna-knee-abnormality-detection`

Also set the EDA kernel's current `enable_internet` value to `false`; the
weak-label kernel is already offline.

## 12. Testing and verification

Add local synthetic tests for:

- Exact deterministic fold output for repeated calls.
- Five-fold selection when feasible.
- Deterministic fallback to fewer folds.
- Clear failure when no candidate has both classes per validation fold.
- Frozen vectorizer and classifier parameters.
- OOF shape, complete single coverage, finite probabilities, and metric
  output on a sufficiently sized synthetic multilabel fixture.
- Fold-local vectorizer fitting (validation-only tokens never enter that
  fold's learned vocabulary).
- Boolean/non-binary labels, duplicate identifiers, missing labeled reports,
  and schema errors.
- Submission column order, identifier order, row count, duplicate IDs,
  probability shape, non-finite values, and out-of-range values.
- Constant-0.5 macro-AUC sanity behavior.
- Vendored wheel filename/SHA-256 and presence of the accompanying upstream
  BSD 3-Clause license text.

Notebook checks must confirm:

- Valid notebook JSON and standard kernel metadata.
- Zero committed outputs and null execution counts.
- No `NOTEBOOK_VERSION`.
- Functional `IS_KAGGLE` guard present, diagnostic print absent.
- No raw-report, study-identifier, row-level label, or prediction printing.
- No runtime URL download or internet-enabled kernel.
- Insight/interpretation Markdown follows each important aggregate result.

Before each implementation handoff, run the relevant focused tests, then:

```bash
uv run pytest -q
uv run ruff check .
git diff --check
```

## 13. Documentation changes

The implementation updates:

- `docs/0_coding_standards.md`
  - Notebook sequence becomes EDA → weak-label evaluation → baseline
    modeling.
  - Keep the functional Kaggle-only guard but remove its diagnostic print.
  - Remove the `NOTEBOOK_VERSION` requirement.
  - Require public-facing aggregate-only notebook prose and Title Case kernel
    titles.
- `README.md`
  - Replace the stale scaffolding badge/status with current Phase 3A
    progress.
- Both historical implementation plans
  - Add a short completed/historical status note without rewriting their
    original unchecked execution trace.
- `docs/3_strategy.md`
  - Record Phase 3A/3B/3C sequencing and Phase 3A status.
- `docs/4_experiments.md`
  - Append the trusted Phase 3A OOF configuration/result after the Kaggle
    run; do not predict or prefill its score.
- `docs/5_submissions.md`
  - Append the real kernel-native submission only after it occurs.

## 14. Acceptance criteria

Phase 3A implementation is complete only when:

- All local tests and lint pass.
- All three repository notebooks are output-free and pass the presentation
  and privacy checks.
- All three kernels complete with internet disabled.
- The final baseline kernel reproduces its recorded aggregate OOF result and
  writes a schema-valid `submission.csv` within the competition runtime.
- The user approves and the exact completed kernel version is submitted via
  the kernel-native API.
- Experiment and submission records match the actual run and score.
- Claude's implementation review has no unresolved finding.

Publication is not part of Phase 3A completion. Kernels and the source dataset
remain private until the user makes a separate publication decision.
