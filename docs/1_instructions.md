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
- **`test.csv`** — **not** the same schema as `train.csv`: real Kaggle
  execution confirms it has only `StudyInstanceUID`, no `Report` column at
  all (verified directly against the live mounted competition data, not
  assumed — see `docs/collaboration/active_task.md` round 37). A model that
  needs report text at inference time cannot be built against this file.
- **`test_series.csv` / `test_series/`** — same schema as
  `train_series.csv`/`train_series/` (also verified against real data, round
  39's preflight audit). The local copies are 3 example studies only. Real
  scoring test set is ~1300 studies.
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
