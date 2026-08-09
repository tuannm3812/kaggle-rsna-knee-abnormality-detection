# Experiments

Append-only log: every local/Kaggle validation run, submitted or not, one
entry per experiment (config, score, conclusion).

## 2026-08-09 — Weak-label evaluation (Phase 2)

**Kernel:** `tuannm3812/rsna-knee-weak-label-evaluation` v2 (v1 failed on
a real-data validation bug, see `docs/collaboration/active_task.md`).
**Code:** `rsna-knee-mri-src` dataset version published from commit
`39e955b`. **Data:** the 58 human-labeled studies (`split_labeled_studies`
on `train.csv`). Full mechanism:
`docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md`.

Two extractors scored against the same 58 studies via
`weak_label_metrics`: `extract_weak_labels_naive` (frozen baseline,
keyword match only) vs. `extract_weak_labels` (clause-scoped,
assertion-aware). Aggregate counts/rates only — no report text or study
identifiers left Kaggle.

### Precision, per label (naive → fixed; Wilson 95% lower bound in parens)

| Label | naive precision (ci_low) | fixed precision (ci_low) | fixed support | fixed coverage |
|---|---|---|---|---|
| ACL | 0.414 (0.255) | 0.750 (0.468) | 12 | 0.483 |
| MCL | 0.200 (0.089) | 0.500 (0.237) | 10 | 0.431 |
| Medial Meniscus | 0.545 (0.347) | 0.750 (0.505) | 16 | 0.379 |
| Lateral Meniscus | 0.524 (0.324) | 0.769 (0.497) | 13 | 0.362 |
| Medial OA | 1.000 (0.207) | 1.000 (0.207) | 1 | 0.017 |
| Lateral OA | 0.000 (0.000) | 0.000 (0.000) | 0 | 0.000 |
| PF OA | 0.000 (0.000) | 0.000 (0.000) | 0 | 0.000 |
| Effusion | 0.536 (0.358) | 0.682 (0.473) | 22 | 0.483 |
| Synovitis | 0.667 (0.354) | 0.667 (0.354) | 9 | 0.155 |
| Baker's | 0.364 (0.152) | 0.667 (0.300) | 6 | 0.190 |
| Contusion | 0.529 (0.310) | 0.667 (0.391) | 12 | 0.293 |
| Fracture | 0.500 (0.268) | 1.000 (0.510) | 4 | 0.224 |

("support" = `predicted_positive_support`, the Wilson interval's `n`.
"coverage" = fraction of the 58 studies where the fixed extractor gave a
confident 1 or 0 rather than abstaining.)

### Allowlist: 0/12 (`MIN_SUPPORT=5`, `MIN_PRECISION_LOWER_BOUND=0.55`)

No label clears the gate. Point-estimate precision improved substantially
for most labels (assertion-awareness is doing real work — e.g. Medial
Meniscus 0.545→0.750, Fracture 0.500→1.000), but the Wilson lower bounds
stay under 0.55 for every label given only 58 labeled studies. Closest
misses: **Medial Meniscus** (ci_low 0.505, support 16) and **Fracture**
(ci_low 0.510, but support 4 — fails the support gate outright regardless
of precision). No label has both `support >= 5` and `ci_low >= 0.55`.

**Interpretation, explicitly hedged:** this reads as small-sample
uncertainty rather than a precision ceiling — several labels are already
above the 0.55 point estimate (Medial Meniscus 0.750, Lateral Meniscus
0.769, Fracture 1.000, Baker's 0.667, Contusion 0.667) but the interval
is too wide at n≈10-20 to clear a 95% lower-bound gate. Not confirmed:
whether more labeled data would actually narrow the interval past the
gate, or whether the point estimates themselves would regress toward
something lower with more studies. `resolution_signature` counts (error
taxonomy, `docs/collaboration/active_task.md`) show `no_mention`
(abstain, correctly not scored) dominates false negatives across almost
every label — coverage, not precision, looks like the more informative
next lever.

### Orthographic-bucket comparison (labeled vs. all 4407 studies)

| Bucket | labeled | unlabeled |
|---|---|---|
| ascii_only | 0.483 | 0.406 |
| other_latin_undetermined | 0.259 | 0.242 |
| mixed_latin_diacritics | 0.103 | 0.124 |
| latin_with_south_slavic_diacritics | 0.069 | 0.092 |
| greek_script | 0.052 | 0.073 |
| latin_with_german_turkish_umlaut | 0.034 | 0.062 |

The labeled set's character-set mix is close to the unlabeled set's (all
buckets within ~2 points), so this result plausibly generalizes rather
than being an artifact of a skewed labeled sample — though "close
orthographic mix" is not proof of "close extraction accuracy" for
non-English text, since these buckets are honestly named as character
sets, not language identification.

### Verdict: **No-go** for an automatic weak-label allowlist from this
pass, per `docs/3_strategy.md` Phase 2's predefined decision rule. See
Phase 2's entry there for the resulting fork decision.
