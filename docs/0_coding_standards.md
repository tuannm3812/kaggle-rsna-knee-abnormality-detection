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

- `notebooks/` — `01_eda.ipynb`, `02_weak_label_evaluation.ipynb`,
  `03_baseline_modeling.ipynb`, plus `notebooks/kernels/<name>/` holding
  each notebook's Kaggle `kernel-metadata.json`.
- `docs/` — durable findings and decisions, including
  `docs/collaboration/active_task.md` (current task's live handoff/review
  channel) and `docs/collaboration/archive/` (closed tasks' records).
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

## Collaboration Log

`docs/collaboration/active_task.md` is the shared handoff and review
channel for whatever task is currently in progress — design discussion,
Codex rounds, implementation reports, and independent review, all in one
place, in chronological order. Same pattern as
`kaggle-s6e8-predicting-smartphone-addiction`'s (pre-Cursor)
`docs/collaboration/`: one side implements/drafts, the other reviews
independently, findings get resolved there before the next step starts.
**Roles are assigned per task, not fixed** — either Claude or Codex may
be the implementer, with the other as reviewer; the active task's status
section states which is which for the current task. Read it (and the
relevant design spec or plan) before starting or resuming any task.

When a task is fully accepted — spec approved and, once implemented, both
reviews closed — move `active_task.md`'s record to
`docs/collaboration/archive/YYYY-MM-DD-<task-name>.md` and start a fresh
`active_task.md` for the next task. This replaces the earlier
single-growing-file `docs/7_codex_review_log.md` approach (used for this
project's first design review, now migrated into
`docs/collaboration/active_task.md`) — a per-task file that gets archived
scales better once the project has many sequential tasks, rather than one
document that grows without bound across the whole project.

## Codex Collaboration

**The user runs the Codex CLI (`codex exec` / `codex review`) directly —
Claude does not invoke it.** At major milestones (a new design spec, a
completed implementation phase), the user gets an independent pass from
Codex, run by hand — matches the manual, no-automation workflow already
used in `kaggriculture` and `kaggle-s6e8-predicting-smartphone-addiction`.
No CI/hook wiring, and no Claude-initiated `codex` subprocess calls —
this is a workflow habit the user drives, not a config artifact or an
automation Claude triggers.

Whichever side is reviewing in a given task, its evaluation of the
implementer's response, disposition, or revision must be appended to
`docs/collaboration/active_task.md`; do not leave feedback only in the
chat transcript. Each round records the date, reviewed commit or
artifact, verdict (`approved`, `revision required`, or `blocked on user
decision`), resolved findings, remaining findings with concrete evidence,
and the next required action. Record the entry before the next revision
starts so the full exchange remains reconstructable from the repository
alone.

Notebook naming: `01_eda.ipynb` → `02_weak_label_evaluation.ipynb` →
`03_baseline_modeling.ipynb` — zero-padded, matching the sibling repos.
Prefer a new config flag inside an existing notebook for a new experiment
variant over a new notebook file; only split out a new numbered notebook
once the current one becomes too large/slow to run as a single kernel.

## Python Style

- Follow PEP 8: 4-space indentation, group imports stdlib → third-party →
  local with a blank line between groups.
- Type hints and Google-style docstrings for everything in `src/`.
- `LABEL_COLUMNS` in `src/knee_mri/labels.py` is the single source of
  truth for the 12 target names and their order (must match
  `sample_submission.csv`'s header exactly) — import it, never
  re-type the list.

## Notebook Style

Every notebook is a public-facing artifact (private during development,
released only after an explicit publication decision — see "Pushing
Notebooks To Kaggle" below) and should include:

- Purpose statement aimed at a public reader — no internal file paths,
  housekeeping notes, or references to the design/review process (specs,
  plans, "trusted"/"reviewed" language). State facts about the analysis,
  not facts about the repository or how the work was reviewed.
- Configuration cell near the top, with a functional `IS_KAGGLE` check
  that resolves the competition data mount and the attached
  `rsna-knee-mri-src` source dataset, and raises immediately with a
  clear, path-free message if run anywhere other than Kaggle (this
  project has no local execution path — see "Data & Compute" below),
  plus a deterministic seed. The guard itself stays functional and
  unprinted: do not print `IS_KAGGLE`, resolved paths, or a
  `NOTEBOOK_VERSION` string — none of that belongs in public output.
- Markdown insight cells immediately after every displayed table or plot,
  starting with **Interpretation** (e.g. plain "Interpretation." or a more
  specific label such as "Interpretation and decision: No-go."),
  explaining what it shows and what it does not establish.
- Numbered `##` sections (`## 1. ...`, `## 2. ...`, ...) with clear
  reader-facing headers.
- Aggregate-only displayed content: no raw report text, study/series
  identifiers, or row-level predictions. Computed aggregates (counts,
  rates, distributions, summary statistics), column schema/dtype
  information, and hand-authored glossary/reference content are all
  permitted — the boundary is "no per-row sensitive values," not "nothing
  but a number."

**Outputs policy:** repository notebook copies (the `.ipynb` files
committed under `notebooks/`) remain output-free — empty `outputs`, null
`execution_count` — always, regardless of whether they've been run on
Kaggle. Only the private Kaggle kernel version itself may display real
aggregate outputs; a trusted run's results get transcribed into the
repository copy's Markdown, not left as stored cell output.
**Offline-safety:** submission notebooks must declare every dependency
explicitly and run with internet disabled — this is a Code Competition.
**Kernel display titles:** Title Case, matching the notebook's own `#`
heading (e.g. "RSNA Knee Abnormality Detection — Report Baseline").

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
(unflattened — see below), `vendor/` (the pinned offline wheel and its
license — see "Pin and Package the Offline Stratifier" in
`docs/superpowers/plans/2026-08-10-phase-3a-report-baseline.md`),
`README.md`, `LICENSE`, `pyproject.toml`, and `dataset-metadata.json` in
a clean temp directory, and passes `-r zip` — the Kaggle CLI's default
`--dir-mode` is `"skip"`, which silently omits directories (including
`src/` itself) from the upload if omitted.

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
matching the staging choice explained above. `01_eda.ipynb`'s and
`03_baseline_modeling.ipynb`'s config cells locate the package by
searching every attached dataset for a unique `knee_mri/__init__.py`
(`Path("/kaggle/input/datasets").rglob(...)`) rather than assuming a
fixed relative path, raising a clear error (rather than an opaque
`ModuleNotFoundError`) if it's missing or ambiguous.
`02_weak_label_evaluation.ipynb` still uses the original two-candidate
form (checks both the `src/`-nested and flat layouts directly) — an
accepted, unchanged legacy detail from before the `rglob` approach was
adopted, not a defect.

Submit with `scripts/submit_kaggle.sh`, which wraps
`api.competition_submit_code(...)` against a completed kernel version —
see the shared standard's §11 and `docs/1_instructions.md` for why this
needs the Python `kaggle` package rather than a raw CLI subcommand.

Kernels are `is_private: true` — this is a live, prize-money competition.
