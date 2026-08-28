# Submissions

Append-only log: every real Kaggle submission — the ground-truth
leaderboard record. Empty until the first submission is made.

## 2026-08-28 — First two submissions

Both authorized by the user; both are code-competition submissions, so Kaggle
reruns the kernel against the hidden test set rather than scoring an uploaded
file. Both scored; private scores follow the deadline.

| Ref | Kernel | Config | OOF macro AUC | Public | Private |
|---|---|---|---:|---|---|
| `55838115` | `rsna-knee-frozen-image-baseline` v12 | V0: mean pooling, 5 slices | 0.6346 | **0.681** | pending |
| `55838628` | `rsna-knee-max-pooling-submission` v1 | Max pooling, 15 slices | 0.6507 | **0.687** | pending |

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

## 2026-08-28 — Results, read against what was written beforehand

| Config | OOF | Public LB | Public − OOF |
|---|---:|---:|---:|
| V0 mean, 5 slices | 0.6346 | **0.681** | +0.046 |
| Max, 15 slices | 0.6507 | **0.687** | +0.036 |
| Gap | +0.0161 | **+0.006** | |

### The leaderboard does not separate them, exactly as pre-stated

The previous section fixed the threshold before the scores existed: a public
gap smaller than the out-of-fold interval of roughly `±0.024` carries no
information about which configuration is better. **The observed gap is
`0.006`, about a quarter of that threshold.**

The ordering matches the out-of-fold ordering, and that is worth nothing. A
0.006 separation on a single public split is what two indistinguishable models
look like. **This is not confirmation that max pooling is better.** Had the
ordering reversed, that would equally not have been evidence it is worse.

The honest summary is the one the labelled set already gave: **the two
configurations are indistinguishable on the evidence available**, and the
leaderboard — despite a far larger test set — agrees.

### A prediction that was wrong, and the reason

The previous section predicted both public scores would land **below** their
out-of-fold values, on the grounds that the 58 labelled studies are the subset
a human chose to label and so are probably easier than the test distribution.

**Both landed above** — by `+0.046` and `+0.036`. The reasoning was not merely
unlucky; it weighed the wrong effect.

The dominant factor is training-set size, not difficulty. Each out-of-fold
prediction comes from a model fitted on about 46 studies, while the submitted
model refits on all 58 — **26% more training data**. At this sample size that
difference is large, and cross-validation is a known-pessimistic estimator of
the refit model's performance for exactly this reason. The selection-difficulty
argument may still be real, but it is smaller than the effect it was competing
with.

This also slightly rehabilitates the reported figure: `0.6346` is a
conservative estimate of what the deployed baseline does, not an optimistic
one. The winner's-curse caveat on the max-pooling entry is unaffected — that
concerns which configuration was chosen, not how either was estimated.

### What still cannot be claimed

A public leaderboard is itself a sample, and its own interval is not published.
Neither entry has a private score yet. Nothing here changes the registered
conclusion: **no variant displaced the baseline**, and the reported figure
remains `0.6346` out-of-fold with a public score of `0.681`.
