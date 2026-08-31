# Phase 3A Report Baseline Implementation Plan

> **Historical artifact — do not execute.** Phase 3A was implemented in full,
> then stopped at Kaggle Task 10: the real competition `test.csv` carries no
> `Report` column, so a report-only model can never produce a submission. It
> stands as a train-only signal audit (`docs/3_strategy.md` Phase 3A).
>
> **This plan's closing steps name an archive file that was never created
> under that name.** The collaboration log was not archived at the end of
> Phase 3A — it stayed open through Phase 3B, the aggregation comparisons and
> W1, and was archived on 2026-08-31 after 115 rounds as
> `docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md`, whose
> name reflects that wider scope. Read `2026-08-10-phase-3a-report-baseline.md`
> in the steps below as that file. The in-plan instructions to append rounds to
> `docs/collaboration/active_task.md` were correct while this plan was live and
> are left as written.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, validate, run, and submit the frozen report-only Phase 3A baseline while turning all three notebooks into professional, aggregate-only Kaggle kernels.

**Architecture:** Keep validation, fold selection, report modeling, and submission construction in small tested `knee_mri` modules; the notebooks orchestrate those interfaces in one linear Kaggle-only flow. Ship the pinned iterative-stratification wheel through the existing private source dataset, evaluate with deterministic study-level OOF predictions, refit once on all 58 human-labeled studies, and release only after a reproducible kernel rerun and explicit user approval.

**Tech Stack:** Python 3.11+, pandas, NumPy, scikit-learn, iterative-stratification 0.1.9, pytest, Ruff, Jupyter notebook JSON, Kaggle CLI/API, Bash.

## Global Constraints

- Work on the shared `main` checkout; do not create a worktree unless the user explicitly requests one.
- Codex is the implementer and Claude is the independent reviewer. Append and commit every feedback pass as a numbered round in `docs/collaboration/active_task.md`.
- Stop at the review checkpoints after Tasks 5, 9, and 11. Do not continue while a Claude finding is unresolved.
- Use only the 58 fully human-labeled studies for fitting and OOF evaluation; weak labels, MRI features, leaderboard feedback, and target columns are forbidden model inputs.
- Select folds by one deterministic iterative split per candidate `(5, 4, 3, 2)` with seed `42`; never retry seeds or consult model scores during fold selection.
- Freeze TF-IDF at `analyzer="char_wb"`, `ngram_range=(3, 5)`, `min_df=2`, `max_features=50_000`, `sublinear_tf=True`, `lowercase=True`, and `strip_accents=None`.
- Freeze the classifier as explicit `OneVsRestClassifier(LogisticRegression(penalty="l2", solver="liblinear", C=1.0, class_weight="balanced", max_iter=2_000, random_state=42), n_jobs=1)`.
- Treat `ConvergenceWarning`, empty vocabulary, and every estimator-fit error as fatal; do not retune after viewing results.
- Pin `iterative-stratification==0.1.9`; vendor only `iterative_stratification-0.1.9-py3-none-any.whl` with SHA-256 `476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80` and its verbatim BSD 3-Clause license.
- Keep the functional `IS_KAGGLE` fail-fast guard, remove `NOTEBOOK_VERSION`, and never print platform values or filesystem paths.
- Never display or commit report text, study identifiers, row-level labels, OOF rows, test predictions, fitted features, or generated `submission.csv` data.
- Repository notebooks remain output-free with null execution counts. All kernels and the source dataset remain private; publication is outside this phase.
- The only submission method is the exact completed kernel version through `scripts/submit_kaggle.sh`; require explicit user approval immediately before submission.

---

### Task 1: Pin and Package the Offline Stratifier

**Files:**
- Create: `vendor/iterative_stratification-0.1.9-py3-none-any.whl`
- Create: `vendor/iterative-stratification-LICENSE.txt`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `scripts/publish_code_dataset.sh`
- Create: `tests/test_vendor_assets.py`

**Interfaces:**
- Consumes: the existing `scripts/publish_code_dataset.sh <create|version>` staging flow.
- Produces: an importable core dependency and two verified offline files staged under the source dataset's `vendor/` directory.

- [ ] **Step 1: Write the failing asset and publisher tests**

```python
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

WHEEL_NAME = "iterative_stratification-0.1.9-py3-none-any.whl"
WHEEL_SHA256 = "476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80"


def test_vendored_iterative_stratification_wheel_is_exact_release() -> None:
    wheel = Path("vendor") / WHEEL_NAME
    assert wheel.stat().st_size == 8_515
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == WHEEL_SHA256


def test_vendored_iterative_stratification_license_is_bsd_3_clause() -> None:
    license_text = Path("vendor/iterative-stratification-LICENSE.txt").read_text()
    assert "BSD 3-Clause License" in license_text
    assert "Redistribution and use in source and binary forms" in license_text
    assert "THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS" in license_text


def test_code_dataset_publisher_stages_vendor_directory(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    captured_stage = tmp_path / "captured-stage"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "stage_dir=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ $1 == '-p' ]]; then stage_dir=$2; shift 2; else shift; fi\n"
        "done\n"
        "cp -R \"${stage_dir}\" \"${CAPTURED_STAGE}\"\n"
    )
    fake_uv.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "CAPTURED_STAGE": str(captured_stage),
    }

    subprocess.run(
        ["bash", "scripts/publish_code_dataset.sh", "create"],
        check=True,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert (captured_stage / "vendor" / WHEEL_NAME).is_file()
    assert (captured_stage / "vendor" / "iterative-stratification-LICENSE.txt").is_file()
```

- [ ] **Step 2: Run the focused tests and confirm the assets are absent**

Run: `uv run pytest tests/test_vendor_assets.py -q`

Expected: FAIL because `vendor/iterative_stratification-0.1.9-py3-none-any.whl` does not exist and the publisher does not stage `vendor/`.

- [ ] **Step 3: Add the exact dependency and retrieve the exact wheel**

Add this core dependency alongside scikit-learn in `pyproject.toml`:

```toml
"iterative-stratification==0.1.9",
```

Then run:

```bash
mkdir -p vendor
uv lock
uv run python -m pip download --no-deps --dest vendor iterative-stratification==0.1.9
```

Extract `iterative_stratification-0.1.9.dist-info/LICENSE.txt` from that wheel verbatim to `vendor/iterative-stratification-LICENSE.txt`. Verify the wheel before proceeding:

```bash
shasum -a 256 vendor/iterative_stratification-0.1.9-py3-none-any.whl
wc -c vendor/iterative_stratification-0.1.9-py3-none-any.whl
```

Expected: hash `476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80` and size `8515` bytes.

- [ ] **Step 4: Stage the vendor directory in the source-dataset publisher**

Add immediately after the existing source-tree copy:

```bash
cp -R "${REPO_ROOT}/vendor" "${STAGE_DIR}/vendor"
```

- [ ] **Step 5: Run dependency and asset verification**

Run:

```bash
uv sync --all-extras
uv run pytest tests/test_vendor_assets.py -q
uv run python -c 'from iterstrat.ml_stratifiers import MultilabelStratifiedKFold; print(MultilabelStratifiedKFold.__name__)'
```

Expected: all asset tests PASS and the import command prints `MultilabelStratifiedKFold`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock vendor scripts/publish_code_dataset.sh tests/test_vendor_assets.py
git commit -m "build(deps): vendor iterative stratification for offline kernels"
```

### Task 2: Extract Shared Labeled-Study and Modeling-Input Validation

**Files:**
- Create: `src/knee_mri/validation.py`
- Create: `tests/test_validation.py`
- Modify: `src/knee_mri/dataset.py`
- Modify: `tests/test_dataset.py`
- Modify: `src/knee_mri/weak_label_evaluation.py`
- Modify: `tests/test_weak_label_evaluation.py`

**Interfaces:**
- Consumes: `split_labeled_studies(train_df) -> tuple[pd.DataFrame, pd.DataFrame]` and `LABEL_COLUMNS`.
- Produces from `validation.py`: the pure raising boundary `validate_labeled_studies(frame: pd.DataFrame) -> None`.
- Produces from `dataset.py`: immutable `ModelingInputs` and `prepare_modeling_inputs(train_df: pd.DataFrame, test_df: pd.DataFrame, sample_df: pd.DataFrame, expected_labeled_count: int = 58) -> ModelingInputs`, alongside the existing dataset-view constructor `split_labeled_studies`.

- [ ] **Step 1: Move the hardened validation matrix to the new public boundary**

Create `tests/test_validation.py` with the existing missing-column, empty-frame, duplicate-ID, non-binary, bool-dtype, mixed-object-bool, clean-float64, fractional-value, and missing-report cases moved from `tests/test_weak_label_evaluation.py`. Import `validate_labeled_studies` from `knee_mri.validation`, call it directly, and add:

```python
def test_validate_labeled_studies_rejects_whitespace_only_report() -> None:
    frame = _true_df([_row("s1", "   ")])

    with pytest.raises(ValueError, match="empty after stripping"):
        validate_labeled_studies(frame)
```

Keep one wiring test in `tests/test_weak_label_evaluation.py`:

```python
def test_weak_label_metrics_uses_shared_labeled_study_validator(monkeypatch) -> None:
    calls = []

    def spy(frame: pd.DataFrame) -> None:
        calls.append(frame)

    monkeypatch.setattr("knee_mri.weak_label_evaluation.validate_labeled_studies", spy)
    true_df = _true_df([_row("s1", "report")])

    weak_label_metrics(true_df, _constant_extractor(None))

    assert calls == [true_df]
```

- [ ] **Step 2: Write modeling-input contract tests beside the existing dataset tests**

Add these cases to `tests/test_dataset.py` and import `prepare_modeling_inputs` from `knee_mri.dataset`. Use a helper that builds 58 rows with every label alternating `0.0/1.0`, plus two test/sample rows. Add tests proving the returned labeled frame has 58 rows, empty test reports normalize to `""`, the missing/empty aggregate count is correct, and these failures raise `ValueError`: wrong labeled count, missing required train/test/sample columns, null or duplicate IDs in each frame, sample/test ID order mismatch, one-class labels, missing labeled reports, and non-string non-missing test reports.

```python
def test_prepare_modeling_inputs_normalizes_empty_test_reports() -> None:
    train_df, test_df, sample_df = _modeling_frames()
    test_df["Report"] = [None, "   "]

    result = prepare_modeling_inputs(train_df, test_df, sample_df)

    assert len(result.labeled_studies) == 58
    assert result.test_studies["Report"].tolist() == ["", ""]
    assert result.missing_test_report_count == 2


def test_prepare_modeling_inputs_rejects_sample_id_reordering() -> None:
    train_df, test_df, sample_df = _modeling_frames()
    sample_df = sample_df.iloc[::-1].reset_index(drop=True)

    with pytest.raises(ValueError, match="same order"):
        prepare_modeling_inputs(train_df, test_df, sample_df)
```

Add this regression to `tests/test_validation.py` so the design-mandated
non-null identifier rule is visible rather than hidden inside implementation:

```python
def test_validate_labeled_studies_rejects_null_study_id() -> None:
    frame = _true_df([_row("s1", "report")])
    frame.loc[0, "StudyInstanceUID"] = None

    with pytest.raises(ValueError, match="null or duplicate StudyInstanceUID"):
        validate_labeled_studies(frame)
```

- [ ] **Step 3: Run tests and confirm the public module is missing**

Run: `uv run pytest tests/test_validation.py tests/test_dataset.py tests/test_weak_label_evaluation.py -q`

Expected: collection FAIL for both missing interfaces:

- `ModuleNotFoundError: No module named 'knee_mri.validation'` from the new
  validation tests.
- `ImportError: cannot import name 'prepare_modeling_inputs' from
  'knee_mri.dataset'` from the expanded dataset tests.

- [ ] **Step 4: Implement the shared validator without weakening Phase 2 behavior**

Create `validation.py` with Google-style docstrings and this shape. The null-ID rejection is an explicit Phase 3A input-contract extension to the extracted Phase 2 behavior; whitespace-only report rejection is the other extension. Both now apply consistently to every caller of the shared public validator:

```python
def validate_labeled_studies(frame: pd.DataFrame) -> None:
    required = {"StudyInstanceUID", "Report", *LABEL_COLUMNS}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"labeled studies are missing required columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("labeled studies have zero rows")
    if frame["StudyInstanceUID"].isna().any() or frame["StudyInstanceUID"].duplicated().any():
        raise ValueError("labeled studies have null or duplicate StudyInstanceUID values")
    for label in LABEL_COLUMNS:
        column = frame[label]
        has_bool = column.apply(lambda value: isinstance(value, (bool, np.bool_))).any()
        if has_bool or not column.isin([0, 1]).all():
            raise ValueError(f"labeled studies column '{label}' has values outside {{0, 1}}")
    reports_are_strings = frame["Report"].apply(lambda value: isinstance(value, str))
    if frame["Report"].isna().any() or not reports_are_strings.all():
        raise ValueError("labeled studies have a missing or non-string Report value")
    if frame["Report"].str.strip().eq("").any():
        raise ValueError("labeled studies have a Report empty after stripping")
```

- [ ] **Step 5: Implement modeling-input assembly in `dataset.py`**

Define the immutable value object beside `split_labeled_studies`:

```python
@dataclass(frozen=True)
class ModelingInputs:
    """Validated train/test views for Phase 3A modeling."""

    labeled_studies: pd.DataFrame
    test_studies: pd.DataFrame
    missing_test_report_count: int
```

Implement `prepare_modeling_inputs` with the exact signature in this task's Interfaces block. The function calls `split_labeled_studies` and `validate_labeled_studies`, then validates exact train/test/sample schemas, null/duplicate IDs, sample/test ID equality in row order, the exact labeled count, both classes for every target, test report types, and empty normalization. Copy returned frames so caller mutations cannot alter inputs. This keeps `validation.py` a pure raising boundary and `dataset.py` responsible for constructing typed views from raw competition frames.

- [ ] **Step 6: Rewire Phase 2 to the public validator**

Delete `_validate_true_df`, import `validate_labeled_studies`, and replace its call inside `weak_label_metrics`:

```python
validate_labeled_studies(true_df)
```

- [ ] **Step 7: Run the validation, dataset, and Phase 2 regression suite**

Run: `uv run pytest tests/test_validation.py tests/test_dataset.py tests/test_weak_label_evaluation.py -q`

Expected: PASS, including clean `float64` labels and element-level bool rejection.

- [ ] **Step 8: Commit**

```bash
git add src/knee_mri/validation.py src/knee_mri/dataset.py src/knee_mri/weak_label_evaluation.py tests/test_validation.py tests/test_dataset.py tests/test_weak_label_evaluation.py
git commit -m "refactor(validation): share hardened labeled-study checks"
```

### Task 3: Select Deterministic Multilabel Folds

**Files:**
- Create: `src/knee_mri/model_selection.py`
- Create: `tests/test_model_selection.py`

**Interfaces:**
- Consumes: a pandas target frame in canonical `LABEL_COLUMNS` order.
- Produces: `select_multilabel_folds(y: pd.DataFrame, candidate_splits: tuple[int, ...] = (5, 4, 3, 2), seed: int = 42) -> tuple[int, tuple[tuple[np.ndarray, np.ndarray], ...]]`.

- [ ] **Step 1: Write fold-selection tests**

```python
def test_select_multilabel_folds_is_repeatable_and_prefers_five() -> None:
    y = _balanced_targets(60)

    first_count, first_folds = select_multilabel_folds(y)
    second_count, second_folds = select_multilabel_folds(y)

    assert first_count == second_count == 5
    for first, second in zip(first_folds, second_folds, strict=True):
        np.testing.assert_array_equal(first[0], second[0])
        np.testing.assert_array_equal(first[1], second[1])
    _assert_every_validation_fold_has_both_classes(y, first_folds)


def test_select_multilabel_folds_falls_back_without_seed_retry(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "knee_mri.model_selection.MultilabelStratifiedKFold",
        _fake_splitter_factory(calls, valid_at=3),
    )

    selected, _ = select_multilabel_folds(_balanced_targets(12))

    assert selected == 3
    assert calls == [(5, True, 42), (4, True, 42), (3, True, 42)]


def test_select_multilabel_folds_raises_when_every_candidate_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "knee_mri.model_selection.MultilabelStratifiedKFold",
        _fake_splitter_factory([], valid_at=None),
    )

    with pytest.raises(ValueError, match="No candidate fold count"):
        select_multilabel_folds(_balanced_targets(12))
```

The fake splitter records constructor arguments and returns fixed train/validation indices. Add a test for noncanonical columns and non-binary target values so the split function fails before constructing a splitter.

- [ ] **Step 2: Run tests and confirm the module is missing**

Run: `uv run pytest tests/test_model_selection.py -q`

Expected: collection FAIL with `ModuleNotFoundError: No module named 'knee_mri.model_selection'`.

- [ ] **Step 3: Implement single-pass candidate selection**

```python
def select_multilabel_folds(
    y: pd.DataFrame,
    candidate_splits: tuple[int, ...] = (5, 4, 3, 2),
    seed: int = 42,
) -> tuple[int, tuple[tuple[np.ndarray, np.ndarray], ...]]:
    """Return the first deterministic split whose validation folds contain both classes."""
    if list(y.columns) != LABEL_COLUMNS:
        raise ValueError("y columns must exactly match LABEL_COLUMNS in canonical order")
    if y.empty or not y.isin([0, 1]).all().all():
        raise ValueError("y must be a non-empty binary target frame")

    positions = np.arange(len(y))
    for n_splits in candidate_splits:
        splitter = MultilabelStratifiedKFold(
            n_splits=n_splits,
            shuffle=True,
            random_state=seed,
        )
        folds = tuple(splitter.split(positions, y.to_numpy()))
        if all(y.iloc[validation].nunique().eq(2).all() for _, validation in folds):
            return n_splits, folds
    raise ValueError("No candidate fold count gives both classes for every validation label")
```

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_model_selection.py -q`

Expected: PASS; the constructor-call assertion proves there is exactly one split object per attempted candidate and no seed retry.

- [ ] **Step 5: Commit**

```bash
git add src/knee_mri/model_selection.py tests/test_model_selection.py
git commit -m "feat(modeling): add deterministic multilabel fold selection"
```

### Task 4: Build and Cross-Validate the Frozen Report Model

**Files:**
- Create: `src/knee_mri/report_model.py`
- Create: `tests/test_report_model.py`

**Interfaces:**
- Consumes: report strings, canonical binary targets, and the index pairs returned by `select_multilabel_folds`.
- Produces: `build_report_vectorizer() -> TfidfVectorizer`, `build_report_classifier() -> OneVsRestClassifier`, immutable `ReportCrossValidationResult`, `cross_validate_report_model(reports: pd.Series, y: pd.DataFrame, folds: tuple[tuple[np.ndarray, np.ndarray], ...]) -> ReportCrossValidationResult`, and `fit_report_model(reports: pd.Series, y: pd.DataFrame) -> tuple[TfidfVectorizer, OneVsRestClassifier]`.

- [ ] **Step 1: Test the exact frozen factories**

```python
def test_report_model_factories_are_frozen() -> None:
    vectorizer = build_report_vectorizer()
    classifier = build_report_classifier()
    estimator = classifier.estimator

    assert vectorizer.analyzer == "char_wb"
    assert vectorizer.ngram_range == (3, 5)
    assert vectorizer.min_df == 2
    assert vectorizer.max_features == 50_000
    assert vectorizer.sublinear_tf is True
    assert vectorizer.lowercase is True
    assert vectorizer.strip_accents is None
    assert classifier.n_jobs == 1
    assert estimator.penalty == "l2"
    assert estimator.solver == "liblinear"
    assert estimator.C == 1.0
    assert estimator.class_weight == "balanced"
    assert estimator.max_iter == 2_000
    assert estimator.random_state == 42
```

- [ ] **Step 2: Test complete OOF coverage, metrics, and leakage safety**

Create a 24-row fixture whose 12 labels alternate with phase offsets and whose four fixed validation folds each contain both classes. Assert:

```python
result = cross_validate_report_model(reports, y, folds)

assert result.oof_probabilities.shape == (24, len(LABEL_COLUMNS))
assert list(result.oof_probabilities.columns) == LABEL_COLUMNS
assert np.isfinite(result.oof_probabilities.to_numpy()).all()
assert result.oof_probabilities.to_numpy().min() >= 0.0
assert result.oof_probabilities.to_numpy().max() <= 1.0
assert result.pooled_macro_auc == pytest.approx(
    macro_auc(y, result.oof_probabilities)
)
assert result.pooled_per_label_auc == per_label_auc(y, result.oof_probabilities)
assert len(result.fold_macro_auc) == len(folds)
assert len(result.fold_per_label_auc) == len(folds)
assert len(result.vocabulary_sizes) == len(folds)
```

Monkeypatch `build_report_vectorizer` with a recording subclass. Put the token `validationexclusive` only in one validation fold and assert the character n-gram `valid` is absent from that fold's recorded vocabulary; this proves each vectorizer was fit on training reports only. Also test duplicate/missing fold coverage and mismatched report/target lengths.

- [ ] **Step 3: Test failure propagation and the constant baseline**

```python
def test_constant_half_predictions_have_macro_auc_one_half() -> None:
    y = _balanced_targets(24)
    predictions = pd.DataFrame(0.5, index=y.index, columns=LABEL_COLUMNS)
    assert macro_auc(y, predictions) == pytest.approx(0.5)


def test_cross_validation_turns_convergence_warning_into_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "sklearn.multiclass.OneVsRestClassifier.fit",
        _fit_that_warns_with_convergence_warning,
    )
    with pytest.raises(ConvergenceWarning):
        cross_validate_report_model(reports, y, folds)
```

Add an empty-vocabulary case and assert scikit-learn's `ValueError` is propagated unchanged. Do not add fallback parameters.

- [ ] **Step 4: Run tests and confirm the module is missing**

Run: `uv run pytest tests/test_report_model.py -q`

Expected: collection FAIL with `ModuleNotFoundError: No module named 'knee_mri.report_model'`.

- [ ] **Step 5: Implement the frozen model and result object**

```python
@dataclass(frozen=True)
class ReportCrossValidationResult:
    """Safe aggregate and OOF products from one frozen CV run."""

    oof_probabilities: pd.DataFrame
    pooled_macro_auc: float
    pooled_per_label_auc: dict[str, float]
    fold_macro_auc: tuple[float, ...]
    fold_per_label_auc: tuple[dict[str, float], ...]
    vocabulary_sizes: tuple[int, ...]
```

Implement the two factories exactly as frozen globally. In cross-validation, allocate an all-NaN OOF frame plus an integer coverage array, instantiate fresh components inside each fold, wrap every fit in:

```python
with warnings.catch_warnings():
    warnings.simplefilter("error", ConvergenceWarning)
    classifier.fit(train_features, y.iloc[train_indices])
```

Increment coverage at validation indices; after the loop require `coverage == 1`, finite values, and probabilities in `[0, 1]`. Compute fold and pooled values only through `knee_mri.metrics.per_label_auc` and `macro_auc`. `fit_report_model` creates another fresh pair, applies the same warning policy, fits all 58 rows, and returns the pair.

- [ ] **Step 6: Run focused tests**

Run: `uv run pytest tests/test_report_model.py tests/test_metrics.py -q`

Expected: PASS, including the validation-only-token leakage test and fatal warning test.

- [ ] **Step 7: Commit**

```bash
git add src/knee_mri/report_model.py tests/test_report_model.py
git commit -m "feat(modeling): add frozen report baseline and OOF evaluation"
```

### Task 5: Build a Schema-Safe Submission Frame

**Files:**
- Create: `src/knee_mri/submission.py`
- Create: `tests/test_submission.py`

**Interfaces:**
- Consumes: `sample_df: pd.DataFrame`, `test_ids: pd.Series`, and `probabilities: np.ndarray` shaped `(len(test_ids), 12)`.
- Produces: `build_submission(sample_df: pd.DataFrame, test_ids: pd.Series, probabilities: np.ndarray) -> pd.DataFrame`.

- [ ] **Step 1: Write the happy-path and failure-matrix tests**

```python
def test_build_submission_preserves_schema_and_identifier_order() -> None:
    sample_df, test_ids = _submission_inputs()
    probabilities = np.full((len(test_ids), len(LABEL_COLUMNS)), 0.25)

    result = build_submission(sample_df, test_ids, probabilities)

    assert list(result.columns) == ["StudyInstanceUID", *LABEL_COLUMNS]
    assert result["StudyInstanceUID"].tolist() == test_ids.tolist()
    np.testing.assert_allclose(result[LABEL_COLUMNS], probabilities)
    assert result is not sample_df
```

Parameterize failures for wrong sample column order, row-count mismatch, null/duplicate sample or test IDs, sample/test order mismatch, wrong probability shape, `NaN`, `inf`, values below zero, and values above one. Match concise aggregate errors that never interpolate an identifier.

- [ ] **Step 2: Run tests and confirm the module is missing**

Run: `uv run pytest tests/test_submission.py -q`

Expected: collection FAIL with `ModuleNotFoundError: No module named 'knee_mri.submission'`.

- [ ] **Step 3: Implement copy-replace-validate behavior**

```python
def build_submission(
    sample_df: pd.DataFrame,
    test_ids: pd.Series,
    probabilities: np.ndarray,
) -> pd.DataFrame:
    """Return a validated submission in competition row and column order."""
    expected_columns = ["StudyInstanceUID", *LABEL_COLUMNS]
    if list(sample_df.columns) != expected_columns:
        raise ValueError("sample submission columns do not match the canonical schema")
    if len(sample_df) != len(test_ids):
        raise ValueError("sample submission and test row counts differ")
    if sample_df["StudyInstanceUID"].isna().any() or test_ids.isna().any():
        raise ValueError("submission identifiers must be non-null")
    if sample_df["StudyInstanceUID"].duplicated().any() or test_ids.duplicated().any():
        raise ValueError("submission identifiers must be unique")
    if not sample_df["StudyInstanceUID"].reset_index(drop=True).equals(
        test_ids.reset_index(drop=True)
    ):
        raise ValueError("sample submission identifiers must match test order")
    values = np.asarray(probabilities, dtype=float)
    if values.shape != (len(test_ids), len(LABEL_COLUMNS)):
        raise ValueError("probability matrix has the wrong shape")
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError("probabilities must be finite and within [0, 1]")
    submission = sample_df.copy()
    submission.loc[:, LABEL_COLUMNS] = values
    return submission
```

- [ ] **Step 4: Run focused and aggregate package checks**

Run:

```bash
uv run pytest tests/test_submission.py -q
uv run ruff check src/knee_mri tests
git diff --check
```

Expected: PASS/clean.

- [ ] **Step 5: Commit and stop for the first Claude implementation review**

```bash
git add src/knee_mri/submission.py tests/test_submission.py
git commit -m "feat(submission): validate competition submission frames"
```

Append a numbered Codex round to `docs/collaboration/active_task.md` listing commits from Tasks 1–5, focused/full test evidence, design deviations (if any), and a concrete Claude request to review the public interfaces, validation preservation, fold determinism, leakage protection, and submission contract. Commit that log entry separately before handoff.

### Task 6: Add Notebook Policy Tests and Refine the EDA Narrative

**Files:**
- Create: `tests/test_notebooks.py`
- Modify: `notebooks/01_eda.ipynb`
- Modify: `notebooks/kernels/eda/kernel-metadata.json`

**Interfaces:**
- Consumes: trusted aggregate values already recorded in `docs/2_eda_insights.md`.
- Produces: an output-free public-facing EDA notebook and reusable JSON policy assertions for all notebooks.

- [ ] **Step 1: Write EDA notebook policy tests**

Load notebook JSON and assert valid Python 3 kernelspec, empty `outputs`, null `execution_count`, no `NOTEBOOK_VERSION`, a functional `IS_KAGGLE`/`raise RuntimeError` guard, and absence of `print(IS_KAGGLE`, `StudyInstanceUID` display calls, report sampling, `.head()` on report-bearing frames, or URLs in code. Assert the EDA metadata title is `RSNA Knee Abnormality Detection — EDA` and `enable_internet` is false.

```python
def test_eda_notebook_is_output_free_and_privacy_safe() -> None:
    notebook = _load_notebook("notebooks/01_eda.ipynb")
    code = _code_source(notebook)
    assert all(not cell.get("outputs", []) for cell in notebook["cells"])
    assert all(cell.get("execution_count") is None for cell in notebook["cells"] if cell["cell_type"] == "code")
    assert "NOTEBOOK_VERSION" not in code
    assert "IS_KAGGLE" in code and "raise RuntimeError" in code
    assert "sample_reports" not in code
    assert "report_text" not in code
```

- [ ] **Step 2: Run the EDA policy test and confirm current violations**

Run: `uv run pytest tests/test_notebooks.py -q`

Expected: FAIL on `NOTEBOOK_VERSION`, raw report sampling, and EDA internet-enabled metadata.

- [ ] **Step 3: Replace the EDA cells with an aggregate-only story**

Use `nbformat` to preserve valid notebook JSON and create this ordered narrative:

1. `# RSNA Knee Abnormality Detection — Exploratory Data Analysis`
2. `## Competition Data Overview`
3. `## Human Labels and Target Prevalence`
4. `## MRI Series Composition`
5. `## Aggregate Report Characteristics`
6. `## Slice-Count Distribution`
7. `## Findings, Limitations, and Modeling Implications`

The setup cell retains only imports, `SEED = 42`, the Kaggle-only guard, data/source discovery, and `sys.path` insertion without printing paths. Replace the report sample with aggregate code:

```python
report_lengths = train_df["Report"].fillna("").str.len()
report_summary = report_lengths.describe(percentiles=[0.25, 0.5, 0.75]).rename("characters")
orthographic_counts = (
    train_df["Report"].fillna("").map(orthographic_bucket).value_counts().rename("studies")
)
display(report_summary.to_frame())
display(orthographic_counts.to_frame())
```

Display only aggregate counts, prevalence, distribution tables, and plots. State that orthographic buckets describe character sets rather than identify languages, that only 58/4,407 studies are human-labeled, and that Phase 3A therefore uses small-sample internal CV rather than claiming an independent validation set. Remove troubleshooting, internal paths, raw report examples, identifiers, and the obsolete PatientSex branch.

- [ ] **Step 4: Disable EDA internet access and normalize notebook state**

Set `"enable_internet": false`, clear every output, and set every code execution count to null. Do not add a copied notebook to the kernel directory; `push_kaggle_kernel.sh` stages it only when pushing.

- [ ] **Step 5: Run policy verification**

Run:

```bash
uv run pytest tests/test_notebooks.py -q
python3 -m json.tool notebooks/01_eda.ipynb >/dev/null
git diff --check
```

Expected: PASS/clean.

- [ ] **Step 6: Commit**

```bash
git add tests/test_notebooks.py notebooks/01_eda.ipynb notebooks/kernels/eda/kernel-metadata.json
git commit -m "docs(notebook): polish aggregate EDA narrative"
```

### Task 7: Refine the Weak-Label Evaluation Narrative

**Files:**
- Modify: `notebooks/02_weak_label_evaluation.ipynb`
- Modify: `tests/test_notebooks.py`

**Interfaces:**
- Consumes: the trusted Phase 2 v2 aggregate results in `docs/4_experiments.md`.
- Produces: an output-free public-facing evaluation notebook whose Markdown states the accepted 0/12 No-go result.

- [ ] **Step 1: Extend notebook policy tests to the weak-label notebook**

Parameterize the generic output/guard/version/privacy checks across `01_eda.ipynb` and `02_weak_label_evaluation.ipynb`. Add assertions that weak-label Markdown contains `0/12`, `No-go`, `58`, and `7.7`, contains no form of `pending`, and code does not display report text, identifiers, or row-level extractor output. Public-facing prose intentionally renders the unlabeled-study count as `4,349` for readability while existing internal docs retain `4349`; keep the test semantic rather than coupling it to punctuation:

```python
markdown = _markdown_source(_load_notebook("notebooks/02_weak_label_evaluation.ipynb"))
assert "4349" in markdown.replace(",", "")
```

- [ ] **Step 2: Run the focused test and confirm stale narrative remains**

Run: `uv run pytest tests/test_notebooks.py -q`

Expected: FAIL because the current notebook contains `NOTEBOOK_VERSION` and “pending” Markdown.

- [ ] **Step 3: Replace stale Markdown with the trusted interpretation**

Keep the established evaluation code and safe aggregate tables, but remove version/path diagnostics and use these sections:

1. `# RSNA Knee Abnormality Detection — Weak-Label Evaluation`
2. `## Frozen Evaluation Contract`
3. `## Naive Keyword Baseline`
4. `## Assertion-Aware Extractor`
5. `## Coverage and Error Taxonomy`
6. `## Labeled-to-Unlabeled Orthographic Comparison`
7. `## Decision and Modeling Implication`

The adjacent Markdown must explain: assertion awareness improves several point precision estimates but no Wilson lower bound/support pair passes; the allowlist is empty (`0/12`, No-go); `no_mention` dominates false negatives observationally without proving language causation; the labeled set has a 7.7 percentage-point ASCII-only gap versus 4,349 unlabeled studies; and Phase 3A uses only the 58 human labels.

- [ ] **Step 4: Normalize and verify the notebook**

Clear outputs/execution counts and run:

```bash
uv run pytest tests/test_notebooks.py -q
python3 -m json.tool notebooks/02_weak_label_evaluation.ipynb >/dev/null
git diff --check
```

Expected: PASS/clean.

- [ ] **Step 5: Commit**

```bash
git add notebooks/02_weak_label_evaluation.ipynb tests/test_notebooks.py
git commit -m "docs(notebook): publish trusted weak-label conclusions"
```

### Task 8: Create the End-to-End Baseline Modeling Notebook

**Files:**
- Create: `notebooks/03_baseline_modeling.ipynb`
- Create: `notebooks/kernels/baseline-modeling/kernel-metadata.json`
- Modify: `tests/test_notebooks.py`

**Interfaces:**
- Consumes: `prepare_modeling_inputs`, `select_multilabel_folds`, report-model functions, `build_submission`, `LABEL_COLUMNS`, and the vendored wheel contract.
- Produces: `/kaggle/working/submission.csv` and safe aggregate OOF/fold/submission summaries in one private CPU kernel.

- [ ] **Step 1: Extend notebook tests for the baseline kernel**

Assert the new notebook exists, is output-free, obeys all generic policy checks, imports every package boundary, verifies the exact wheel filename/SHA/version before importing `iterstrat`, constructs all-0.5 predictions, writes exactly `/kaggle/working/submission.csv`, and contains no URL or alternative model/fold parameters. Validate metadata exactly:

```json
{
  "id": "tuannm3812/rsna-knee-baseline-modeling",
  "title": "RSNA Knee Baseline Modeling",
  "code_file": "03_baseline_modeling.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": false,
  "enable_tpu": false,
  "enable_internet": false,
  "dataset_sources": ["tuannm3812/rsna-knee-mri-src"],
  "competition_sources": ["rsna-knee-abnormality-detection"]
}
```

- [ ] **Step 2: Run the policy test and confirm the notebook is absent**

Run: `uv run pytest tests/test_notebooks.py -q`

Expected: FAIL because `notebooks/03_baseline_modeling.ipynb` and its metadata do not exist.

- [ ] **Step 3: Build the Kaggle-only dependency setup**

Create the notebook with Title Case headings and an initial setup cell that: raises off Kaggle; locates exactly one source root containing the exact wheel; hashes it; installs it with `sys.executable -m pip install --no-index`; verifies `importlib.metadata.version("iterative-stratification") == "0.1.9"`; then adds the located `src` directory to `sys.path`. Suppress successful pip output, check the return code, and ensure every failure message names only the violated rule, not the resolved filesystem path.

```python
wheel_name = "iterative_stratification-0.1.9-py3-none-any.whl"
expected_sha256 = "476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80"
wheel_matches = list(Path("/kaggle/input/datasets").rglob(wheel_name))
if len(wheel_matches) != 1:
    raise RuntimeError("Expected exactly one pinned iterative-stratification wheel")
wheel_path = wheel_matches[0]
if hashlib.sha256(wheel_path.read_bytes()).hexdigest() != expected_sha256:
    raise RuntimeError("Pinned iterative-stratification wheel checksum mismatch")
subprocess.run(
    [sys.executable, "-m", "pip", "install", "--no-index", str(wheel_path)],
    check=True,
    stdout=subprocess.DEVNULL,
)
if importlib.metadata.version("iterative-stratification") != "0.1.9":
    raise RuntimeError("Installed iterative-stratification version mismatch")
```

- [ ] **Step 4: Build the single linear modeling flow**

Use these sections in order:

1. `# RSNA Knee Abnormality Detection — Report Baseline`
2. `## Frozen Experiment Contract`
3. `## Offline Setup and Data Validation`
4. `## Deterministic Multilabel Folds`
5. `## Constant-Probability Sanity Check`
6. `## Fold-Local Out-of-Fold Evaluation`
7. `## Pooled and Per-Label Interpretation`
8. `## Full-Data Refit and Test Prediction`
9. `## Submission Validation and Artifact`
10. `## Limitations and Phase 3B`

The main calls are exactly:

```python
inputs = prepare_modeling_inputs(train_df, test_df, sample_df)
y = inputs.labeled_studies[LABEL_COLUMNS]
selected_folds, folds = select_multilabel_folds(y)
constant_predictions = pd.DataFrame(0.5, index=y.index, columns=LABEL_COLUMNS)
assert macro_auc(y, constant_predictions) == 0.5
cv_result = cross_validate_report_model(inputs.labeled_studies["Report"], y, folds)
vectorizer, classifier = fit_report_model(inputs.labeled_studies["Report"], y)
test_features = vectorizer.transform(inputs.test_studies["Report"])
test_probabilities = classifier.predict_proba(test_features)
submission = build_submission(
    sample_df,
    inputs.test_studies["StudyInstanceUID"],
    test_probabilities,
)
submission.to_csv("/kaggle/working/submission.csv", index=False)
```

Display only aggregate fold sizes/class counts, selected fold count, constant score, pooled/fold AUC tables, vocabulary sizes, missing-test-report count, submission shape, and per-label probability summaries. Initial Markdown explains how each result is interpreted but asserts no Phase 3A result before the trusted run.

- [ ] **Step 5: Normalize and verify notebook JSON**

Run:

```bash
uv run pytest tests/test_notebooks.py -q
python3 -m json.tool notebooks/03_baseline_modeling.ipynb >/dev/null
git diff --check
```

Expected: PASS/clean.

- [ ] **Step 6: Commit**

```bash
git add notebooks/03_baseline_modeling.ipynb notebooks/kernels/baseline-modeling/kernel-metadata.json tests/test_notebooks.py
git commit -m "feat(notebook): add end-to-end report baseline kernel"
```

### Task 9: Synchronize Standards, Status, Strategy, and Historical Plans

**Files:**
- Modify: `docs/0_coding_standards.md`
- Modify: `README.md`
- Modify: `docs/3_strategy.md`
- Modify: `docs/superpowers/plans/2026-08-09-repo-setup.md`
- Modify: `docs/superpowers/plans/2026-08-09-weak-label-evaluation.md`
- Modify: `docs/collaboration/active_task.md`

**Interfaces:**
- Consumes: the approved Phase 3A design and Tasks 1–8 implementation state.
- Produces: one noncontradictory project status and the second Claude review handoff.

- [ ] **Step 1: Update the notebook and submission standards**

Set the canonical sequence to `01_eda.ipynb` → `02_weak_label_evaluation.ipynb` → `03_baseline_modeling.ipynb`. Require Title Case display titles, aggregate-only public content, no internal paths/housekeeping, a retained unprinted Kaggle-only guard, and no `NOTEBOOK_VERSION`. Preserve section 11's kernel-native submission rule.

- [ ] **Step 2: Update current project status**

Replace README “Scaffolding” language with Phase 3A implementation status. In `docs/3_strategy.md`, record Phase 3A report baseline → Phase 3B frozen image embeddings → Phase 3C predefined late fusion, identify the approved design/plan, and keep Phase 3B/3C unstarted.

- [ ] **Step 3: Mark old plans as historical without rewriting their checkbox traces**

Immediately below each old plan title, add a dated status note saying the plan is completed and retained as historical authoring evidence; its unchecked boxes do not represent active work. Do not check or reorder the old task lists.

- [ ] **Step 4: Run the complete local gate**

Run:

```bash
uv run pytest -q
uv run ruff check .
python3 -m json.tool notebooks/01_eda.ipynb >/dev/null
python3 -m json.tool notebooks/02_weak_label_evaluation.ipynb >/dev/null
python3 -m json.tool notebooks/03_baseline_modeling.ipynb >/dev/null
git diff --check
```

Expected: all tests PASS, Ruff clean, all notebooks valid JSON, diff clean.

- [ ] **Step 5: Commit implementation documentation**

```bash
git add README.md docs/0_coding_standards.md docs/3_strategy.md docs/superpowers/plans/2026-08-09-repo-setup.md docs/superpowers/plans/2026-08-09-weak-label-evaluation.md
git commit -m "docs: align project status with Phase 3A baseline"
```

- [ ] **Step 6: Record and commit the second Codex review handoff**

Append a numbered Codex round to the active log with commits from Tasks 6–9, full-gate output, notebook privacy-policy evidence, and a Claude request to inspect every notebook cell/metadata file plus design-to-implementation traceability. Commit only the log entry:

```bash
git add docs/collaboration/active_task.md
git commit -m "docs(collaboration): request Phase 3A notebook review"
```

Stop until Claude records a clean review and the user approves Kaggle execution.

### Task 10: Publish the Private Source Dataset and Run All Three Kernels

**Files:**
- No repository edit before remote verification.
- Modify after trusted execution: `notebooks/03_baseline_modeling.ipynb`
- Modify after trusted execution: `docs/4_experiments.md`

**Interfaces:**
- Consumes: reviewed local commits, private Kaggle credentials, source dataset `tuannm3812/rsna-knee-mri-src`, and three private kernel metadata files.
- Produces: one trusted initial Phase 3A result and proof that every offline kernel completes.

- [ ] **Step 1: Verify clean local state immediately before publishing**

Run:

```bash
git status --short --branch
uv run pytest -q
uv run ruff check .
git diff --check
```

Expected: clean/synchronized intended branch, all tests PASS, Ruff/diff clean.

- [ ] **Step 2: Publish a new private source-dataset version**

Run:

```bash
scripts/publish_code_dataset.sh version "Phase 3A report baseline and offline stratifier"
```

Inspect the Kaggle response and confirm the new dataset version contains `src/knee_mri`, the exact wheel, and its license. Do not alter dataset privacy.

- [ ] **Step 3: Push EDA and weak-label kernels and wait for completion**

Run:

```bash
scripts/push_kaggle_kernel.sh eda
scripts/push_kaggle_kernel.sh weak-label-evaluation
```

Poll each kernel with the Kaggle CLI until `KernelWorkerStatus.COMPLETE`. If either status is ERROR, capture the aggregate error, return to the smallest failing task, add a regression test, and obtain review before republishing.

- [ ] **Step 4: Push the initial baseline kernel and wait for completion**

Run:

```bash
scripts/push_kaggle_kernel.sh baseline-modeling
```

Wait for `KernelWorkerStatus.COMPLETE`, download its output to a temporary directory outside the repository, and inspect only aggregate notebook outputs plus the generated file's schema/shape/range. Do not print rows from `submission.csv`.

- [ ] **Step 5: Transcribe the trusted aggregate result**

Update the notebook's interpretation Markdown and append one dated Phase 3A entry to `docs/4_experiments.md` containing: kernel ID/version, source-dataset version, exact frozen TF-IDF/classifier configuration, selected fold count and fold sizes, constant score `0.5000`, pooled macro AUC, all 12 pooled per-label AUCs, fold macro AUC values/mean/standard deviation, vocabulary sizes, missing-test-report count, and the conclusion that this is internal CV on 58 labels. Copy only values visible in the completed trusted run, rounded to four decimal places for AUCs.

- [ ] **Step 6: Re-run local policy verification and commit trusted results**

Clear outputs and execution counts from the repository notebook after editing Markdown, then run:

```bash
uv run pytest -q
uv run ruff check .
git diff --check
```

Expected: PASS/clean.

```bash
git add notebooks/03_baseline_modeling.ipynb docs/4_experiments.md
git commit -m "docs(experiment): record trusted Phase 3A OOF result"
```

### Task 11: Reproduce the Final Candidate to Four Decimal Places

**Files:**
- Modify only if the rerun matches: `docs/collaboration/active_task.md`

**Interfaces:**
- Consumes: the result-bearing commit from Task 10.
- Produces: an exact completed baseline kernel version eligible for user submission approval.

- [ ] **Step 1: Republish the result-bearing source and push the final candidate**

Publish a new source-dataset version if package/source content changed after the preceding publish, then run `scripts/push_kaggle_kernel.sh baseline-modeling`. Record the returned kernel version and wait for `KernelWorkerStatus.COMPLETE`.

- [ ] **Step 2: Compare the final run against the recorded result**

Confirm the selected fold count matches and every recorded OOF AUC—pooled macro, 12 pooled per-label values, and every fold macro/per-label value—matches after rounding both runs to four decimal places. Also verify `/kaggle/working/submission.csv` exists and passes the schema, ID-order, finiteness, and `[0, 1]` checks. A mismatch returns to diagnosis and Claude review; it is not rounded away beyond four decimals.

- [ ] **Step 3: Record the final Codex review handoff**

Append and commit a numbered Codex round naming the exact kernel ID/version, source-dataset version, completion status, four-decimal comparison result, submission artifact checks, and a request for Claude's final implementation/release review. Do not include report text, identifiers, predictions, or the submission file.

- [ ] **Step 4: Stop for Claude and user approval**

Do not submit. Claude must record no unresolved implementation finding, then the user must explicitly approve the exact kernel ID/version from Step 3.

### Task 12: Submit the Approved Kernel Version and Close Phase 3A

**Files:**
- Modify: `docs/5_submissions.md`
- Modify: `docs/3_strategy.md`
- Move after acceptance: `docs/collaboration/active_task.md` to `docs/collaboration/archive/2026-08-10-phase-3a-report-baseline.md` *(Not what happened — see the header note: archived 2026-08-31 as `2026-08-10-phase-3-baseline-modeling.md`.)*
- Create after acceptance: `docs/collaboration/active_task.md`

**Interfaces:**
- Consumes: explicit user approval of the exact completed kernel ID/version and Claude's clean release review.
- Produces: one kernel-native Kaggle submission record and an archived, accepted Phase 3A collaboration thread.

- [ ] **Step 1: Submit only the approved completed kernel version**

Run:

```bash
printf 'Approved kernel version: '
IFS= read -r kernel_version
case "${kernel_version}" in
  [1-9]|[1-9][0-9]*) ;;
  *) echo "Kernel version must be a positive integer." >&2; exit 1 ;;
esac
scripts/submit_kaggle.sh tuannm3812/rsna-knee-baseline-modeling "${kernel_version}" "Phase 3A frozen report baseline"
```

This `printf` plus `IFS= read -r` prompt works in both Bash and zsh, and the `case` statement exits before the submission script for empty, zero, negative, or nonnumeric input. Enter only the integer explicitly named in the user's approval and re-read it aloud in the execution handoff. Do not upload a separately generated CSV.

- [ ] **Step 2: Verify submission status and score**

Use the Kaggle submissions API/CLI to confirm the recorded submission references the approved kernel version. Wait for completion and capture date, message, status, and public/private score fields exactly as returned.

- [ ] **Step 3: Append the real submission record**

Add one entry to `docs/5_submissions.md` containing competition, UTC date/time, kernel ID/version, message, source commit/dataset version, status, scores, and a link-free note that the artifact came from the completed kernel. Update `docs/3_strategy.md` to mark Phase 3A complete and Phase 3B as the next design task.

- [ ] **Step 4: Run the final verification gate**

Run:

```bash
uv run pytest -q
uv run ruff check .
git diff --check
git status --short --branch
```

Expected: tests PASS, Ruff/diff clean, and only the intended documentation changes are present.

- [ ] **Step 5: Commit the submission record**

```bash
git add docs/5_submissions.md docs/3_strategy.md
git commit -m "docs(submission): record Phase 3A kernel submission"
```

- [ ] **Step 6: Archive only after Claude acceptance**

After Claude records a clean final review and the user accepts Phase 3A, move the entire collaboration log to `docs/collaboration/archive/2026-08-10-phase-3a-report-baseline.md`. Create a fresh active log naming Phase 3B as unapproved design work, commit both, and leave all Kaggle assets private. *(Not what happened — see the header note: archived 2026-08-31 as `2026-08-10-phase-3-baseline-modeling.md`.)*
