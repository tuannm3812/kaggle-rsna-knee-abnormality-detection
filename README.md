# RSNA Knee Abnormality Detection

<p align="center">
  <a href="https://www.kaggle.com/competitions/rsna-knee-abnormality-detection"><img alt="Kaggle Competition" src="https://img.shields.io/badge/Kaggle-RSNA%20Knee%20Abnormality%20Detection-20BEFF?logo=kaggle&logoColor=white"></a>
  <a href="pyproject.toml"><img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="docs/0_coding_standards.md"><img alt="Execution" src="https://img.shields.io/badge/Execution-Kaggle--only-orange"></a>
  <img alt="Status" src="https://img.shields.io/badge/Status-Phase%203A%20In%20Progress-blue">
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
complete with real trusted results — see
[`docs/2_eda_insights.md`](docs/2_eda_insights.md) and
[`docs/4_experiments.md`](docs/4_experiments.md). Phase 3A (report-only
baseline) is in progress: the package layer and all three public
notebooks are implemented and reviewed; the first Kaggle run and
submission have not happened yet. Full roadmap:
[`docs/3_strategy.md`](docs/3_strategy.md). See
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

## Repository layout

- [`notebooks/`](notebooks/) — `01_eda.ipynb`,
  `02_weak_label_evaluation.ipynb`, `03_baseline_modeling.ipynb`, plus
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
