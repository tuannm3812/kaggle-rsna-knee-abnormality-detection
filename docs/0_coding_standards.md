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
- `7_codex_review_log.md` — independent Codex CLI review of design specs,
  plans, and milestones, same pattern as `kaggriculture` and
  `kaggle-s6e8-predicting-smartphone-addiction`. Append-only; one entry
  per review, cited by section/date from the plan or spec it reviewed.

## Codex Review

At major milestones (a new design spec, a completed implementation
phase), get an independent second opinion from the Codex CLI (`codex
review` / `codex exec -s read-only`) alongside Claude's own review
process — matches the manual, no-automation workflow already used in
`kaggriculture` and `kaggle-s6e8-predicting-smartphone-addiction`: run it
by hand, record findings in `docs/7_codex_review_log.md`, and treat it as
a collaboration input, not an approved decision by itself. No CI/hook
wiring — this is a workflow habit, not a config artifact.

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
- Configuration cell near the top, with an `IS_KAGGLE` check that resolves
  the competition data mount and `src/knee_mri`'s dataset mount, and raises
  immediately with a clear message if run anywhere other than Kaggle (this
  project has no local execution path — see "Data & Compute" below), plus
  a deterministic seed and a `NOTEBOOK_VERSION` string printed by the first
  code cell.
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
can upload `.venv/`/`.git/` by accident. The script stages `src/`
(unflattened — see below), `README.md`, `LICENSE`, `pyproject.toml`, and
`dataset-metadata.json` in a clean temp directory, and passes `-r zip` —
the Kaggle CLI's default `--dir-mode` is `"skip"`, which silently omits
directories (including `src/` itself) from the upload if omitted.

**Confirmed against a real kernel run** (see
`docs/6_kaggle_troubleshooting.md`): a personal/private dataset attached
via `dataset_sources` mounts at
`/kaggle/input/datasets/<owner>/<dataset-slug>/` — **not**
`/kaggle/input/<dataset-slug>/`, which only holds true for a kernel's
*own* output or in older/solo-dataset-source kernels. Competition data
attached via `competition_sources` does mount at the flat
`/kaggle/input/competitions/<competition-slug>/`, as originally assumed —
only the dataset path needed correcting. Within the dataset mount, the
zip's `src/` wrapper is preserved (`.../rsna-knee-mri-src/src/knee_mri/`),
matching the staging choice explained above. `01_eda.ipynb`'s config cell
uses this confirmed path directly and still checks both the `src/`-nested
and flat forms before importing, raising a clear error (rather than an
opaque `ModuleNotFoundError`) if neither exists.

Submit with `scripts/submit_kaggle.sh`, which wraps
`api.competition_submit_code(...)` against a completed kernel version —
see the shared standard's §11 and `docs/1_instructions.md` for why this
needs the Python `kaggle` package rather than a raw CLI subcommand.

Kernels are `is_private: true` — this is a live, prize-money competition.
