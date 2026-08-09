# Codex Review Log

Append-only: independent Codex CLI review of design specs, plans, and
milestones — a collaboration input, not an approved decision by itself.
Same workflow as `kaggriculture` and
`kaggle-s6e8-predicting-smartphone-addiction`: run by hand, findings
recorded here, cited from the plan/spec/README where relevant.

## 2026-08-09 — Weak-label calibration design (`docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md`)

Reviewed via `codex exec -s read-only` (read-only, no edits). Full
critique below; a revised design incorporating it is tracked as a design
update to the same spec, not a separate doc.

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
