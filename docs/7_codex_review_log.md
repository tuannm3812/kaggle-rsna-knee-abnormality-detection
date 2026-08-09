# Codex Review Log

Append-only: independent Codex CLI review of design specs, plans, and
milestones — a collaboration input, not an approved decision by itself.
Same workflow as `kaggriculture` and
`kaggle-s6e8-predicting-smartphone-addiction`: run by hand, findings
recorded here, cited from the plan/spec/README where relevant.

## 2026-08-09 — Weak-label calibration design (`docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md`)

Reviewed via `codex exec -s read-only` (read-only, no edits). The full
critique is recorded below. These findings have not yet been incorporated.
Claude should evaluate each finding, record its disposition, and revise the
existing design spec in place before implementation.

1. **58 labeled studies is enough for a diagnostic audit, not for
   choosing between two fix candidates from point estimates.** Per-label
   positive counts will likely be single digits — precision/recall/F1
   will be unstable or undefined for some labels. Report TP/FP/FN/TN and
   support alongside any rate, with confidence intervals. Predefine the
   decision rule before looking at results — picking whichever fix looks
   better on the same 58 rows and then reporting "after" numbers on those
   same rows is optimistically biased (a multiple-comparisons trap).
2. **Aggregate precision/recall can't distinguish *why* extraction
   failed** (negation vs. wrong language vs. something else). Build an
   error taxonomy stratified by label × report-language × failure-cause,
   recording only counts on Kaggle — never raw text locally.
3. **Deeper semantic flaw than "no negation handling":** the current
   extractor detects an anatomical *mention*, not an *asserted
   abnormality* — `"ACL intact"` reads as a positive today with or
   without negation handling, because it matches on the anatomy keyword
   alone. Multilingual keyword expansion would amplify this flaw rather
   than fix it if applied first.
4. **Check whether the 58 labeled studies' report-language distribution
   resembles the 4349 unlabeled studies' before trusting any multilingual
   coverage decision generalizes** — if the labeled set skews toward one
   language, a fix validated only there may not transfer.
5. **Treat this pass as a go/no-go test, not "the" labeling strategy for
   1.3% supervision.** If precision/coverage/confidence intervals remain
   poor after one fix, stop iterating on regex and consider a
   fundamentally different approach (multilingual assertion-extraction,
   probabilistic weak supervision / multiple labeling functions à la
   Snorkel). Weak labels should be able to abstain (no evidence either
   way) rather than being forced to 0 for every unmatched report; the 58
   real human labels should stay distinguishable as higher-confidence
   data downstream.
6. **Data-leakage surface is broader than "don't paste report text into
   docs.**" Also guard: notebook outputs, exception tracebacks, cached
   artifacts, downloadable kernel output files, study identifiers in
   printed output, and accidentally publishing a notebook version with
   outputs attached. Clear outputs before any dataset/kernel publish;
   avoid near-paraphrase examples close enough to reconstruct real
   report text.
7. **Add schema validation**: missing/non-string `Report`, non-binary
   label values, duplicate `StudyInstanceUID`, partially-labeled rows.
8. **Naming**: "calibration" implies probability calibration, which this
   isn't — "weak-label evaluation" is more accurate.
9. **This is a proxy metric.** Binary precision/recall against the 58
   labels is not the real objective; the real question is whether
   weak-labeling improves the competition's actual macro-AUC on held-out
   human labels. Worth stating explicitly as a longer-term validation
   step, even if out of scope for this pass.

### Claude's disposition (discussed with user, 2026-08-09)

1. **Accept.** Report `tp/fp/fn/tn/support` per label, add a confidence
   interval (Wilson score or similar), and write the decision rule into
   the spec *before* the calibration notebook runs, not after.
2. **Accept.** Add an error-taxonomy cell (label × report-language ×
   failure-cause, counts only), kept on Kaggle.
3. **Accept — most important finding in the review.** Reframes "negation
   handling" as "assertion-status detection" (negation is the main
   mechanism, not the whole concept). Because Codex's own argument is
   that multilingual expansion would amplify this flaw if fixed first,
   the design's predefined decision rule (see #1) is biased toward
   assertion-detection as the default fix unless the baseline data
   clearly shows negation/assertion isn't the dominant error mode —
   rather than treating both candidate fixes as equally unproven going
   in.
4. **Accept.** Add a coarse per-report language-distribution comparison
   (58 labeled vs. a sample of the 4349 unlabeled), counts only, before
   trusting a multilingual fix would generalize.
5. **Partially accept — real scope fork, escalated to user.** "Go/no-go"
   framing and an explicit stop criterion: accepted, added to the spec.
   The **abstain-state change** (returning unknown instead of forced-0
   for a label with no textual evidence) is a real interface change —
   affects `split_labeled_studies` and every future weak-label consumer,
   not a tuning knob. Escalated to the user rather than decided
   unilaterally: fold it into this pass, or defer it to
   `docs/3_strategy.md` as the next decision once the false-zero rate is
   actually measured? **Awaiting user decision** as of this entry.
6. **Accept.** Tightens the constraint section (no committed outputs for
   this notebook, no report text in exception paths, etc.) — doesn't
   change the design's shape.
7. **Partially accept.** NaN-`Report` guard: accepted (cheap, matches
   existing `.dropna()` conventions elsewhere in the codebase).
   Partially-labeled rows: already correctly handled today —
   `split_labeled_studies` routes *any* missing label to the unlabeled
   bucket, not a gap. Duplicate `StudyInstanceUID` / non-binary label
   values: deferred as unlikely enough to not warrant handling in this
   pass; revisit if actually observed.
8. **Accept.** Rename "calibration" → "weak-label evaluation" throughout
   the spec's prose; module filename (`label_calibration.py`) left as-is
   unless the user prefers renaming the file too.
9. **Accept.** State explicitly as a caveat rather than leave implicit;
   remains out of scope for this pass (no trained model exists yet to
   test against).
