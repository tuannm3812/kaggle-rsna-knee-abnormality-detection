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

## Kernel title/id slug auto-migration and the 50-character title limit (2026-08-11)

Pushing a kernel whose `title` doesn't resolve to the same slug as the `id`
declared in `kernel-metadata.json` triggers a warning
(`"Your kernel title does not resolve to the specified id"`) and Kaggle
silently assigns the kernel a **new** id/slug derived from the title,
rather than honoring the pinned `id`. Confirmed on first push for three
separate kernels (EDA, baseline-modeling, image-baseline-preflight). Fix:
after the first push, pull the live metadata (`kaggle kernels pull
<slug> -m`) to discover the real id, then update the local
`kernel-metadata.json` (and any test asserting that id) to match — do not
assume the declared `id` took effect just because the push command
succeeded.

Separately, Kaggle also hard-rejects any kernel `title` over 50 characters
(`{"error":{"code":400,"message":"The title cannot exceed 50 characters"}}`
from `SaveKernel`) — this fails the push outright with an unhelpful `400
Client Error: Bad Request` unless the raw response body is inspected (the
CLI's own stderr output doesn't surface the actual reason). Applies even
though nothing in the CLI's `-h` output or the metadata template mentions
a length limit. See `docs/0_coding_standards.md`'s "Kernel display titles"
rule for the resulting convention (shorten the kernel title, keep the
notebook's own `#` heading full-length).

## GPU allocation can be an older card the installed PyTorch no longer supports (2026-08-11/12)

An `enable_gpu: true` kernel run can be allocated a Tesla P100
(CUDA compute capability 6.0); Kaggle's preinstalled `torch` build has
dropped support for anything below `sm_70`, so any CUDA op raises
`AcceleratorError: CUDA error: no kernel image is available for execution
on the device` — losing the entire run, including any already-computed
results, unless the notebook checks compatibility itself before running
GPU code (`torch.cuda.get_device_capability(0)` against
`torch.cuda.get_arch_list()`) and reports it as data rather than crashing.
Observed on two independent runs for the same kernel, suggesting this may
not be per-session random luck for this account. `kaggle kernels push`
supports an explicit `--accelerator ACC` flag (confirmed via `-h` and the
installed `kagglesdk`'s enum, which documents `NvidiaTeslaT4` and
`NvidiaTeslaP100` as valid values) to request a specific card instead of
leaving it to whatever the pool assigns — untested whether this is honored
for every account/competition tier.

## Kernel-output retrieval only covers `/kaggle/working` files and a plain log, not rendered notebook output (2026-08-11)

`kaggle kernels output <slug>` downloads files written to `/kaggle/working`
during the run plus a plain-text stderr/traceback log — it does **not**
expose a notebook-type kernel's rendered `display()`/`plt.show()` output
(the `__notebook__.ipynb`/`__results__.html` papermill/nbconvert produce
internally are not part of the `list_kernel_session_output` API this CLI
command wraps). A kernel that never writes to `/kaggle/working` leaves its
real results unretrievable through this workflow even after a `COMPLETE`
run. Fix: have the notebook explicitly serialize its aggregate results to
a small file under `/kaggle/working` (e.g. a JSON summary) as its last
step, and fetch that.
