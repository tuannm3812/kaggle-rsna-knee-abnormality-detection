# Submissions

Append-only log: every real Kaggle submission — the ground-truth
leaderboard record. Empty until the first submission is made.

## 2026-08-28 — First two submissions

Both authorized by the user; both are code-competition submissions, so Kaggle
reruns the kernel against the hidden test set rather than scoring an uploaded
file. Public scores pending at the time of writing.

| Ref | Kernel | Config | OOF macro AUC | Public | Private |
|---|---|---|---:|---|---|
| `55838115` | `rsna-knee-frozen-image-baseline` v12 | V0: mean pooling, 5 slices | 0.6346 | pending | pending |
| `55838628` | `rsna-knee-max-pooling-submission` v1 | Max pooling, 15 slices | 0.6507 | pending | pending |

### Why two entries rather than one

The second is **not a promotion of the first.** Max pooling scored `+0.016`
higher out of fold, but the paired interval did not exclude zero at the level
registered before that comparison was run — `[−0.007, +0.041]` nominal,
`[−0.017, +0.053]` corrected for nine comparisons. Under the registered rule
the baseline stands, so it was submitted as the project's reported figure and
max pooling as a deliberate second entry.

The leaderboard now provides something the labelled set could not: an
independent read on which configuration generalizes, on a test set far larger
than 58 studies.

### What to expect, recorded before the scores land

The out-of-fold difference is `+0.016` with an interval spanning roughly
`±0.024`. **Public scores differing by less than that carry no information
about which configuration is better** — the ordering could reverse purely by
sampling. A reversal should not be read as max pooling having failed, nor a
confirmation as it having been proven; only a gap materially wider than the
out-of-fold interval would be evidence either way.

Both figures will also sit below their out-of-fold values if the labelled 58
are easier than the test distribution, which is likely: they were the subset a
human chose to label.

### Caveats attached to the max-pooling entry

1. It changes sampling density *and* pooling operator against the baseline. The
   density leg was separately measured and null, which makes the pair
   interpretable, but a win is not attributable to the operator alone.
2. It was selected because it scored highest across nine comparisons, so
   `0.6507` overstates what an equivalently-chosen variant would score on new
   data. No interval removes this; it is a property of how the candidate was
   chosen.

### Reproduction

Both kernels pin `machine_shape: NvidiaTeslaT4`, run offline against the
SHA-256-pinned code dataset, and fail rather than proceed if their configuration
does not reproduce its measured out-of-fold score — `0.6345688959` for the
baseline, `0.6507039913` for max pooling. Both reported the same fold-assignment
signature, `f8c576c8…`, so the two scores were computed over identical folds.
