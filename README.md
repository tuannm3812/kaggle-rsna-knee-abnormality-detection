# RSNA Knee Abnormality Detection

<p align="center">
  <a href="https://www.kaggle.com/competitions/rsna-knee-abnormality-detection"><img alt="Kaggle Competition" src="https://img.shields.io/badge/Kaggle-RSNA%20Knee%20Abnormality%20Detection-20BEFF?logo=kaggle&logoColor=white"></a>
  <a href="pyproject.toml"><img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="docs/0_coding_standards.md"><img alt="Execution" src="https://img.shields.io/badge/Execution-Kaggle--only-orange"></a>
  <img alt="Status" src="https://img.shields.io/badge/Status-Phase%203B%20Design%20Proposed-blue">
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

EDA (Phase 1) and weak-label evaluation (Phase 2, verdict: No-go) are
complete with real results — see
[`docs/2_eda_insights.md`](docs/2_eda_insights.md) and
[`docs/4_experiments.md`](docs/4_experiments.md). Phase 3A (report-only
baseline) is fully implemented, but its first real Kaggle run revealed that
the competition's real `test.csv` has no `Report` column — a model trained
only on report text cannot be submitted, so Phase 3A now stands as an
internal, train-only signal audit rather than a path to a submission. Phase
3B (a frozen pretrained image encoder) is being pulled forward as the
actual first submittable baseline: a design has been proposed and a
project-owned DICOM/series preflight audit has run to inform it
([`docs/7_image_baseline_insights.md`](docs/7_image_baseline_insights.md)),
but the formal design is not yet written or approved, and no submission
exists yet. Full roadmap: [`docs/3_strategy.md`](docs/3_strategy.md); full
review history: `docs/collaboration/active_task.md`. See
[`docs/5_submissions.md`](docs/5_submissions.md) once a real submission
exists.

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
| [`7_image_baseline_insights.md`](docs/7_image_baseline_insights.md) | Real DICOM/series measurements informing the Phase 3B image-baseline pipeline design |

## Repository layout

- [`notebooks/`](notebooks/) — `01_eda.ipynb`,
  `02_weak_label_evaluation.ipynb`, `03_baseline_modeling.ipynb`,
  `04_image_baseline_preflight.ipynb`, plus `notebooks/kernels/<name>/`
  holding each notebook's Kaggle `kernel-metadata.json`.
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
