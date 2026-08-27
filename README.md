# RSNA Knee Abnormality Detection

<p align="center">
  <a href="https://www.kaggle.com/competitions/rsna-knee-abnormality-detection"><img alt="Kaggle Competition" src="https://img.shields.io/badge/Kaggle-RSNA%20Knee%20Abnormality%20Detection-20BEFF?logo=kaggle&logoColor=white"></a>
  <a href="pyproject.toml"><img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="docs/0_coding_standards.md"><img alt="Execution" src="https://img.shields.io/badge/Execution-Kaggle--only-orange"></a>
  <img alt="Tests" src="https://img.shields.io/badge/tests-433%20passing-brightgreen">
  <img alt="Status" src="https://img.shields.io/badge/Status-Image%20baseline%20evaluated-blue">
</p>

Personal entry for the Kaggle competition
[RSNA Knee Abnormality Detection](https://www.kaggle.com/competitions/rsna-knee-abnormality-detection):
predict per-study probabilities for 12 clinically important knee MRI
findings — ACL/MCL/meniscus injuries, three-compartment osteoarthritis,
effusion, synovitis, Baker's cyst, contusion, and fracture — from a
**569.76 GB** dataset pairing DICOM series with free-text radiology
reports. Scored by macro-averaged AUC-ROC. Full task, data format, and
scoring details: [`docs/1_instructions.md`](docs/1_instructions.md).

## Where this stands

A frozen-encoder image baseline is **implemented, run end to end on Kaggle,
and evaluated with an uncertainty estimate**. No submission has been made.

**Pooled out-of-fold macro AUC `0.6346`, bootstrap 95% interval
`[0.5704, 0.6973]`** over the 58 human-labeled studies. The lower bound is
above chance, so the signal is real; the interval is `±0.063` wide, which is
the honest cost of 58 studies.

The macro hides a strongly uneven picture, and that is the most useful result:

| Informative | | Near chance | |
|---|---:|---|---:|
| Effusion | 0.811 | PF OA | 0.551 |
| ACL | 0.786 | MCL | 0.519 |
| Lateral Meniscus | 0.755 | Fracture | 0.456 |
| Medial OA | 0.752 | | |

Mean-pooling five central-band slices through a frozen encoder carries
effusion and cruciate-ligament signal but evidently not fine cartilage or
patellofemoral detail. Decomposing the variance also shows **study sampling
contributes 4x more uncertainty than fold assignment**, so a better split
cannot tighten this — only more labeled studies would.

Runtime is not a constraint: the complete path projects to **3.5 hours
against a 9-hour budget** including a 3x safety margin, measured across 83
studies in five slice-count strata. Three independent kernel runs produced a
bit-identical score, so the pipeline is reproducible.

Earlier phases: EDA (Phase 1) complete; weak-label mining (Phase 2) evaluated
and rejected, **verdict No-go**; a report-only baseline (Phase 3A) fully
implemented before a real Kaggle run revealed the competition's `test.csv`
carries no `Report` column at all — so it can never produce a submission and
stands as a train-only signal audit. That discovery is why the image baseline
exists.

Full measurement history:
[`docs/7_image_baseline_insights.md`](docs/7_image_baseline_insights.md).
Roadmap: [`docs/3_strategy.md`](docs/3_strategy.md).

## Pipeline

Per study, all contracts frozen before evaluation:

1. **Select** at most one series per anatomical plane, ranking candidates
   (fluid-sensitive, then slice count, then UID) and retrying the next when
   one fails validation.
2. **Validate the order** strictly — finite, non-degenerate, mutually
   consistent, pairwise-distinguishable geometry, or a complete unique
   `InstanceNumber` sequence. A series that satisfies neither is never
   silently ordered by filename.
3. **Sample** five deterministic central-band slices, requiring at least
   three to decode.
4. **Normalize** intensity faithfully to DICOM: padding masked in the stored
   value domain *before* the modality transform, `MONOCHROME1` polarity
   handled, per-slice percentile clipping.
5. **Frame** by true physical aspect ratio, letterboxed to 336x336 — nothing
   cropped.
6. **Canonicalize laterality** by a signed rule over the patient axis that
   actually carries left/right, applied atomically across planes or not at
   all.
7. **Encode** with a frozen DINOv2-small, mean-pool within and across present
   planes, and fit one strongly regularized multilabel linear head.

Absent planes are excluded from the mean, never imputed. Every fallback is
counted in aggregate telemetry rather than assumed.

## Documentation

| Doc | Contents |
|---|---|
| [`0_coding_standards.md`](docs/0_coding_standards.md) | Project conventions and overrides of the personal master standard |
| [`1_instructions.md`](docs/1_instructions.md) | Competition spec, data format, submission method |
| [`2_eda_insights.md`](docs/2_eda_insights.md) | EDA findings from real Kaggle runs |
| [`3_strategy.md`](docs/3_strategy.md) | Competitive-landscape analysis and the prioritized roadmap |
| [`4_experiments.md`](docs/4_experiments.md) | Every local/Kaggle validation run |
| [`5_submissions.md`](docs/5_submissions.md) | Every real Kaggle submission |
| [`6_kaggle_troubleshooting.md`](docs/6_kaggle_troubleshooting.md) | Reusable diagnosis for Kaggle CLI/API friction |
| [`7_image_baseline_insights.md`](docs/7_image_baseline_insights.md) | Every measured result behind the image baseline |

The frozen design lives in
[`docs/superpowers/specs/`](docs/superpowers/specs/), and the full
round-by-round review history in `docs/collaboration/`.

## Repository layout

- [`notebooks/`](notebooks/) — `01_eda`, `02_weak_label_evaluation`,
  `03_baseline_modeling`, `04_image_baseline_preflight`,
  `05_image_baseline`, plus `notebooks/kernels/<name>/` holding each
  notebook's Kaggle `kernel-metadata.json`.
- [`src/knee_mri/`](src/knee_mri/) — the tested pipeline: DICOM I/O and
  series auditing, geometry validation and ordering, intensity
  normalization, physical framing, laterality canonicalization, slice
  sampling, study-feature assembly, and the evaluation harness. Written from
  scratch; no official competition baseline exists.
- [`docs/`](docs/) — see the table above.
- [`scripts/`](scripts/) — `push_kaggle_kernel.sh`,
  `publish_code_dataset.sh`, `submit_kaggle.sh`.
- [`vendor/`](vendor/) — offline wheels and model metadata shipped to Kaggle
  kernels, each pinned by SHA-256. **Note:** `pylibjpeg-libjpeg` is licensed
  GPL v3.0 while this repository is MIT; see
  [`vendor/pylibjpeg-LICENSE.txt`](vendor/pylibjpeg-LICENSE.txt).

## Setup

```bash
uv sync --extra dev --extra notebook --extra kaggle --extra torch
uv run pytest -q
uv run ruff check .
```

The competition dataset (569.76 GB) is never downloaded locally — everything
touching real data runs on Kaggle Kernels via the Kaggle CLI, where it is
already mounted. Local tests run against small synthetic DICOM fixtures. See
[`docs/0_coding_standards.md`](docs/0_coding_standards.md) for project
conventions.
