# Kaggle Troubleshooting

Append-only log: reusable diagnosis for Kaggle CLI/API friction (auth,
kernel push quirks, offline-install pitfalls, submission mechanics).

## Personal dataset mount path is `/kaggle/input/datasets/<owner>/<slug>/`, not `/kaggle/input/<slug>/` (2026-08-09)

`scripts/publish_code_dataset.sh create` staged `src/` (containing
`knee_mri/`) and zipped it as `src.zip`. `kaggle datasets files
tuannm3812/rsna-knee-mri-src` (checked right after publishing, before any
kernel run) showed the zip's `src/` wrapper preserved — files listed as
`src/knee_mri/__init__.py` etc. — confirming the internal package layout
guess was correct.

That alone wasn't enough: `01_eda.ipynb` kernel versions 1 and 2 both
failed with our own `RuntimeError` (not an opaque `ModuleNotFoundError` —
the fail-fast check did its job) because `SRC_DATASET_DIR` was set to
`/kaggle/input/rsna-knee-mri-src`, which doesn't exist. Kernel version 3
added a bounded, depth-limited directory listing (`/kaggle/input`, 3
levels deep — an *unbounded* recursive glob would have crawled the
competition's hundreds of thousands of DICOM files) and revealed the real
structure:

```
/kaggle/input/competitions/rsna-knee-abnormality-detection/...   (as assumed — competition_sources mounts flat)
/kaggle/input/datasets/tuannm3812/rsna-knee-mri-src/...           (NOT flat — dataset_sources nests under datasets/<owner>/)
```

So a kernel combining `competition_sources` + `dataset_sources` mounts
them differently: competition data stays flat at
`/kaggle/input/competitions/<slug>/`, but a personal dataset nests under
`/kaggle/input/datasets/<owner>/<dataset-slug>/`. `01_eda.ipynb` kernel
version 4 uses `SRC_DATASET_DIR = Path("/kaggle/input/datasets/tuannm3812/
rsna-knee-mri-src")` directly (no longer a guess). Apply this same
`datasets/<owner>/<slug>/` mount pattern to
any future kernel that attaches a personal dataset alongside competition
data — check `/kaggle/input`'s actual layout first if a kernel behaves
this way again with a *different* dataset, since this hasn't been
confirmed for a kernel with dataset-only attachments (no competition
data).

**Resolved**: kernel version 4 (with the corrected mount path) got past
the import step and ran three full EDA sections before hitting an
unrelated `KeyError: 'PatientSex'` (see the "no `PatientSex` column"
finding in `docs/2_eda_insights.md` — a real data finding, not a mount-path
issue). Kernel version 6, with that cell made defensive, completed end to
end. Kernel version 7 (`01_eda.ipynb` as currently committed, with real
insight text and `NOTEBOOK_VERSION=v5`) reconfirmed COMPLETE.
