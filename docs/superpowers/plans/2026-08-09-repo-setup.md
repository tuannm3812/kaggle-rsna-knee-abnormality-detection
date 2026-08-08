# RSNA Knee Abnormality Detection — Repo Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold `kaggle-rsna-knee-abnormality-detection` from an empty repo into a Kaggle-only-execution project: tooling, docs, a tested `src/knee_mri` package, a stub EDA notebook, and Kaggle CLI push/publish/submit scripts.

**Architecture:** All data access, training, and inference happen on Kaggle Kernels via the Kaggle CLI — the 569.76 GB dataset is never downloaded locally. Reused logic (DICOM series loading, report weak-label mining, study-level dataset assembly, the macro-AUC metric) lives in a `src/knee_mri` package tested locally against small synthetic fixtures, then published to Kaggle as a private code-dataset that kernels attach via `dataset_sources`.

**Tech Stack:** Python 3.11+, `uv` + `pyproject.toml` (hatchling backend), `pandas`, `numpy`, `scikit-learn`, `pydicom` (pinned `<3.0`), `pytest`, `ruff`, Kaggle CLI (`kaggle` Python package).

## Global Constraints

- Kaggle-only execution: no code here runs against real competition data locally; `tests/` uses only small synthetic fixtures.
- Package name: `knee_mri` (project name `knee-mri`, normalizes to the same via hatchling).
- `LABEL_COLUMNS` (defined once, in `knee_mri.labels`) must match `sample_submission.csv`'s header exactly and in order: `ACL, MCL, Medial Meniscus, Lateral Meniscus, Medial OA, Lateral OA, PF OA, Effusion, Synovitis, Baker's, Contusion, Fracture`.
- Competition slug: `rsna-knee-abnormality-detection`. Kaggle username: `tuannm3812` (credentials already at `~/.kaggle/kaggle.json`).
- `src/knee_mri` code-dataset slug: `tuannm3812/rsna-knee-mri-src`.
- `pydicom` pinned `>=2.4,<3.0` — its 3.0 release renames `Dataset.save_as`'s `write_like_original` kwarg, and Task 6's synthetic-DICOM test fixture depends on the 2.x signature.
- Kernels and datasets are `is_private: true` (live, prize-money competition).
- Python style: PEP 8, 4-space indent, type hints + Google-style docstrings on everything in `src/`, import groups stdlib → third-party → local.

---

### Task 1: Project scaffolding & tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `dataset-metadata.json`
- Create: `src/knee_mri/__init__.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: an importable `knee_mri` package (`knee_mri.__version__ == "0.1.0"`), a working `uv` environment (`dev` extra installed), and `uv.lock`. All later tasks run `uv run pytest` / `uv run ruff check .` against this environment.

- [ ] **Step 1: Create the directory skeleton**

```bash
mkdir -p src/knee_mri tests notebooks/kernels/eda docs scripts
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.metadata]
allow-direct-references = true

[tool.hatch.build.targets.wheel]
packages = ["src/knee_mri"]

[project]
name = "knee-mri"
version = "0.1.0"
description = "Personal entry for the Kaggle RSNA Knee Abnormality Detection competition"
readme = "README.md"
requires-python = ">=3.11,<3.14"
license = "MIT"
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "scikit-learn>=1.4",
    "pydicom>=2.4,<3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.4.2",
    "ruff>=0.8",
]
notebook = [
    "jupyterlab>=4.0",
    "ipykernel>=6.29",
    "matplotlib>=3.9",
    "seaborn>=0.13",
]
kaggle = [
    "kaggle>=1.6",
]
dicom-extra = [
    "pylibjpeg>=2.0",
    "pylibjpeg-libjpeg>=2.1",
    "pylibjpeg-openjpeg>=2.0",
]
torch = [
    "torch>=2.9.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
src = ["src"]
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "C4", "B", "A001", "RUF", "TID"]

[tool.ruff.format]
docstring-code-format = true
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.mypy_cache/
.ipynb_checkpoints/

.venv/
venv/
env/

*.pt
*.pth
*.ckpt
*.onnx
*.h5
*.npy
*.npz
*.dcm

.env
kaggle.json

data/
predictions/
scratch/
outputs/
models/

notebooks/kernels/*/*.ipynb

submission.csv
```

- [ ] **Step 4: Write `dataset-metadata.json`**

```json
{
  "title": "rsna-knee-mri-src",
  "id": "tuannm3812/rsna-knee-mri-src",
  "licenses": [{"name": "MIT"}]
}
```

- [ ] **Step 5: Write `src/knee_mri/__init__.py`**

```python
"""Knee MRI multi-label abnormality detection package."""

__version__ = "0.1.0"
```

- [ ] **Step 6: Write `tests/__init__.py`**

```python
```

(Empty file — makes `tests/` an importable package for consistent test discovery.)

- [ ] **Step 7: Sync the environment**

Run: `uv sync --extra dev`
Expected: completes without error; creates/updates `.venv/` and `uv.lock`.

- [ ] **Step 8: Verify the package imports**

Run: `uv run python -c "import knee_mri; print(knee_mri.__version__)"`
Expected: prints `0.1.0`

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .gitignore dataset-metadata.json src/knee_mri/__init__.py tests/__init__.py uv.lock
git commit -m "chore: scaffold uv project structure for knee_mri package"
```

---

### Task 2: Core docs — coding standards and competition instructions

**Files:**
- Create: `docs/0_coding_standards.md`
- Create: `docs/1_instructions.md`

**Interfaces:**
- Produces: the project-specific override doc and the competition spec doc that `README.md` (Task 10) links to.

- [ ] **Step 1: Write `docs/0_coding_standards.md`**

```markdown
# Coding Standards

## Baseline

This project follows the shared `coding-standards/coding_standards.md` at
the GitHub root (`/Users/tuannm3812/Documents/GitHub/coding-standards`) as
its baseline. That file is the fallback for anything not overridden below —
commit message convention, pre-commit/pre-push workflow, documentation
style, and Kaggle submission preference all live there. Everything in this
doc is either a project-specific addition or an explicit override of the
shared baseline.

## Repository Scope

Kaggle-only execution, same shape as `kaggle-biohub-cell-tracking-during-
development`: the dataset (569.76 GB) is never downloaded locally, and no
code here is expected to run against real data outside a Kaggle Kernel.

- `notebooks/` — `01_eda.ipynb`, plus `notebooks/kernels/<name>/` holding
  each notebook's Kaggle `kernel-metadata.json`.
- `docs/` — durable findings and decisions.
- `src/knee_mri/` — tested, locally-verifiable package: DICOM series
  loading, report-based weak-label mining, study-level dataset assembly,
  and the macro-AUC evaluation metric. Written from scratch — unlike
  biohub, this competition has no official baseline repo to vendor.
  Covered by `tests/` against small synthetic fixtures (`pydicom`-written
  series, synthetic report strings), so it's verified without needing a
  Kaggle session or real data.
- `scripts/` — `push_kaggle_kernel.sh <name>`, `publish_code_dataset.sh
  <create|version>`, `submit_kaggle.sh`.

No local `data/`, `predictions/`, or `scratch/` — the dataset is ~6.5x
biohub's, so there's nothing to usefully keep in a local `data/` folder.

## Document Naming

- `0_coding_standards.md` — this file.
- `1_instructions.md` — competition task, data format, metric, submission
  method, deadlines.
- `2_eda_insights.md` — real findings from `01_eda.ipynb`'s first trusted
  Kaggle run.
- `3_strategy.md` — competitive-landscape synthesis and the prioritized
  next-experiment roadmap.
- `4_experiments.md` — every local/Kaggle validation run, submitted or
  not, with config/score/conclusion. Append-only.
- `5_submissions.md` — every real Kaggle submission — the ground-truth
  progress record. Append-only.
- `6_kaggle_troubleshooting.md` — reusable diagnosis for Kaggle CLI/API
  friction. Append-only.

Notebook naming: `01_eda.ipynb`, `02_baseline_modeling.ipynb`, ... —
zero-padded, matching the sibling repos. Prefer a new config flag inside
an existing notebook for a new experiment variant over a new notebook
file; only split out a new numbered notebook once the current one becomes
too large/slow to run as a single kernel.

## Python Style

- Follow PEP 8: 4-space indentation, group imports stdlib → third-party →
  local with a blank line between groups.
- Type hints and Google-style docstrings for everything in `src/`.
- `LABEL_COLUMNS` in `src/knee_mri/labels.py` is the single source of
  truth for the 12 target names and their order (must match
  `sample_submission.csv`'s header exactly) — import it, never
  re-type the list.

## Notebook Style

Each notebook should include:

- Purpose statement.
- Configuration cell near the top, with an `IS_KAGGLE` check resolving
  `/kaggle/input/competitions/rsna-knee-abnormality-detection/` for Kaggle
  execution vs. local development, a deterministic seed, and a
  `NOTEBOOK_VERSION` string printed by the first code cell.
- Markdown insight cells after every important plot or metric.
- Numbered sections with clear reader-facing headers.

**Outputs policy:** clear outputs before committing if the notebook code
changed and hasn't been rerun on Kaggle yet.
**Offline-safety:** submission notebooks must declare every dependency
explicitly and run with internet disabled — this is a Code Competition.

## Plot Style

Use `viridis` as the default colormap, matching the shared baseline.

## Data & Compute

- The competition dataset is ~569.76 GB — never download it wholesale.
  Kaggle auto-mounts it at `/kaggle/input/competitions/rsna-knee-
  abnormality-detection/` inside a kernel.
- Kaggle CLI auth: `~/.kaggle/kaggle.json` locally (already set up, user
  `tuannm3812`), picked up automatically by `uv run kaggle ...` — never
  paste its contents anywhere.
- GPU kernels for training/inference; CPU is enough for EDA. Both are
  capped at 9h runtime for the actual competition submission per the
  Code Requirements (see `1_instructions.md`).

## Git Hygiene

Do not commit raw Kaggle data, model weights/checkpoints, prediction
arrays, local credentials, notebook checkpoints, or the staged notebook
copies under `notebooks/kernels/*/*.ipynb` (regenerated by
`push_kaggle_kernel.sh`, gitignored).

## Pushing Notebooks To Kaggle

Each notebook's Kaggle kernel has its own `kernel-metadata.json` under
`notebooks/kernels/<name>/`. The notebook under `notebooks/` is the single
source of truth; the `.ipynb` copy inside `notebooks/kernels/<name>/` is
gitignored and regenerated on every push.

Push with `scripts/push_kaggle_kernel.sh <name>` rather than running
`kaggle kernels push` directly — it copies the current notebook into the
right kernel folder first, so the two never drift.

`src/knee_mri` is not on PyPI, so any kernel that imports it must declare
`"tuannm3812/rsna-knee-mri-src"` in `dataset_sources` (see
`dataset-metadata.json`). Publish/refresh that dataset with
`scripts/publish_code_dataset.sh <create|version "message">` — **not** a
plain `kaggle datasets create/version -p .` from the repo root, which
biohub confirmed does not honor `.kaggleignore` for directory uploads and
can upload `.venv/`/`.git/` by accident. The script stages only `src/`,
`README.md`, `pyproject.toml`, and `dataset-metadata.json` in a clean temp
directory first.

Submit with `scripts/submit_kaggle.sh`, which wraps
`api.competition_submit_code(...)` against a completed kernel version —
see the shared standard's §11 and `docs/1_instructions.md` for why this
needs the Python `kaggle` package rather than a raw CLI subcommand.

Kernels are `is_private: true` — this is a live, prize-money competition.
```

- [ ] **Step 2: Write `docs/1_instructions.md`**

```markdown
# Competition Instructions

[RSNA Knee Abnormality Detection](https://www.kaggle.com/competitions/rsna-knee-abnormality-detection)
— started 2026-07-30, entry/team-merger deadline **2026-10-15 23:59 UTC**,
final submission deadline **2026-10-22 23:59 UTC**, winners' requirements
**2026-11-05**. Prize pool: 10 main-leaderboard prizes ($5,000-$9,000) plus
a 3-prize Efficiency Track ($5,000-$7,000).

## The task

Predict, per study, the probability of 12 clinically important knee MRI
findings:

```
ACL, MCL, Medial Meniscus, Lateral Meniscus, Medial OA, Lateral OA, PF OA,
Effusion, Synovitis, Baker's, Contusion, Fracture
```

Multimodal: every study pairs a set of MRI series (DICOM) with the
original free-text radiology report.

## Data

- **`train.csv`** — one row per study: `StudyInstanceUID`, `PatientSex`
  (Male/Female, may be blank), `Report` (free text, multilingual), and the
  12 binary labels. **Only a small subset of training studies carry
  labels** — the rest have only `Report`, from which weak labels may be
  derived.
- **`train_series.csv`** — one row per series: `StudyInstanceUID`,
  `SeriesInstanceUID`, `Fluid_Sensitive` (1 if T2/PD/STIR-like),
  `Fat_Suppression`, `Anatomical_Plane` (Sagittal/Coronal/Axial).
- **`train_series/<StudyInstanceUID>/<SeriesInstanceUID>/<SOPInstanceUID>.dcm`**
  — one DICOM per slice. 20-45 slices/series typically (median 30), long
  tail to a few hundred. Mixed transfer syntaxes: uncompressed Explicit VR
  Little Endian, JPEG Lossless, JPEG 2000, Implicit VR Little Endian.
  Stripped to an allowlisted set of 86 metadata tags.
- **`test.csv` / `test_series.csv` / `test_series/`** — same schema; the
  local copies are 3 example studies only. Real scoring test set is
  ~1300 studies.
- **`sample_submission.csv`** — all label columns set to 0.5.
- **Size**: 569.76 GB total. Class prevalence is not guaranteed consistent
  across train / public LB / private LB.

## Evaluation metric

Macro-averaged AUC-ROC across the 12 target columns — the mean of the
per-column ROC-AUC, unweighted. Implemented in
`src/knee_mri/metrics.py::macro_auc`.

## Submission format

```
StudyInstanceUID,ACL,MCL,Medial Meniscus,Lateral Meniscus,Medial OA,Lateral OA,PF OA,Effusion,Synovitis,Baker's,Contusion,Fracture
<uid_1>,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5
```

One row per test study, header exactly as above (this is
`LABEL_COLUMNS`'s canonical order in `src/knee_mri/labels.py`).

## Submission method — Code Competition (notebook rerun)

Matches the shared standard's §11 (notebook-based submission). Submit via
`scripts/submit_kaggle.sh`, which wraps `api.competition_submit_code(...)`
— see `docs/0_coding_standards.md` "Pushing Notebooks To Kaggle".

**Code Requirements** (from the competition page):
- CPU or GPU notebook, <=9h runtime.
- Internet access disabled during the scored run.
- Freely & publicly available external data/pretrained models allowed.
- Output file must be named `submission.csv`.

## Efficiency Track

A separate prize track scores eligible submissions (ranked above
`sample_submission.csv` on the private LB) on an efficiency score that
combines leaderboard AUC against the best submission's AUC and wall-clock
scoring runtime. Relevant to inference-cost tradeoffs once a working
pipeline exists — not to initial EDA/scaffolding.

## Links

- Competition: https://www.kaggle.com/competitions/rsna-knee-abnormality-detection
```

- [ ] **Step 3: Commit**

```bash
git add docs/0_coding_standards.md docs/1_instructions.md
git commit -m "docs: add coding standards and competition instructions"
```

---

### Task 3: Stub docs (EDA, strategy, experiments, submissions, troubleshooting)

**Files:**
- Create: `docs/2_eda_insights.md`
- Create: `docs/3_strategy.md`
- Create: `docs/4_experiments.md`
- Create: `docs/5_submissions.md`
- Create: `docs/6_kaggle_troubleshooting.md`

**Interfaces:**
- Produces: the remaining doc-table targets `README.md` (Task 10) links to. No code interface — these are append-only logs populated by future work, not this scaffolding pass.

- [ ] **Step 1: Write `docs/2_eda_insights.md`**

```markdown
# EDA Insights

Populated after `01_eda.ipynb`'s first trusted Kaggle run. No run has
happened yet as of this scaffold (2026-08-09).
```

- [ ] **Step 2: Write `docs/3_strategy.md`**

```markdown
# Strategy

Competitive-landscape synthesis and the prioritized next-experiment
roadmap. Empty until `2_eda_insights.md` has real findings to build on.
```

- [ ] **Step 3: Write `docs/4_experiments.md`**

```markdown
# Experiments

Append-only log: every local/Kaggle validation run, submitted or not, one
entry per experiment (config, score, conclusion). Empty until the first
baseline notebook exists.
```

- [ ] **Step 4: Write `docs/5_submissions.md`**

```markdown
# Submissions

Append-only log: every real Kaggle submission — the ground-truth
leaderboard record. Empty until the first submission is made.
```

- [ ] **Step 5: Write `docs/6_kaggle_troubleshooting.md`**

```markdown
# Kaggle Troubleshooting

Append-only log: reusable diagnosis for Kaggle CLI/API friction (auth,
kernel push quirks, offline-install pitfalls, submission mechanics).
Empty until an issue is hit.
```

- [ ] **Step 6: Commit**

```bash
git add docs/2_eda_insights.md docs/3_strategy.md docs/4_experiments.md docs/5_submissions.md docs/6_kaggle_troubleshooting.md
git commit -m "docs: add stub logs for EDA, strategy, experiments, submissions, troubleshooting"
```

---

### Task 4: `knee_mri.labels` — label schema and report weak-label mining

**Files:**
- Create: `src/knee_mri/labels.py`
- Test: `tests/test_labels.py`

**Interfaces:**
- Produces: `LABEL_COLUMNS: list[str]` and `extract_weak_labels(report_text: str) -> dict[str, int]` in `knee_mri.labels`. Consumed by Tasks 5, 7, and 8.

- [ ] **Step 1: Write the failing test**

Create `tests/test_labels.py`:

```python
from knee_mri.labels import LABEL_COLUMNS, extract_weak_labels


def test_label_columns_matches_submission_header():
    assert LABEL_COLUMNS == [
        "ACL",
        "MCL",
        "Medial Meniscus",
        "Lateral Meniscus",
        "Medial OA",
        "Lateral OA",
        "PF OA",
        "Effusion",
        "Synovitis",
        "Baker's",
        "Contusion",
        "Fracture",
    ]


def test_extract_weak_labels_detects_multiple_findings():
    report = (
        "There is a complete tear of the ACL. Moderate joint effusion is "
        "present. Medial meniscus appears intact. No fracture."
    )

    labels = extract_weak_labels(report)

    assert labels["ACL"] == 1
    assert labels["Effusion"] == 1
    assert labels["Medial Meniscus"] == 0
    assert labels["Fracture"] == 1  # regex has no negation handling yet


def test_extract_weak_labels_returns_all_columns_even_with_no_matches():
    labels = extract_weak_labels("Normal knee MRI, no significant findings.")

    assert set(labels.keys()) == set(LABEL_COLUMNS)
    assert all(value in (0, 1) for value in labels.values())
    assert sum(labels.values()) == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_labels.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knee_mri.labels'`

- [ ] **Step 3: Write `src/knee_mri/labels.py`**

```python
"""Report-derived weak labels and the canonical 12-target label schema."""

from __future__ import annotations

import re

LABEL_COLUMNS: list[str] = [
    "ACL",
    "MCL",
    "Medial Meniscus",
    "Lateral Meniscus",
    "Medial OA",
    "Lateral OA",
    "PF OA",
    "Effusion",
    "Synovitis",
    "Baker's",
    "Contusion",
    "Fracture",
]

# One or more regex patterns per label; a match anywhere in the report
# (case-insensitive) counts as a positive weak label for that column.
_LABEL_PATTERNS: dict[str, list[str]] = {
    "ACL": [r"\bacl\b", r"anterior cruciate ligament"],
    "MCL": [r"\bmcl\b", r"medial collateral ligament"],
    "Medial Meniscus": [r"medial meniscus"],
    "Lateral Meniscus": [r"lateral meniscus"],
    "Medial OA": [r"medial.{0,20}(osteoarthritis|compartment.{0,10}oa)"],
    "Lateral OA": [r"lateral.{0,20}(osteoarthritis|compartment.{0,10}oa)"],
    "PF OA": [r"patellofemoral.{0,20}(osteoarthritis|oa)", r"\bpf oa\b"],
    "Effusion": [r"effusion"],
    "Synovitis": [r"synovitis"],
    "Baker's": [r"baker'?s? cyst", r"popliteal cyst"],
    "Contusion": [r"contusion", r"bone bruise"],
    "Fracture": [r"fracture"],
}

_COMPILED_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    label: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for label, patterns in _LABEL_PATTERNS.items()
}


def extract_weak_labels(report_text: str) -> dict[str, int]:
    """Derive weak per-label findings from a free-text radiology report.

    Keyword/regex matching only — a starting point for studies that lack
    a human-annotated label, not a replacement for the annotated subset.
    Case-insensitive; does not attempt negation detection (e.g. "no
    evidence of fracture" still matches "Fracture") — a known limitation
    to refine once real report text has been inspected (see
    docs/3_strategy.md).

    Args:
        report_text: The study's free-text radiology report.

    Returns:
        A dict mapping each of the 12 `LABEL_COLUMNS` to 0 or 1.
    """
    return {
        label: int(any(pattern.search(report_text) for pattern in patterns))
        for label, patterns in _COMPILED_PATTERNS.items()
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_labels.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/knee_mri/labels.py tests/test_labels.py
git commit -m "feat: add label schema and report-based weak-label extraction"
```

---

### Task 5: `knee_mri.metrics` — macro-averaged AUC-ROC

**Files:**
- Create: `src/knee_mri/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `LABEL_COLUMNS` from `knee_mri.labels` (Task 4).
- Produces: `per_label_auc(y_true: pd.DataFrame, y_pred: pd.DataFrame) -> dict[str, float]` and `macro_auc(y_true: pd.DataFrame, y_pred: pd.DataFrame) -> float` in `knee_mri.metrics`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_metrics.py`:

```python
import pandas as pd
import pytest

from knee_mri.labels import LABEL_COLUMNS
from knee_mri.metrics import macro_auc, per_label_auc


def _constant_frame(value: float) -> pd.DataFrame:
    return pd.DataFrame({label: [value] * 4 for label in LABEL_COLUMNS})


def test_macro_auc_is_one_for_perfect_predictions():
    y_true = pd.DataFrame({label: [0, 0, 1, 1] for label in LABEL_COLUMNS})
    y_pred = pd.DataFrame(
        {label: [0.1, 0.2, 0.8, 0.9] for label in LABEL_COLUMNS}
    )

    assert macro_auc(y_true, y_pred) == pytest.approx(1.0)


def test_macro_auc_is_half_for_random_predictions_tied_at_midpoint():
    y_true = pd.DataFrame({label: [0, 0, 1, 1] for label in LABEL_COLUMNS})
    y_pred = _constant_frame(0.5)

    assert macro_auc(y_true, y_pred) == pytest.approx(0.5)


def test_per_label_auc_returns_one_score_per_label_column():
    y_true = pd.DataFrame({label: [0, 1, 0, 1] for label in LABEL_COLUMNS})
    y_pred = pd.DataFrame(
        {label: [0.2, 0.7, 0.3, 0.6] for label in LABEL_COLUMNS}
    )

    scores = per_label_auc(y_true, y_pred)

    assert set(scores.keys()) == set(LABEL_COLUMNS)
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_macro_auc_raises_on_single_class_column():
    y_true = pd.DataFrame({label: [0, 0, 0, 0] for label in LABEL_COLUMNS})
    y_pred = _constant_frame(0.5)

    with pytest.raises(ValueError, match="only one class"):
        macro_auc(y_true, y_pred)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knee_mri.metrics'`

- [ ] **Step 3: Write `src/knee_mri/metrics.py`**

```python
"""Competition scoring metric: macro-averaged AUC-ROC across the 12 labels."""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import roc_auc_score

from knee_mri.labels import LABEL_COLUMNS


def per_label_auc(y_true: pd.DataFrame, y_pred: pd.DataFrame) -> dict[str, float]:
    """Compute ROC-AUC independently for each of the 12 target columns.

    Args:
        y_true: Ground-truth binary labels, one column per `LABEL_COLUMNS`
            entry, one row per study.
        y_pred: Predicted probabilities, same shape/columns as `y_true`.

    Returns:
        A dict mapping each label column to its ROC-AUC score.

    Raises:
        ValueError: If a label column has only one class present in
            `y_true` (ROC-AUC is undefined in that case).
    """
    scores: dict[str, float] = {}
    for label in LABEL_COLUMNS:
        if y_true[label].nunique() < 2:
            raise ValueError(
                f"Cannot compute ROC-AUC for '{label}': only one class "
                "present in y_true."
            )
        scores[label] = roc_auc_score(y_true[label], y_pred[label])
    return scores


def macro_auc(y_true: pd.DataFrame, y_pred: pd.DataFrame) -> float:
    """Compute the competition metric: the unweighted mean of per-label ROC-AUC.

    Args:
        y_true: Ground-truth binary labels, one column per `LABEL_COLUMNS`
            entry, one row per study.
        y_pred: Predicted probabilities, same shape/columns as `y_true`.

    Returns:
        The macro-averaged ROC-AUC across the 12 target columns.
    """
    scores = per_label_auc(y_true, y_pred)
    return sum(scores.values()) / len(scores)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/knee_mri/metrics.py tests/test_metrics.py
git commit -m "feat: add macro-averaged AUC-ROC competition metric"
```

---

### Task 6: `knee_mri.dicom_io` — DICOM series loading

**Files:**
- Create: `src/knee_mri/dicom_io.py`
- Test: `tests/test_dicom_io.py`

**Interfaces:**
- Produces: `SeriesVolume` (dataclass with `pixel_array: np.ndarray`, `instance_numbers: list[int]`) and `load_series(series_dir: Path) -> SeriesVolume` in `knee_mri.dicom_io`. Not consumed by other tasks in this plan (used directly by future EDA/training notebooks).

- [ ] **Step 1: Write the failing test**

Create `tests/test_dicom_io.py`:

```python
from pathlib import Path

import numpy as np
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from knee_mri.dicom_io import load_series


def _write_synthetic_slice(path: Path, instance_number: int, fill_value: int) -> None:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = generate_uid()
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.InstanceNumber = instance_number
    ds.Rows = 4
    ds.Columns = 4
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0

    pixels = np.full((4, 4), fill_value, dtype=np.uint16)
    ds.PixelData = pixels.tobytes()

    ds.save_as(str(path), write_like_original=False)


def test_load_series_stacks_slices_in_instance_number_order(tmp_path: Path):
    series_dir = tmp_path / "series_1"
    series_dir.mkdir()
    # Written out of InstanceNumber order to prove sorting, not filesystem
    # order, controls the stack.
    _write_synthetic_slice(series_dir / "b.dcm", instance_number=2, fill_value=20)
    _write_synthetic_slice(series_dir / "a.dcm", instance_number=1, fill_value=10)
    _write_synthetic_slice(series_dir / "c.dcm", instance_number=3, fill_value=30)

    volume = load_series(series_dir)

    assert volume.pixel_array.shape == (3, 4, 4)
    assert volume.instance_numbers == [1, 2, 3]
    assert (volume.pixel_array[0] == 10).all()
    assert (volume.pixel_array[1] == 20).all()
    assert (volume.pixel_array[2] == 30).all()


def test_load_series_raises_on_empty_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty_series"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="No .dcm files"):
        load_series(empty_dir)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_dicom_io.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knee_mri.dicom_io'`

- [ ] **Step 3: Write `src/knee_mri/dicom_io.py`**

```python
"""DICOM series loading: decode all slices in a series directory into a
stacked volume, sorted by InstanceNumber."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pydicom


@dataclass
class SeriesVolume:
    """A decoded DICOM series: stacked pixel data plus its slice order."""

    pixel_array: np.ndarray  # shape (num_slices, rows, cols)
    instance_numbers: list[int]


def load_series(series_dir: Path) -> SeriesVolume:
    """Load every `.dcm` file in `series_dir` into a single stacked volume.

    Slices are sorted by `InstanceNumber` so the stack order matches
    acquisition order regardless of filesystem listing order. Relies on
    `pydicom`'s pixel data handlers (with the `dicom-extra` optional
    dependency group installed) to decode all four transfer syntaxes the
    competition data uses: uncompressed Explicit VR Little Endian, JPEG
    Lossless, JPEG 2000, and Implicit VR Little Endian.

    Args:
        series_dir: Directory containing one series' `.dcm` slice files.

    Returns:
        A `SeriesVolume` with slices stacked along axis 0 in acquisition
        order.

    Raises:
        FileNotFoundError: If `series_dir` contains no `.dcm` files.
    """
    dcm_paths = sorted(series_dir.glob("*.dcm"))
    if not dcm_paths:
        raise FileNotFoundError(f"No .dcm files found in {series_dir}")

    datasets = [pydicom.dcmread(path) for path in dcm_paths]
    datasets.sort(key=lambda ds: int(ds.InstanceNumber))

    pixel_array = np.stack([ds.pixel_array for ds in datasets], axis=0)
    instance_numbers = [int(ds.InstanceNumber) for ds in datasets]

    return SeriesVolume(pixel_array=pixel_array, instance_numbers=instance_numbers)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_dicom_io.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/knee_mri/dicom_io.py tests/test_dicom_io.py
git commit -m "feat: add DICOM series loading with instance-number ordering"
```

---

### Task 7: `knee_mri.dataset` — series selection and label-completeness split

**Files:**
- Create: `src/knee_mri/dataset.py`
- Test: `tests/test_dataset.py`

**Interfaces:**
- Consumes: `LABEL_COLUMNS` from `knee_mri.labels` (Task 4).
- Produces: `series_for_study(series_df, study_id) -> pd.DataFrame`, `select_primary_series(series_df, study_id, plane="Sagittal", prefer_fluid_sensitive=True) -> str | None`, `split_labeled_studies(train_df) -> tuple[pd.DataFrame, pd.DataFrame]` in `knee_mri.dataset`. Consumed by Task 8's notebook.

- [ ] **Step 1: Write the failing test**

Create `tests/test_dataset.py`:

```python
import numpy as np
import pandas as pd

from knee_mri.dataset import select_primary_series, series_for_study, split_labeled_studies
from knee_mri.labels import LABEL_COLUMNS


def _series_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_1a",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_1b",
                "Fluid_Sensitive": 1,
                "Fat_Suppression": 1,
                "Anatomical_Plane": "Sagittal",
            },
            {
                "StudyInstanceUID": "study_1",
                "SeriesInstanceUID": "series_1c",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Axial",
            },
            {
                "StudyInstanceUID": "study_2",
                "SeriesInstanceUID": "series_2a",
                "Fluid_Sensitive": 0,
                "Fat_Suppression": 0,
                "Anatomical_Plane": "Coronal",
            },
        ]
    )


def test_series_for_study_filters_to_one_study():
    result = series_for_study(_series_frame(), "study_1")

    assert set(result["SeriesInstanceUID"]) == {"series_1a", "series_1b", "series_1c"}


def test_select_primary_series_prefers_fluid_sensitive_within_plane():
    chosen = select_primary_series(_series_frame(), "study_1", plane="Sagittal")

    assert chosen == "series_1b"


def test_select_primary_series_returns_none_when_plane_missing():
    chosen = select_primary_series(_series_frame(), "study_2", plane="Sagittal")

    assert chosen is None


def test_split_labeled_studies_separates_missing_labels():
    rows = []
    for i in range(3):
        row = {"StudyInstanceUID": f"labeled_{i}", "PatientSex": "Female", "Report": "text"}
        row.update({label: 0 for label in LABEL_COLUMNS})
        rows.append(row)
    for i in range(2):
        row = {"StudyInstanceUID": f"unlabeled_{i}", "PatientSex": "Male", "Report": "text"}
        row.update({label: np.nan for label in LABEL_COLUMNS})
        rows.append(row)
    train_df = pd.DataFrame(rows)

    labeled, unlabeled = split_labeled_studies(train_df)

    assert len(labeled) == 3
    assert len(unlabeled) == 2
    assert set(labeled["StudyInstanceUID"]) == {"labeled_0", "labeled_1", "labeled_2"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_dataset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knee_mri.dataset'`

- [ ] **Step 3: Write `src/knee_mri/dataset.py`**

```python
"""Study-level series selection and train.csv label-completeness splitting."""

from __future__ import annotations

import pandas as pd

from knee_mri.labels import LABEL_COLUMNS


def series_for_study(series_df: pd.DataFrame, study_id: str) -> pd.DataFrame:
    """Return every series row belonging to one study.

    Args:
        series_df: A `train_series.csv`/`test_series.csv`-shaped frame.
        study_id: The `StudyInstanceUID` to filter to.

    Returns:
        The subset of `series_df` for that study, in its original row order.
    """
    return series_df.loc[series_df["StudyInstanceUID"] == study_id]


def select_primary_series(
    series_df: pd.DataFrame,
    study_id: str,
    plane: str = "Sagittal",
    prefer_fluid_sensitive: bool = True,
) -> str | None:
    """Pick one `SeriesInstanceUID` to represent a study for a given plane.

    Filters to the requested `Anatomical_Plane` first, then (if requested)
    prefers a fluid-sensitive sequence — knee abnormalities like effusion,
    meniscus/ligament tears show up most clearly on fluid-sensitive
    sequences (T2/PD/STIR). Falls back to the first matching series if no
    fluid-sensitive one is present.

    Args:
        series_df: A `train_series.csv`/`test_series.csv`-shaped frame.
        study_id: The `StudyInstanceUID` to select a series for.
        plane: The `Anatomical_Plane` to require (`"Sagittal"`,
            `"Coronal"`, or `"Axial"`).
        prefer_fluid_sensitive: If `True`, prefer a series with
            `Fluid_Sensitive == 1` among the plane-matching candidates.

    Returns:
        The chosen `SeriesInstanceUID`, or `None` if no series for this
        study matches `plane`.
    """
    candidates = series_for_study(series_df, study_id)
    candidates = candidates.loc[candidates["Anatomical_Plane"] == plane]
    if candidates.empty:
        return None

    if prefer_fluid_sensitive:
        fluid_sensitive = candidates.loc[candidates["Fluid_Sensitive"] == 1]
        if not fluid_sensitive.empty:
            candidates = fluid_sensitive

    return str(candidates.iloc[0]["SeriesInstanceUID"])


def split_labeled_studies(
    train_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split `train.csv` into fully-labeled and label-missing studies.

    Args:
        train_df: A `train.csv`-shaped frame containing `LABEL_COLUMNS`.

    Returns:
        A `(labeled, unlabeled)` tuple: `labeled` has no missing values
        across `LABEL_COLUMNS`; `unlabeled` has at least one missing
        label and is a weak-labeling candidate (see
        `knee_mri.labels.extract_weak_labels`).
    """
    has_missing_label = train_df[LABEL_COLUMNS].isna().any(axis=1)
    labeled = train_df.loc[~has_missing_label]
    unlabeled = train_df.loc[has_missing_label]
    return labeled, unlabeled
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_dataset.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/knee_mri/dataset.py tests/test_dataset.py
git commit -m "feat: add study-level series selection and label-completeness split"
```

---

### Task 8: `01_eda.ipynb` stub and its Kaggle kernel metadata

**Files:**
- Create: `notebooks/01_eda.ipynb`
- Create: `notebooks/kernels/eda/kernel-metadata.json`

**Interfaces:**
- Consumes: `knee_mri.labels.LABEL_COLUMNS`, `knee_mri.dataset.split_labeled_studies` (Tasks 4 and 7).
- Produces: the notebook Task 9's `push_kaggle_kernel.sh eda` pushes, and the `code_file`/`id` fields its `kernel-metadata.json` declares.

- [ ] **Step 1: Write `notebooks/01_eda.ipynb`**

```json
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# RSNA Knee Abnormality Detection — EDA\n",
    "\n",
    "First look at `train.csv` and `train_series.csv`: label prevalence, how\n",
    "many studies have human-annotated labels vs. report-only, series-per-study\n",
    "and anatomical-plane/sequence-type distribution, patient sex, report\n",
    "language, and slice counts per series. Runs on Kaggle only — the dataset\n",
    "(569.76 GB) is never downloaded locally; see `docs/1_instructions.md`."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import random\n",
    "import sys\n",
    "from pathlib import Path\n",
    "\n",
    "import numpy as np\n",
    "import pandas as pd\n",
    "\n",
    "NOTEBOOK_VERSION = \"v1\"\n",
    "SEED = 42\n",
    "random.seed(SEED)\n",
    "np.random.seed(SEED)\n",
    "\n",
    "IS_KAGGLE = Path(\"/kaggle/input\").exists()\n",
    "\n",
    "if IS_KAGGLE:\n",
    "    DATA_DIR = Path(\"/kaggle/input/competitions/rsna-knee-abnormality-detection\")\n",
    "    SRC_DATASET_DIR = Path(\"/kaggle/input/rsna-knee-mri-src\")\n",
    "    if SRC_DATASET_DIR.exists():\n",
    "        sys.path.insert(0, str(SRC_DATASET_DIR / \"src\"))\n",
    "else:\n",
    "    DATA_DIR = Path(\"../data\")\n",
    "    sys.path.insert(0, str(Path(\"../src\").resolve()))\n",
    "\n",
    "print(f\"NOTEBOOK_VERSION={NOTEBOOK_VERSION}\")\n",
    "print(f\"IS_KAGGLE={IS_KAGGLE}\")\n",
    "print(f\"DATA_DIR={DATA_DIR}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 1. Load study & series tables"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from knee_mri.labels import LABEL_COLUMNS\n",
    "from knee_mri.dataset import split_labeled_studies\n",
    "\n",
    "train_df = pd.read_csv(DATA_DIR / \"train.csv\")\n",
    "series_df = pd.read_csv(DATA_DIR / \"train_series.csv\")\n",
    "\n",
    "print(train_df.shape, series_df.shape)\n",
    "train_df.head()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 2. Label prevalence and labeled-vs-unlabeled split"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import matplotlib.pyplot as plt\n",
    "\n",
    "labeled, unlabeled = split_labeled_studies(train_df)\n",
    "print(f\"Labeled studies: {len(labeled)}\")\n",
    "print(f\"Unlabeled (report-only) studies: {len(unlabeled)}\")\n",
    "\n",
    "prevalence = labeled[LABEL_COLUMNS].mean().sort_values(ascending=False)\n",
    "\n",
    "fig, ax = plt.subplots(figsize=(8, 5))\n",
    "prevalence.plot(kind=\"barh\", ax=ax, colormap=\"viridis\")\n",
    "ax.set_xlabel(\"Positive rate (labeled studies)\")\n",
    "ax.set_title(\"Label prevalence across the 12 targets\")\n",
    "plt.tight_layout()\n",
    "plt.show()\n",
    "\n",
    "prevalence"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "**Insight:** pending first Kaggle run."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 3. Series per study, anatomical plane, and sequence type"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "series_per_study = series_df.groupby(\"StudyInstanceUID\").size()\n",
    "\n",
    "fig, ax = plt.subplots(figsize=(8, 4))\n",
    "series_per_study.plot(kind=\"hist\", bins=30, ax=ax, colormap=\"viridis\")\n",
    "ax.set_xlabel(\"Series per study\")\n",
    "ax.set_title(\"Distribution of series count per study\")\n",
    "plt.tight_layout()\n",
    "plt.show()\n",
    "\n",
    "print(series_df[\"Anatomical_Plane\"].value_counts())\n",
    "print(series_df[[\"Fluid_Sensitive\", \"Fat_Suppression\"]].mean())"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "**Insight:** pending first Kaggle run."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 4. Patient sex and report language spot-check"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(train_df[\"PatientSex\"].value_counts(dropna=False))\n",
    "\n",
    "sample_reports = train_df[\"Report\"].dropna().sample(5, random_state=SEED)\n",
    "for idx, report in sample_reports.items():\n",
    "    non_ascii_fraction = sum(ord(ch) > 127 for ch in report) / max(len(report), 1)\n",
    "    study_id = train_df.loc[idx, \"StudyInstanceUID\"]\n",
    "    print(f\"--- {study_id} (len={len(report)}, non_ascii_fraction={non_ascii_fraction:.2f}) ---\")\n",
    "    print(report[:300])\n",
    "    print()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "**Insight:** pending first Kaggle run."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 5. Slice count per series"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "train_series_root = DATA_DIR / \"train_series\"\n",
    "\n",
    "slice_counts = []\n",
    "for study_dir in sorted(train_series_root.iterdir())[:200]:  # cap for a fast EDA pass\n",
    "    for series_dir in study_dir.iterdir():\n",
    "        slice_counts.append(len(list(series_dir.glob(\"*.dcm\"))))\n",
    "\n",
    "slice_counts = pd.Series(slice_counts)\n",
    "print(slice_counts.describe())\n",
    "\n",
    "fig, ax = plt.subplots(figsize=(8, 4))\n",
    "slice_counts.plot(kind=\"hist\", bins=30, ax=ax, colormap=\"viridis\")\n",
    "ax.set_xlabel(\"Slices per series\")\n",
    "ax.set_title(\"Distribution of slice count per series (first 200 studies)\")\n",
    "plt.tight_layout()\n",
    "plt.show()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "**Insight:** pending first Kaggle run."
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.11"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
```

- [ ] **Step 2: Verify the notebook JSON is well-formed**

Run: `uv run python -c "import json; json.load(open('notebooks/01_eda.ipynb'))" && echo OK`
Expected: prints `OK`

- [ ] **Step 3: Write `notebooks/kernels/eda/kernel-metadata.json`**

```json
{
  "id": "tuannm3812/rsna-knee-eda",
  "title": "rsna-knee-eda",
  "code_file": "01_eda.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": false,
  "enable_tpu": false,
  "enable_internet": true,
  "dataset_sources": ["tuannm3812/rsna-knee-mri-src"],
  "competition_sources": ["rsna-knee-abnormality-detection"],
  "kernel_sources": []
}
```

- [ ] **Step 4: Commit**

```bash
git add notebooks/01_eda.ipynb notebooks/kernels/eda/kernel-metadata.json
git commit -m "feat: add EDA notebook stub and its Kaggle kernel metadata"
```

---

### Task 9: Kaggle CLI scripts (push, publish, submit)

**Files:**
- Create: `scripts/push_kaggle_kernel.sh`
- Create: `scripts/publish_code_dataset.sh`
- Create: `scripts/submit_kaggle.sh`

**Interfaces:**
- Consumes: `dataset-metadata.json` (Task 1), `notebooks/kernels/<name>/kernel-metadata.json` (Task 8), `pyproject.toml`'s `kaggle` extra (Task 1).
- Produces: no importable interface — these are operator-run CLI entry points referenced by `docs/0_coding_standards.md` and `docs/1_instructions.md`.

- [ ] **Step 1: Write `scripts/push_kaggle_kernel.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <kernel-name>" >&2
  echo "  e.g. $0 eda" >&2
  exit 1
fi

KERNEL_NAME="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KERNEL_DIR="${REPO_ROOT}/notebooks/kernels/${KERNEL_NAME}"

if [[ ! -f "${KERNEL_DIR}/kernel-metadata.json" ]]; then
  echo "No kernel-metadata.json at ${KERNEL_DIR} — create it first." >&2
  exit 1
fi

NOTEBOOK_FILE=$(python3 -c "
import json
with open('${KERNEL_DIR}/kernel-metadata.json') as f:
    print(json.load(f)['code_file'])
")

SOURCE_NOTEBOOK="${REPO_ROOT}/notebooks/${NOTEBOOK_FILE}"
if [[ ! -f "${SOURCE_NOTEBOOK}" ]]; then
  echo "Source notebook not found: ${SOURCE_NOTEBOOK}" >&2
  exit 1
fi

cp "${SOURCE_NOTEBOOK}" "${KERNEL_DIR}/${NOTEBOOK_FILE}"
echo "Copied ${SOURCE_NOTEBOOK} -> ${KERNEL_DIR}/${NOTEBOOK_FILE}"

cd "${KERNEL_DIR}"
uv run --project "${REPO_ROOT}" kaggle kernels push -p .
echo "Pushed kernel ${KERNEL_NAME}."
```

- [ ] **Step 2: Write `scripts/publish_code_dataset.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <create|version> [\"version message\"]" >&2
  exit 1
fi

ACTION="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGE_DIR}"' EXIT

cp -R "${REPO_ROOT}/src" "${STAGE_DIR}/src"
cp "${REPO_ROOT}/pyproject.toml" "${STAGE_DIR}/pyproject.toml"
cp "${REPO_ROOT}/README.md" "${STAGE_DIR}/README.md"
cp "${REPO_ROOT}/dataset-metadata.json" "${STAGE_DIR}/dataset-metadata.json"

find "${STAGE_DIR}/src" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

case "${ACTION}" in
  create)
    uv run --project "${REPO_ROOT}" kaggle datasets create -p "${STAGE_DIR}"
    ;;
  version)
    MESSAGE="${2:-Update src/knee_mri}"
    uv run --project "${REPO_ROOT}" kaggle datasets version -p "${STAGE_DIR}" -d -m "${MESSAGE}"
    ;;
  *)
    echo "Unknown action: ${ACTION} (expected create|version)" >&2
    exit 1
    ;;
esac
```

- [ ] **Step 3: Write `scripts/submit_kaggle.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <kernel-user/kernel-slug> <kernel-version> \"<submission message>\"" >&2
  exit 1
fi

KERNEL="$1"
VERSION="$2"
MESSAGE="$3"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

uv run --project "${REPO_ROOT}" python3 - "$KERNEL" "$VERSION" "$MESSAGE" <<'PYEOF'
import sys

import kaggle

kernel, version, message = sys.argv[1], int(sys.argv[2]), sys.argv[3]

api = kaggle.KaggleApi()
api.authenticate()
api.competition_submit_code(
    file_name="submission.csv",
    message=message,
    competition="rsna-knee-abnormality-detection",
    kernel=kernel,
    kernel_version=version,
)
print(f"Submitted {kernel} v{version}: {message}")
PYEOF
```

- [ ] **Step 4: Make the scripts executable**

Run: `chmod +x scripts/push_kaggle_kernel.sh scripts/publish_code_dataset.sh scripts/submit_kaggle.sh`
Expected: no output, exit code 0

- [ ] **Step 5: Commit**

```bash
git add scripts/push_kaggle_kernel.sh scripts/publish_code_dataset.sh scripts/submit_kaggle.sh
git commit -m "feat: add Kaggle CLI push, publish, and submit scripts"
```

---

### Task 10: README

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: doc links from Tasks 2-3, setup commands from Task 1's `pyproject.toml` extras, layout from Tasks 4-9.

- [ ] **Step 1: Write `README.md`**

```markdown
# RSNA Knee Abnormality Detection

<p align="center">
  <a href="https://www.kaggle.com/competitions/rsna-knee-abnormality-detection"><img alt="Kaggle Competition" src="https://img.shields.io/badge/Kaggle-RSNA%20Knee%20Abnormality%20Detection-20BEFF?logo=kaggle&logoColor=white"></a>
  <a href="pyproject.toml"><img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="docs/0_coding_standards.md"><img alt="Execution" src="https://img.shields.io/badge/Execution-Kaggle--only-orange"></a>
  <img alt="Status" src="https://img.shields.io/badge/Status-Scaffolding-lightgrey">
</p>

Personal entry for the Kaggle competition
[RSNA Knee Abnormality Detection](https://www.kaggle.com/competitions/rsna-knee-abnormality-detection):
predict per-study probabilities for 12 clinically important knee MRI
findings — ACL/MCL/meniscus injuries, three-compartment osteoarthritis,
effusion, synovitis, Baker's cyst, contusion, and fracture — from a
**569.76 GB** multimodal dataset pairing DICOM series with free-text
radiology reports. Scored by macro-averaged AUC-ROC. Full task, data
format, and scoring details: [`docs/1_instructions.md`](docs/1_instructions.md).

## Status

Scaffolding only as of 2026-08-09 — no EDA/baseline Kaggle run yet. See
[`docs/2_eda_insights.md`](docs/2_eda_insights.md) and
[`docs/5_submissions.md`](docs/5_submissions.md) as they fill in.

## Documentation

| Doc | Contents |
|---|---|
| [`0_coding_standards.md`](docs/0_coding_standards.md) | Project conventions and overrides of the personal master standard |
| [`1_instructions.md`](docs/1_instructions.md) | Competition spec, data format, submission method |
| [`2_eda_insights.md`](docs/2_eda_insights.md) | EDA findings once `01_eda.ipynb` has a trusted Kaggle run |
| [`3_strategy.md`](docs/3_strategy.md) | Competitive-landscape analysis and the prioritized roadmap |
| [`4_experiments.md`](docs/4_experiments.md) | Every local/Kaggle validation run |
| [`5_submissions.md`](docs/5_submissions.md) | Every real Kaggle submission |
| [`6_kaggle_troubleshooting.md`](docs/6_kaggle_troubleshooting.md) | Reusable diagnosis for Kaggle CLI/API friction |

## Repository layout

- [`notebooks/`](notebooks/) — `01_eda.ipynb`, plus
  `notebooks/kernels/<name>/` holding each notebook's Kaggle
  `kernel-metadata.json`.
- [`docs/`](docs/) — see the table above.
- [`src/knee_mri/`](src/knee_mri/) — tested DICOM I/O, report weak-label
  mining, study-level dataset assembly, and the macro-AUC metric. Written
  from scratch (no official competition baseline exists), covered by
  `tests/` against small synthetic fixtures.
- [`scripts/`](scripts/) — `push_kaggle_kernel.sh`,
  `publish_code_dataset.sh`, `submit_kaggle.sh`.

## Setup

```bash
uv sync --extra dev --extra notebook --extra kaggle
uv run pytest
uv run ruff check .
```

The competition dataset (569.76 GB) is never downloaded locally —
everything that touches real data runs on Kaggle Kernels via the Kaggle
CLI, where it's already mounted. See
[`docs/0_coding_standards.md`](docs/0_coding_standards.md) for
project-specific conventions.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add project README"
```

---

### Task 11: Final verification

**Files:** none (verification only).

**Interfaces:** none — this task confirms every earlier task's deliverable still works together.

- [ ] **Step 1: Full environment sync**

Run: `uv sync --all-extras`
Expected: completes without error.

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests from Tasks 4-7 pass (13 passed: 3 labels + 4 metrics + 2 dicom_io + 4 dataset).

- [ ] **Step 3: Run the linter**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 4: Confirm notebook JSON validity**

Run: `uv run python -c "import json; json.load(open('notebooks/01_eda.ipynb')); print('OK')"`
Expected: prints `OK`

- [ ] **Step 5: Review git status for anything unintentionally left out**

Run: `git status --short`
Expected: clean (empty output) — every file from Tasks 1-10 was committed at the end of its own task.

- [ ] **Step 6: Confirm the full commit history is coherent**

Run: `git log --oneline`
Expected: one commit per task (10 commits total: scaffold, coding standards+instructions, stub docs, labels, metrics, dicom_io, dataset, notebook, scripts, README), each with a clear Conventional Commits message.
