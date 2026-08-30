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

### Baseline (`extract_weak_labels_naive`)

All 58 studies are non-abstained (the naive extractor never abstains):
`abstained_on_positive = abstained_on_negative = 0` for every label, and
`non_abstained_count = total_rows = 58` throughout, so `coverage = 1.0`
for every label. **`predicted_positive_support` and
`actual_positive_support` are not the same quantity even here** — e.g.
ACL has 29 predicted positives (`tp+fp`) but only 24 actual positives
(`tp+fn_confident`); they only coincide when precision happens to equal
recall's positive count, which they don't in general.

| Label | tp | fp | tn | fn_confident | abstained_on_positive | abstained_on_negative | actual_positive_support | predicted_positive_support | precision (ci) | recall (ci) | coverage | passes_gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ACL | 12 | 17 | 17 | 12 | 0 | 0 | 24 | 29 | 0.414 (0.255–0.593) | 0.500 (0.314–0.686) | 1.000 | False |
| MCL | 5 | 20 | 29 | 4 | 0 | 0 | 9 | 25 | 0.200 (0.089–0.391) | 0.556 (0.267–0.811) | 1.000 | False |
| Medial Meniscus | 12 | 10 | 22 | 14 | 0 | 0 | 26 | 22 | 0.545 (0.347–0.731) | 0.462 (0.288–0.645) | 1.000 | False |
| Lateral Meniscus | 11 | 10 | 25 | 12 | 0 | 0 | 23 | 21 | 0.524 (0.324–0.717) | 0.478 (0.292–0.670) | 1.000 | False |
| Medial OA | 1 | 0 | 43 | 14 | 0 | 0 | 15 | 1 | 1.000 (0.207–1.000) | 0.067 (0.012–0.298) | 1.000 | False |
| Lateral OA | 0 | 0 | 47 | 11 | 0 | 0 | 11 | 0 | 0.000 (0.000–0.000) | 0.000 (0.000–0.259) | 1.000 | False |
| PF OA | 0 | 0 | 37 | 21 | 0 | 0 | 21 | 0 | 0.000 (0.000–0.000) | 0.000 (0.000–0.155) | 1.000 | False |
| Effusion | 15 | 13 | 10 | 20 | 0 | 0 | 35 | 28 | 0.536 (0.358–0.705) | 0.429 (0.280–0.591) | 1.000 | False |
| Synovitis | 6 | 3 | 28 | 21 | 0 | 0 | 27 | 9 | 0.667 (0.354–0.879) | 0.222 (0.106–0.408) | 1.000 | False |
| Baker's | 4 | 7 | 39 | 8 | 0 | 0 | 12 | 11 | 0.364 (0.152–0.646) | 0.333 (0.138–0.609) | 1.000 | False |
| Contusion | 9 | 8 | 31 | 10 | 0 | 0 | 19 | 17 | 0.529 (0.310–0.738) | 0.474 (0.273–0.683) | 1.000 | False |
| Fracture | 7 | 7 | 33 | 11 | 0 | 0 | 18 | 14 | 0.500 (0.268–0.732) | 0.389 (0.203–0.614) | 1.000 | False |

### Fixed (`extract_weak_labels`, assertion-aware)

`total_rows = 58` for every label; `non_abstained_count = tp+fp+tn+
fn_confident` (so `coverage = non_abstained_count / 58`) is now shown
implicitly via `coverage` since it varies per label. Per Codex round 15:
the `abstained_on_positive`/`abstained_on_negative` split is real
information `coverage` alone can't recover (it gives total abstentions,
not their positive/negative split) — e.g. ACL abstains on 13 true
positives and 17 true negatives, a 30-way split `coverage=0.483` alone
doesn't reveal.

| Label | tp | fp | tn | fn_confident | abstained_on_positive | abstained_on_negative | actual_positive_support | predicted_positive_support | precision (ci) | recall (ci) | coverage | passes_gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ACL | 9 | 3 | 14 | 2 | 13 | 17 | 24 | 12 | 0.750 (0.468–0.911) | 0.375 (0.212–0.573) | 0.483 | False |
| MCL | 5 | 5 | 15 | 0 | 4 | 29 | 9 | 10 | 0.500 (0.237–0.763) | 0.556 (0.267–0.811) | 0.431 | False |
| Medial Meniscus | 12 | 4 | 6 | 0 | 14 | 22 | 26 | 16 | 0.750 (0.505–0.898) | 0.462 (0.288–0.645) | 0.379 | False |
| Lateral Meniscus | 10 | 3 | 7 | 1 | 12 | 25 | 23 | 13 | 0.769 (0.497–0.918) | 0.435 (0.256–0.632) | 0.362 | False |
| Medial OA | 1 | 0 | 0 | 0 | 14 | 43 | 15 | 1 | 1.000 (0.207–1.000) | 0.067 (0.012–0.298) | 0.017 | False |
| Lateral OA | 0 | 0 | 0 | 0 | 11 | 47 | 11 | 0 | 0.000 (0.000–0.000) | 0.000 (0.000–0.259) | 0.000 | False |
| PF OA | 0 | 0 | 0 | 0 | 21 | 37 | 21 | 0 | 0.000 (0.000–0.000) | 0.000 (0.000–0.155) | 0.000 | False |
| Effusion | 15 | 7 | 6 | 0 | 20 | 10 | 35 | 22 | 0.682 (0.473–0.836) | 0.429 (0.280–0.591) | 0.483 | False |
| Synovitis | 6 | 3 | 0 | 0 | 21 | 28 | 27 | 9 | 0.667 (0.354–0.879) | 0.222 (0.106–0.408) | 0.155 | False |
| Baker's | 4 | 2 | 5 | 0 | 8 | 39 | 12 | 6 | 0.667 (0.300–0.903) | 0.333 (0.138–0.609) | 0.190 | False |
| Contusion | 8 | 4 | 4 | 1 | 10 | 31 | 19 | 12 | 0.667 (0.391–0.862) | 0.421 (0.231–0.637) | 0.293 | False |
| Fracture | 4 | 0 | 7 | 2 | 12 | 33 | 18 | 4 | 1.000 (0.510–1.000) | 0.222 (0.090–0.452) | 0.224 | False |

Every row above satisfies `tp+fp+tn+fn_confident+abstained_on_positive+
abstained_on_negative = 58` (verified against each row before
transcribing).

### Allowlist (`MIN_SUPPORT=5`, `MIN_PRECISION_LOWER_BOUND=0.55`): **`[]` — 0/12**

Explicit: no label is on the allowlist. Point-estimate precision improved
substantially for most labels under the fixed extractor (assertion-
awareness is doing real work — e.g. Medial Meniscus 0.545→0.750, Fracture
0.500→1.000), but the Wilson lower bound stays under 0.55 for every
label given only 58 labeled studies. Closest misses: **Medial Meniscus**
(ci_low 0.505, support 16 — clears `MIN_SUPPORT` but not the precision
bound) and **Fracture** (ci_low 0.510, but support 4 — fails
`MIN_SUPPORT` outright regardless of precision). No label clears both
gates simultaneously.

**Interpretation, explicitly hedged:** this reads as small-sample
uncertainty rather than a precision ceiling — several labels are already
above the 0.55 point estimate (Medial Meniscus 0.750, Lateral Meniscus
0.769, Fracture 1.000, Baker's 0.667, Contusion 0.667) but the interval
is too wide at n≈10-20 to clear a 95% lower-bound gate. Not confirmed:
whether more labeled data would actually narrow the interval past the
gate, or whether the point estimates themselves would regress toward
something lower with more studies. The taxonomy below shows `no_mention`
(abstain, correctly not scored) dominates false negatives across almost
every label — coverage, not precision, looks like the more informative
next lever.

### Error taxonomy — `(label, orthographic_bucket, resolution_signature, prediction_error)` counts

Purely observational per the design spec section 5: `resolution_signature`
and `prediction_error` are directly-observed mechanical facts, not a
claimed cause for any mismatch.

| Label | Orthographic bucket | Resolution signature | Prediction error | Count |
|---|---|---|---|---|
| ACL | ascii_only | mixed_qualification | false_negative | 3 |
| ACL | ascii_only | unqualified_only | false_positive | 3 |
| ACL | greek_script | no_mention | false_negative | 1 |
| ACL | latin_with_german_turkish_umlaut | no_mention | false_negative | 1 |
| ACL | latin_with_south_slavic_diacritics | no_mention | false_negative | 1 |
| ACL | mixed_latin_diacritics | no_mention | false_negative | 3 |
| ACL | other_latin_undetermined | no_mention | false_negative | 6 |
| Baker's | ascii_only | no_mention | false_negative | 1 |
| Baker's | ascii_only | unqualified_only | false_positive | 2 |
| Baker's | greek_script | no_mention | false_negative | 1 |
| Baker's | latin_with_german_turkish_umlaut | no_mention | false_negative | 1 |
| Baker's | latin_with_south_slavic_diacritics | no_mention | false_negative | 2 |
| Baker's | mixed_latin_diacritics | no_mention | false_negative | 1 |
| Baker's | other_latin_undetermined | no_mention | false_negative | 2 |
| Contusion | ascii_only | mixed_qualification | false_negative | 1 |
| Contusion | ascii_only | no_mention | false_negative | 2 |
| Contusion | ascii_only | unqualified_only | false_positive | 3 |
| Contusion | greek_script | no_mention | false_negative | 2 |
| Contusion | latin_with_south_slavic_diacritics | no_mention | false_negative | 1 |
| Contusion | mixed_latin_diacritics | no_mention | false_negative | 2 |
| Contusion | other_latin_undetermined | no_mention | false_negative | 3 |
| Contusion | other_latin_undetermined | unqualified_only | false_positive | 1 |
| Effusion | ascii_only | unqualified_only | false_positive | 7 |
| Effusion | greek_script | no_mention | false_negative | 3 |
| Effusion | latin_with_german_turkish_umlaut | no_mention | false_negative | 1 |
| Effusion | latin_with_south_slavic_diacritics | no_mention | false_negative | 2 |
| Effusion | mixed_latin_diacritics | no_mention | false_negative | 5 |
| Effusion | other_latin_undetermined | no_mention | false_negative | 9 |
| Fracture | ascii_only | mixed_qualification | false_negative | 3 |
| Fracture | ascii_only | no_mention | false_negative | 1 |
| Fracture | greek_script | no_mention | false_negative | 1 |
| Fracture | latin_with_german_turkish_umlaut | no_mention | false_negative | 1 |
| Fracture | latin_with_south_slavic_diacritics | no_mention | false_negative | 1 |
| Fracture | mixed_latin_diacritics | no_mention | false_negative | 4 |
| Fracture | other_latin_undetermined | no_mention | false_negative | 3 |
| Lateral Meniscus | ascii_only | mixed_qualification | false_negative | 1 |
| Lateral Meniscus | ascii_only | unqualified_only | false_positive | 3 |
| Lateral Meniscus | greek_script | no_mention | false_negative | 2 |
| Lateral Meniscus | latin_with_south_slavic_diacritics | no_mention | false_negative | 1 |
| Lateral Meniscus | mixed_latin_diacritics | no_mention | false_negative | 2 |
| Lateral Meniscus | other_latin_undetermined | no_mention | false_negative | 7 |
| Lateral OA | ascii_only | no_mention | false_negative | 6 |
| Lateral OA | latin_with_south_slavic_diacritics | no_mention | false_negative | 1 |
| Lateral OA | other_latin_undetermined | no_mention | false_negative | 4 |
| MCL | ascii_only | unqualified_only | false_positive | 4 |
| MCL | greek_script | no_mention | false_negative | 1 |
| MCL | latin_with_german_turkish_umlaut | unqualified_only | false_positive | 1 |
| MCL | other_latin_undetermined | no_mention | false_negative | 3 |
| Medial Meniscus | ascii_only | unqualified_only | false_positive | 4 |
| Medial Meniscus | greek_script | no_mention | false_negative | 2 |
| Medial Meniscus | latin_with_german_turkish_umlaut | no_mention | false_negative | 2 |
| Medial Meniscus | latin_with_south_slavic_diacritics | no_mention | false_negative | 3 |
| Medial Meniscus | mixed_latin_diacritics | no_mention | false_negative | 5 |
| Medial Meniscus | other_latin_undetermined | no_mention | false_negative | 2 |
| Medial OA | ascii_only | no_mention | false_negative | 6 |
| Medial OA | greek_script | no_mention | false_negative | 2 |
| Medial OA | latin_with_south_slavic_diacritics | no_mention | false_negative | 3 |
| Medial OA | mixed_latin_diacritics | no_mention | false_negative | 1 |
| Medial OA | other_latin_undetermined | no_mention | false_negative | 2 |
| PF OA | ascii_only | no_mention | false_negative | 8 |
| PF OA | greek_script | no_mention | false_negative | 1 |
| PF OA | latin_with_german_turkish_umlaut | no_mention | false_negative | 1 |
| PF OA | latin_with_south_slavic_diacritics | no_mention | false_negative | 2 |
| PF OA | mixed_latin_diacritics | no_mention | false_negative | 1 |
| PF OA | other_latin_undetermined | no_mention | false_negative | 8 |
| Synovitis | ascii_only | no_mention | false_negative | 5 |
| Synovitis | ascii_only | unqualified_only | false_positive | 3 |
| Synovitis | greek_script | no_mention | false_negative | 3 |
| Synovitis | latin_with_german_turkish_umlaut | no_mention | false_negative | 2 |
| Synovitis | latin_with_south_slavic_diacritics | no_mention | false_negative | 2 |
| Synovitis | mixed_latin_diacritics | no_mention | false_negative | 3 |
| Synovitis | other_latin_undetermined | no_mention | false_negative | 6 |

Observed pattern (mechanical fact, not a claimed cause): `no_mention`
(the extractor found no keyword match at all, so it correctly abstained
rather than guessing) accounts for the large majority of
`false_negative` rows across almost every label and every non-ASCII
bucket. `unqualified_only` (a keyword matched with no qualifying cue
nearby, correctly resolved to 1) accounts for most `false_positive`
rows and is concentrated in `ascii_only`. Any causal read of this
pattern — e.g. "the English-only keyword vocabulary under-covers non-English
reports" — is a plausible hypothesis consistent with the design's known
scope limits, not something this table establishes on its own.

### Orthographic-bucket comparison — labeled (58) vs. unlabeled (4349) studies

Note: this compares the 58 labeled studies against the 4349 *unlabeled*
(report-only) studies produced by `split_labeled_studies` — not against
all 4407 `train.csv` rows (the 58 labeled studies are not double-counted
in the "unlabeled" column).

| Bucket | labeled | unlabeled | gap (pp) |
|---|---|---|---|
| ascii_only | 0.483 | 0.406 | 7.7 |
| other_latin_undetermined | 0.259 | 0.242 | 1.7 |
| mixed_latin_diacritics | 0.103 | 0.124 | 2.1 |
| latin_with_south_slavic_diacritics | 0.069 | 0.092 | 2.3 |
| greek_script | 0.052 | 0.073 | 2.1 |
| latin_with_german_turkish_umlaut | 0.034 | 0.062 | 2.8 |

The `ascii_only` bucket has a real 7.7-point gap (labeled studies skew
more English than the unlabeled population); the other five buckets are
within 1.7–2.8 points. Not close enough across the board to call the
labeled sample's character-set mix representative of the full unlabeled
population — the `ascii_only` overrepresentation is the one gap worth
naming explicitly, not glossing over. As before: even a close
orthographic mix would only bound *how much text looks alike*, not
*how well extraction accuracy transfers* to non-English text — these
buckets are honestly named character-set groups, not a language-ID or
accuracy signal.

### Verdict: **No-go** for an automatic weak-label allowlist from this
pass, per `docs/3_strategy.md` Phase 2's predefined decision rule. See
Phase 2's entry there for the resulting fork decision.

## 2026-08-13 — Signed patient-X orientation audit (Phase 3B preflight v7)

**Kernel:** private/offline/T4
`tuannm3812/rsna-knee-image-baseline-preflight-audit` v9, completed.
**Code:** private source dataset refreshed from commit `8cdfae8`.
**Data:** the fixed seeded 150-study sample, all 822 series; aggregate-only
output.

All 822 geometry-valid series had a unique dominant patient-X axis and
`dominant_abs_x > 0.80` (minimum 0.80985; minimum dominance gap 0.22801).
Counts below thresholds 0.80/0.85/0.90/0.95 were 0/3/13/34. Axial and coronal
series always mapped patient X to columns with positive sign (493/493);
sagittal series always mapped it to slice order, with negative sign among all
322 conservatively side-resolved cases. Seventeen series were excluded from
the side cross-tab by the conservative unresolved/conflict policy.

**Conclusion:** recommend `> 0.80` plus unique dominance as the conditional
canonicalization gate. Below-threshold/tied cases remain unchanged with
`laterality_reliable=0`. This is a descriptive sample and the fallback remains
required for unseen acquisitions. No reflection, model training, or submission
was performed.

> **Superseded:** the `> 0.80` recommendation above was not adopted. Review of
> the same measurements settled on **`> 0.90`**, on the grounds that the
> dominance *gap* establishes the axis choice is unambiguous while the
> dominance *magnitude* governs whether a reversal is a safe left/right
> reflection — and `0.80985`, the observed minimum, is 35.9 degrees off
> patient-X. `0.90` bounds accepted obliquity below 25.8 degrees at a cost of
> 13 of 822 audited series.

---

## 2026-08-27/28 — Image baseline, kernel versions 1-4

First executions of the Phase 3B pipeline itself rather than audits of its
inputs. All private, T4, offline; all `COMPLETE` with zero error markers. Full
detail in [`7_image_baseline_insights.md`](7_image_baseline_insights.md).

| Version | Purpose | Headline |
|---|---|---|
| 1 | First end-to-end run | Pooled OOF macro AUC **0.6346**; zero planes absent, zero retries, zero header failures |
| 2 | Representative timing | 83 studies across five slice-count strata; the 3-study estimate had been **49% pessimistic** |
| 3 | Vendored codecs | All three `cp312` wheels installed offline and imported; stratum profile monotonic, 2.00 to 5.46 s/study |
| 4 | Uncertainty | Bootstrap 95% **[0.5704, 0.6973]**; fold-assignment std `0.0157` against sampling half-width `0.0634` |

**Results that changed a decision, rather than confirming one:**

- The complete path costs **3.4x** the encoder-only lower bound measured
  earlier. Extrapolating from the encoder probe would have overstated headroom
  by roughly that factor. Runtime still is not a constraint — 3.5 hours against
  a 9-hour budget with a 3x margin.
- **Study sampling contributes 4x more uncertainty than fold assignment.** More
  folds, repeats, or a better split cannot tighten the estimate; only more
  labeled studies would.
- Per-label scores are strongly uneven — Effusion `0.811` and ACL `0.786`
  against MCL `0.519` and Fracture `0.456` — so the macro conceals that the
  baseline is informative for some findings and at chance for others.

**Predictions confirmed by measurement, having been stated in advance:** three
of 58 studies carry `laterality_reliable = 0` (predicted 2.7-2.8), and the
three plane-presence flags have variance exactly `0.0`.

**Determinism:** versions 1, 2 and 3 produced a bit-identical pooled macro AUC
while per-study wall clock varied by up to `1.52x`. The computation is
reproducible; only the clock is noisy.

**No submission was made in any run.**

---

## 2026-08-29 — W1: do report-derived weak labels beat 58 human ones?

The comparison, sample, metric and decision rule were pre-registered before
the run (collaboration round 106); the `20/5` label-viability floors were
frozen in code before the first run but not stated in that prose, and are
disclosed here and in the notebook's frozen contract instead. They were
non-binding on this result — every abstained label had zero resolved
negatives, which no threshold rescues — but the pre-registration was not
complete, and round 108's "in full" overstated it. Reopens the
Phase 2 weak-label fork on the grounds that its No-go answered a different
question: Phase 2 asked whether the labels are precise enough to trust and
rejected them on Wilson lower bounds driven by `n ~ 10-20`; it never asked
whether *training* on them improves the score. That has a cleaner test — fit
on report-only studies, evaluate on the 58 human-labelled ones, since noisy
training labels cannot corrupt a human-labelled evaluation set. Private, T4,
offline, `COMPLETE`. The model stays image-only at prediction time, so the
missing `Report` column in `test.csv` does not apply.

| | Baseline (58 human labels) | Weak labels (3000 reports) |
|---|---|---|
| Macro AUC | **0.6346** | **0.6056** |
| Delta, 95% paired bootstrap | — | **-0.0290 [-0.1021, +0.0467]** |
| Resolved | — | No |

**Predicted: positive and possibly resolved. Both halves wrong.** This was
the first experiment to predict resolution, on the reasoning that a
fifty-two-fold increase in training data could move the score by more than
the interval can see. The score moved the other way, and the effect was not
large enough to overcome the uncertainty that 58 evaluation studies impose.
This pairing also produced a *wider* interval than the fixed-58 comparisons:
half-width `0.074` against their `+/-0.024`, about **3.1 times wider**.

That width is not purely a property of the evaluation set. A paired
bootstrap resamples the 58 studies, so their number bounds what it can
resolve, but the width also depends on the two prediction vectors, their
correlation, and how the per-study and per-label differences are
distributed. Enlarging the training set was expected to change the *effect*,
not to narrow an evaluation-only interval mechanically — and here it did
neither favourably.

**The label supports are more informative than the headline.** Three labels
abstained, and not from low support in the ordinary sense — they have **zero
resolved negatives**: Medial OA 14 rows all positive, Lateral OA 1 row
positive, PF OA 36 rows all positive; Synovitis is nearly as skewed at 158
against 12. A report that omits osteoarthritis is an abstention, not a
negative, and radiologists do not appear to write "no osteoarthritis" the way
they write "no meniscal tear". No threshold rescues a single-class column.

**What the macro delta is actually made of.** Macro AUC is the mean of the
twelve per-label AUCs, so the delta decomposes exactly. The three
single-class OA labels are forced to chance and contribute **`-0.0379`** on
their own; the nine fitted heads contribute **`+0.0089`** between them. Those
sum to the observed `-0.0290`. **The headline is negative chiefly because a
quarter of the panel could not be fitted at all**, not because the fitted
heads were harmed.

**A different target is a plausible reading, not an established one.** Round
106 named in advance the mechanism that would matter — weak positives encode
"mentioned without qualification", which is a different event from the
finding being present — and the zero-negative OA supports are consistent with
it. But the registered trigger for that reading was a *clearly* negative
result, and this interval crosses zero widely. Mixed per-label signs (gains
on Baker's `+0.118`, Fracture `+0.101`, Medial Meniscus `+0.100`, Contusion
`+0.096`; losses on ACL `-0.127`, Synovitis `-0.076`) do not establish it:
with 58 studies and uneven per-label support, sign splits are equally
consistent with label-dependent noise and with sampling variation. Round 108
claimed uniform noise would move every label the same way; that does not hold
for a finite, heterogeneous twelve-label panel, and the claim is withdrawn.

**No follow-up is proposed, deliberately — and the two obvious follow-ups
are invalid for different reasons.** Keeping the four labels that gained
would select on the evaluation set: their gains are only visible *because*
they were scored against the 58 human labels, which is exactly the leakage
round 106 refused when it declined to choose labels by measured precision.
Dropping the three abstaining labels is **not** evaluation-set leakage — an
abstention is decided entirely from weak-training support, before any human
label is scored — but it is still invalid here, because it would change the
pre-registered twelve-label macro after seeing the result. The competition
metric is the twelve-label macro; a hybrid that falls back to the baseline
for labels the reports cannot supply is a reasonable idea and would be a
**new registered experiment**, not a re-reading of this one. **The conclusion
stands as measured: W1 does not displace the baseline, and is not shown to
help or hurt.**

**Cost, now measured:** `6958.6 s` for 3000 studies, `2.32 s/study`, within
4% of the budgeted `2.4`. The full 4349 report-only studies would cost about
`2.8 h`, so the 3000 cap was budget-driven and never binding on the result.

**No submission was made.** The notebook writes none, and a test asserts it.
