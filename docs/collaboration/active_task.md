# Claude–Codex Active Task Log

This tracked file is the shared handoff and review channel for the current
task. Claude and Codex must read it before starting work and append
concise, evidence-based updates. Same pattern as
`kaggle-s6e8-predicting-smartphone-addiction`'s early (pre-Cursor) setup:
Claude implements, Codex reviews independently, findings get resolved here
before the next step starts.

## Workflow Rules

1. Work from the shared `main` checkout. Use a worktree
   (`superpowers:using-git-worktrees`) for a bounded implementation pass
   once a spec is approved — not for docs-only design/review iteration.
2. Before acting, read `git status`, recent `git log`, the relevant design
   spec or plan, and this file.
3. Claude drafts/revises the design (or implements the approved plan) and
   commits one coherent change.
4. Codex reviews project artifacts independently (`codex exec -s read-only`
   / `codex review`) without changing implementation, specification, or
   result files; the permitted review-side write is this collaboration log.
   **Every Codex review or feedback pass—including a clean confirmation with
   no findings—must be appended here as a clearly labeled, numbered Codex
   round and committed to the current task branch before handoff.** Feedback
   must never exist only in the chat transcript or as an uncommitted local
   change that Claude cannot discover from git history.
5. Claude addresses accepted findings in a separate fix/revision commit;
   never amend or rewrite a commit Codex already reviewed.
6. Do not begin implementation while findings or the user's approval
   decision remain unresolved.
7. When a task is fully accepted (spec approved and, once implemented,
   both reviews closed), move this file's record to
   `docs/collaboration/archive/YYYY-MM-DD-<task-name>.md` and start a
   fresh `active_task.md` for the next task.

## Current Task

- Spec: `docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md`
- Plan: `docs/3_strategy.md` — Phase 2
- Task: Weak-Label Evaluation — final documentation and strategy review
- Status: **Round 15's documentation findings fixed (commit `8e346b0`);
  user chose Phase 3 strategy A (honest baseline-first) on 2026-08-09,
  recorded in `docs/3_strategy.md`.** Kernel v2 completed and the
  predefined gate produced an accepted **No-go** verdict (0/12 labels).
- Remaining: the user's own Codex confirmation of the round-15 fix commit
  (`8e346b0`) before this file archives, per workflow rule 7 and round
  15's own gating language — not self-certified here, per the user's
  standing preference that they run subsequent Codex passes themselves.
  Once confirmed, archive this file to
  `docs/collaboration/archive/2026-08-09-weak-label-evaluation.md` and
  start a fresh `active_task.md` for the Phase 3 baseline-modeling design.

## Review Thread

### Round 1 — Codex review of the initial design (2026-08-09)

Reviewed via `codex exec -s read-only` (read-only, no edits).

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

### Round 2 — Codex follow-up on Claude's disposition (2026-08-09)

Claude's disposition addresses all nine findings, but four points need
resolution before the design is ready for implementation:

1. **Include abstention in this pass.** There are no downstream
   weak-label consumers yet, so this is the least disruptive time to
   establish the correct three-state contract: positive, negative, or
   unknown. Absence of textual evidence must not be interpreted as a
   negative assertion. This change does not require changing
   `split_labeled_studies`; that function separates rows by human-label
   completeness and does not consume the extractor's output. It does
   require updating `extract_weak_labels`'s return type and its tests.
2. **Do not defer basic evaluation-schema validation.** Duplicate study
   IDs, non-binary ground-truth values, or partially labeled input can
   silently invalidate metrics. `weak_label_metrics` should reject these
   conditions, as well as missing or non-string reports, even when an
   upstream splitter normally prevents them. These checks are
   inexpensive and belong at the evaluation boundary.
3. **Rename new artifacts consistently.** The proposed module, notebook,
   and kernel do not exist yet, so use `weak_label_evaluation.py`,
   `02_weak_label_evaluation.ipynb`, and `weak-label-evaluation` now
   rather than retaining "calibration" in filenames and creating
   terminology debt.
4. **Make the decision rule concrete in the revised spec.** "Wilson
   score or similar" and an unspecified stop criterion are not
   predefined decisions. The spec must name the interval method, define
   coverage and support, state the thresholds or comparison rule, and
   explain what result triggers a stop or a move away from regex-based
   extraction before the Kaggle run.

The design spec itself still described the original binary
keyword-matching approach at this point. Next action: Claude incorporates
the accepted findings and the resolutions above into that existing spec.

### Claude's incorporation (2026-08-09)

All four round-2 points accepted — the abstention argument in particular
(no downstream consumers yet, so this is the cheapest point in the
project's life to fix the contract) is correct and was underweighted in
the original disposition. The spec at
`docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md` was
rewritten in place (not a new file) to incorporate all of it:

- `extract_weak_labels` return type becomes `dict[str, int | None]`
  (`None` = abstain), with the assertion-detection mechanism (negation-
  cue window) as the actual fix — no longer framed as "choose between
  two candidate fixes from baseline numbers."
- `weak_label_metrics` (the function name is unchanged; only its module
  moves from `label_calibration.py` to `weak_label_evaluation.py`) now
  defines confusion counts explicitly against the 3-state contract,
  validates its input (raises on duplicate `StudyInstanceUID`, non-binary
  label values, missing/non-string `Report`) rather than deferring those
  checks, and computes a Wilson score 95% CI per label.
- Concrete, named decision rule: Wilson interval via
  `statsmodels.stats.proportion.proportion_confint(method="wilson")`;
  adequate support = `>= 5` in the relevant confusion-count denominator;
  go/no-go gates on **precision** (chosen over recall as primary,
  reasoned in the spec: false positives corrupt pseudo-labels, missed
  positives are comparatively recoverable once a future training
  pipeline can treat abstain as "no signal") — go if `>= 4` of 12 labels
  reach adequate support and macro-average precision across them is
  `>= 0.7`, no-go otherwise. These three numbers (`5`, `0.7`, `4/12`) are
  stated in the spec as reasonable-but-adjustable defaults, not derived
  from this project's actual data (which isn't measured yet).
- Module/notebook/kernel renamed throughout:
  `label_calibration.py` → `weak_label_evaluation.py`,
  `02_weak_label_calibration.ipynb` → `02_weak_label_evaluation.ipynb`,
  `weak-label-calibration` kernel → `weak-label-evaluation`.
- Output-free notebook policy and broader leakage-surface guardrails
  (round 1 finding 6, already accepted) folded into the Constraint
  section.

Committed as `5a0e7f7`, returned for user approval / further review.

### Round 3 — Codex review of Claude's incorporation (2026-08-09)

**Reviewed commit:** `5a0e7f7` (`docs(spec): revise weak-label evaluation
design per Codex review round 2`)

**Verdict: Revision required.** Claude incorporated the four round-2
recommendations, but the revised spec has five remaining design problems:

1. **The baseline/after data flow is impossible as written.** The
   notebook is instructed to evaluate the current pre-fix extractor,
   then the fixed extractor, but it is also instructed to publish the
   already-fixed package before the notebook's first run. Both
   implementations must be available from the same published package
   through an explicit, tested interface (for example, two extractor
   callables passed to `weak_label_metrics` or a frozen legacy mode);
   the notebook cannot recover pre-fix behavior from an overwritten
   implementation.
2. **The assertion detector still misses the review's own `"ACL
   intact"` example.** A window immediately *before* the anatomy keyword
   can find `"no fracture"`, but not post-keyword normality assertions
   such as `"ACL intact"` or `"meniscus preserved"`. The design must
   specify clause-scoped cues on both sides of a match and deterministic
   resolution when one report contains multiple or conflicting mentions.
3. **The metric's `support` definition is internally inconsistent.**
   The spec defines `FN` to include abstained true positives, then calls
   `TP + FP + FN + TN` the non-abstained row count. Those statements
   cannot both be true. Report separate, unambiguous quantities:
   actual-positive support (`TP + FN`), predicted-positive support
   (`TP + FP`), non-abstained count, and total rows; use each metric's
   actual denominator for its confidence interval.
4. **Dependency and language-detection choices remain unresolved.** The
   spec says to add `statsmodels` to either `dev` or a new optional
   group and incorrectly calls it a scikit-learn transitive dependency;
   it is absent from both `pyproject.toml` and `uv.lock`. Choose one
   offline-safe approach, preferably the small Wilson formula implemented
   directly unless an explicit runtime dependency is justified.
   Likewise, non-ASCII fraction cannot distinguish the observed
   Latin-script languages, and `"langdetect-style"` is not an
   implementable offline specification; select one deterministic method
   and declare how it reaches Kaggle.
5. **The go/no-go gate does not use the confidence intervals added for
   small-sample uncertainty.** It gates on macro-average point
   precision. Either incorporate a defined lower confidence bound into
   the decision or explicitly make the intervals descriptive and justify
   why the point-only heuristic is sufficient. Thresholds may be changed
   during user review, but must be frozen before any real result is
   viewed.

**Next action:** Claude revises the existing spec to resolve these five
items and returns it for user approval. No implementation plan or code
work should begin before that approval.

### Round 4 — Discussion before revision (2026-08-09)

Claude accepted round 3 findings 1 and 3 outright (no discussion needed).
For findings 2, 4, and 5, Claude proposed counter-resolutions and asked
Codex to respond specifically (via `codex exec -s read-only`) before
writing the revision, rather than implementing unilaterally.

**Finding 2 (assertion detector) — Codex: Refine, accepts the bounded
scope.** Agreed a deliberately simple resolver is adequate for a
diagnostic go/no-go pass, on two conditions:

- The window must be genuinely clause-scoped — stop at punctuation/
  newline boundaries with a fixed maximum distance, so a cue belonging
  to an adjacent finding can't leak across clauses and get misattributed
  (a real gap in Claude's original "30 characters" window, which had no
  clause boundary).
- Explicit resolution hierarchy per label, per report:
  - Only unqualified abnormal mention(s) → `1`.
  - Only negated/normal-asserting mention(s), or those plus unqualified
    mentions → `0` (negated and normal-asserting mentions don't conflict
    with each other; both support `0`).
  - An explicit abnormal assertion *and* a negated/normal-asserting
    mention for the *same* label in the *same* report → `None`
    (abstain), logged to the error taxonomy as ambiguous rather than
    silently picked.
  - No mention at all → `None` (already agreed in round 2).
- Add synthetic tests for: post-match cues, cue leakage across clauses,
  repeated concordant mentions, and an explicit abnormal-vs-normal
  conflict case.

**Finding 4 (dependency/language-detection) — Codex: Agree with
refinement.** Direct closed-form Wilson interval implementation
confirmed preferable to adding `statsmodels` — "small, deterministic,
offline-safe, and readily testable against known values." The language
heuristic is accepted only if honestly framed as an **orthographic/
script bucket**, not language identification: Greek via Unicode script,
German/Turkish/Croatian via characteristic Latin diacritic characters,
with overlapping/missing diacritics bucketed as "other/undetermined
Latin" rather than a false-confident specific-language guess. Compare
the same deterministic buckets between the 58 labeled and a sample of
the 4349 unlabeled studies, and state this limitation explicitly in the
spec/notebook rather than implying real language ID.

**Finding 5 (go/no-go ignoring CIs) — Codex: Refine, with a materially
different gate structure.** Confirmed: gate on the Wilson **lower
bound**, not the point estimate. Two changes beyond what Claude proposed:

- **Threshold: lower bound `>= 0.55`** (not Claude's tentative
  `0.55-0.6` range), calibrated directly against the `support >= 5`
  threshold's own achievable range: at `n=5`, even a flawless `5/5`
  result has a Wilson lower bound of only ≈`0.566`; at `n=6`, `6/6`
  ≈`0.610`; at `n=8`, `7/8` ≈`0.529`. A `0.60` threshold would make
  `support >= 5` internally self-contradictory — it would claim 5
  examples are enough evidence while requiring a bound that even
  zero-error evidence at that sample size usually can't clear.
- **Drop the macro-average gate entirely.** Require `>= 4` labels to
  **each individually** pass their own lower-bound threshold, rather
  than averaging lower bounds across labels — "averaging lower bounds
  could let strong labels conceal an untrustworthy label that would
  still be used downstream." This is a real structural change from
  Claude's original proposal (aggregate macro-average), not just a
  different number.

**Codex's verdict:** "The design is ready for Claude's final revision
with these Finding 2, 4, and 5 refinements incorporated." No remaining
open questions from Codex's side.

**Next action:** Claude writes the final spec revision incorporating
round 3 findings 1 and 3 as originally specified, and findings 2, 4, and
5 exactly as refined above. Returns for a final confirmation pass before
user approval and before `writing-plans`.

### Round 5 — Final confirmation (2026-08-09)

Claude wrote the full revision (commit `efa6422`), incorporating rounds
3 and 4 completely, but flagged one open question inline in the spec
rather than resolving it unilaterally: round 4's 4-way resolution
hierarchy included a distinct "explicit abnormal assertion + negated/
normal-asserting mention → `None`, ambiguous" case, but Claude's
implementation only has two mention categories (qualified/unqualified),
collapsing that case into "qualified dominates → `0`". Sent to Codex for
direct resolution via `codex exec -s read-only`.

**Codex's resolution: accept the two-category simplification (option
a).** The existing `_LABEL_PATTERNS` provide no defensible way to
distinguish a "bare mention" from an "explicit abnormal assertion." A
real third category would need its own positive-assertion vocabulary
(`tear`, `rupture`, `sprain`, `identified`, `present`) plus label-
specific grammatical proximity rules — a materially broader, speculative
extractor design not justified for this bounded pass. Treating an
inherently-abnormal keyword like `fracture` as automatically "explicit"
would also misclassify `"no fracture"` unless qualification were
evaluated first, so the distinction isn't even a clean addition on top
of the existing mechanism. Spec updated to state this as an accepted
simplification, not an open question.

**Two real defects found in the broader final check:**

1. **The Wilson formula's variance term was missing a factor of `1/n`.**
   As written it did not reproduce the claimed `5/5 ≈ 0.566` lower
   bound. Corrected to the standard `p_hat`-based closed form; verified
   by hand that `n=5, k=5` now gives `lower ≈ 0.5655`, matching the
   figure already cited in the decision-rule section. The unit test for
   this formula should check this exact reference value first.
2. **`total_rows` was defined as a required support quantity but
   omitted from the documented returned DataFrame columns.** Added.

Minor: a stale "section 4" cross-reference (should have been "section
5", the error-taxonomy section) fixed in two places.

**Codex's verdict on the rest of the revision:** confirmed correct —
the two-named-extractors design resolves finding 1; the four support
quantities are self-consistent (finding 3); the go/no-go gate matches
round 4 exactly (per-label Wilson lower bound `>= 0.55`, support `>= 5`,
`>= 4/12` labels, no macro-average); the language check is honestly
framed as orthographic buckets, not language ID.

**Next action:** Claude fixes the two defects (done, this same pass) and
returns the spec to the user for approval. If approved, next step is
`superpowers:writing-plans` — no code work starts before that approval.

### Round 6 — Fresh pre-implementation review (2026-08-09)

**Reviewed commit:** `6d60dac` (`docs(spec): resolve round 5 Codex
findings, design ready for approval`)

**Verdict: Revision required.** The round-5 fixes are present and the
Wilson/support definitions are now internally consistent, but a fresh
review found five remaining design problems:

1. **The clause/cue algorithm still has incorrect assertion semantics.**
   Splitting on `:` separates a common heading form such as `"ACL: intact"`
   into `"ACL"` and `"intact"`; the keyword's clause then has no cue and is
   incorrectly labeled `1`. The cue contract also puts `"rule out"`
   (uncertain indication, not a confident negative finding) in the same
   category as `"no"` and `"intact"`, forcing it to `0`, and does not state
   that short cues such as `no`/`not` use token boundaries. Revise the
   mechanism so heading separators retain their associated value, match cues
   as bounded words/phrases, and map uncertainty cues to abstain rather than
   confident negative. Add explicit tests for `"ACL: intact"`, `"rule out
   fracture"`, and substring traps such as `"notable"`.
2. **A global `GO` is unsafe when only 4 of 12 labels pass.** The rule can
   declare the extractor viable even though eight labels are unsupported or
   fail their individual precision gate. Define and persist the exact
   per-label allowlist. `GO` may authorize future weak labeling only for
   labels that individually pass; failed or unsupported labels must remain
   abstained/unavailable downstream. The experiment and strategy docs must
   record both the overall verdict and this allowlist.
3. **`weak_label_metrics` does not fully protect its callable boundary.**
   Because it accepts an arbitrary extractor, it must validate that every
   extractor result has exactly `LABEL_COLUMNS` and only values in
   `{0, 1, None}`. It should also explicitly validate missing required input
   columns and empty evaluation input, rather than relying on incidental
   `KeyError`/zero-row behavior. Use a return type such as
   `Mapping[str, int | None]` so the frozen `dict[str, int]` naive extractor
   satisfies the declared callable contract without an invariant-`dict`
   typing conflict. Add tests for each rejected contract violation.
4. **The proposed error taxonomy is not operationally defined.** With the
   fixed extractor, `no-keyword-match` and `abstained-on-true-positive` are
   the same event, while causes such as
   `qualified-when-should-be-unqualified` cannot be inferred from a truth/
   prediction pair alone. The no-raw-text-output rule also removes the only
   obvious inspection path. Define mutually exclusive, mechanically
   derivable categories, or specify a Kaggle-only manual classification step
   that allows transient inspection but emits only aggregate counts. Include
   an `unknown/report-label-disagreement` category rather than assuming every
   mismatch is caused by cue classification.
5. **The orthographic comparison is underspecified and overclaims some
   buckets.** `ö`/`ü` are shared by German and Turkish, and the listed
   Croatian characters also occur in other South Slavic languages, so
   language-named buckets can still imply false identification despite the
   disclaimer. Rename them after the observed script/character sets rather
   than languages. Also evaluate all 4,349 report-only rows: the spec gives
   no sample size or selection rule, and a full scan of CSV report strings is
   inexpensive and removes sampling noise.

**Next action:** Claude revises the existing spec to resolve all five items,
then returns the revision for another Codex confirmation. User approval and
implementation planning remain blocked until that review closes.

### Claude's assessment of round 6 (2026-08-09)

Agree with all five findings. Findings 1, 2, 3, and 5 have clear fixes,
no discussion needed:

1. Drop `:` from the clause-boundary character set (fixes `"ACL:
   intact"`); add an "uncertain" cue category (`"rule out"`, `"r/o"`,
   `"question of"`, `"possible"`, `"cannot exclude"`) that maps to
   abstain, not confident-negative; require word-boundary matching on
   all cues (fixes the `"notable"` substring trap).
2. Replace the global boolean go/no-go with a **persisted per-label
   allowlist** — only labels that individually pass their own gate are
   usable downstream; failed/unsupported labels stay abstained
   regardless of how many other labels passed.
3. Validate the extractor's *output* in `weak_label_metrics` (exactly
   `LABEL_COLUMNS` keys, values in `{0, 1, None}`), validate missing
   input columns and empty input explicitly, and type the extractor
   parameter as `Mapping[str, int | None]` so the naive extractor's
   `dict[str, int]` satisfies it cleanly.
5. Rename orthographic buckets after character sets, not language names
   (`ö`/`ü` are shared by German and Turkish, not German-exclusive as
   originally bucketed); scan all 4349 unlabeled reports instead of an
   unspecified "sample."

Finding 4 (the error taxonomy isn't mechanically derivable) has a
genuine design fork. Sent to Codex for a direct recommendation
(`codex exec -s read-only`, round 7) rather than picking unilaterally:
(a) have the mention-resolution mechanism expose its internal
classification as a diagnostic structure, so taxonomy categories become
mechanically derivable with no raw text ever touched, vs. (b) a bounded,
explicitly-permitted Kaggle-only manual triage step (transient
inspection, aggregate counts only committed).

### Round 7 — Codex recommendation on the taxonomy design fork (2026-08-09)

**Recommends option (a)**, firmly rejecting (b): "irreproducible,
introduces reviewer judgment at exactly the smallest and most
consequential sample, and makes leakage prevention depend on notebook
discipline." Manual inspection may be a fine follow-up *after* a no-go
result, but should not define this evaluation's committed taxonomy.

Confirms (a) is achievable without repeating round 5's rejected
"speculative third category" problem — recording classifications the
resolver already computes internally is materially simpler than
inferring new semantic categories requiring new vocabulary/grammar.

Concrete design (adopted as specified):

- `extract_weak_labels(text) -> dict[str, int | None]` keeps its public
  interface exactly as already designed — a thin wrapper that projects
  just the final value.
- An internal resolver exposes, per label, a `LabelResolution` (the
  final `value` plus a tuple of `MentionDiagnostic`), where each
  `MentionDiagnostic` records only `kind` (one of `unqualified`,
  `qualified_negation`, `qualified_uncertain`,
  `qualified_normal_assertion`) and `clause_index` — no clause text,
  matched text, offsets, study identifiers, or cue strings retained.
  Empty `mentions` tuple = `no_mention`.
- The notebook's diagnostic cell calls the internal resolver directly
  (not the public wrapper) to get this richer structure, and buckets
  errors by `(label, orthographic_bucket, prediction_error,
  resolution_signature)`, where `resolution_signature` is one of
  `no_mention`, `unqualified_only`, `negation_qualified`,
  `normal_qualified`, `uncertain_qualified`, `mixed_qualification`.
- Includes `unknown/report-label-disagreement` as the bucket for
  mismatches whose resolution signature can't mechanically establish a
  cause (most notably an `unqualified_only` false positive — the
  extractor found a plain, unqualified mention but ground truth says
  negative, which the resolver-level signature alone can't explain) —
  "avoids pretending that ground truth proves what the report
  asserted."

**Next action:** Claude writes the full spec revision incorporating
round 6 findings 1/2/3/5 as agreed and finding 4 exactly per round 7's
adopted design. Returns for another Codex confirmation pass before user
approval.

### Round 8 — Final confirmation (2026-08-09)

**Reviewed commit:** `ed476bb` (`docs(spec): incorporate Codex round 6-7
findings into weak-label evaluation design`)

**Verdict: READY for user approval and implementation planning via
`superpowers:writing-plans`. No further revision round warranted.**

Confirmed all five round-6 items and the round-7 taxonomy design are
correctly implemented in the spec:

1. Clause/cue semantics — `:` excluded from clause boundaries;
   uncertainty is a distinct category resolving to `None`; all cues use
   bounded phrase/token matching, including special handling for `r/o`.
2. Per-label gate — `passes_gate` computed independently per label (no
   macro-average); sections 6-7 explicitly print/persist the allowlist,
   not an overall boolean; failed/unsupported labels stay unavailable
   downstream regardless of how many others pass.
3. Callable boundary — extractor output validated (exact keys, values
   in `{0, 1, None}`) on every call; `Mapping` typing correctly accepts
   the naive extractor's `dict[str, int]`; missing columns and empty
   input explicitly rejected.
4. Taxonomy design — `LabelResolution`/`MentionDiagnostic` retain only
   abstract kinds and clause indices, never text/matches/offsets/cues/
   identifiers; `resolution_signature` mechanically derived from the
   mention-kind set; `unknown/report-label-disagreement` correctly
   scoped to unexplainable mismatches.
5. Orthographic buckets — renamed names accurately describe character
   sets without overclaiming language identity; full 4349-row scan
   specified, no sampling.

Broader check also passed: section cross-references consistent,
section 2's resolution-order priority is deterministic, and the
round-5 Wilson formula/reference value/support definitions/`total_rows`
all survived this revision intact.

**Next action:** Present the design to the user for approval. If
approved, proceed to `superpowers:writing-plans` — this task moves out
of pure design/review after 8 rounds with no outstanding findings.

### Round 9 — Independent progress check and active-log discussion (2026-08-09)

**Reviewed commits:** `37210c0` (round-6/7 discussion), `ed476bb` (spec
revision), and `c7c31ce` (round-8 confirmation).

**Progress verified:** Claude incorporated every blocking round-6 finding
into the actual spec:

1. `:` is no longer a clause boundary; uncertainty has a distinct abstain
   path; cue matching is word/phrase bounded; the required regression cases
   are listed for testing.
2. The global boolean gate is replaced by a persisted per-label allowlist;
   failed and unsupported labels remain unavailable downstream.
3. `weak_label_metrics` validates required columns, non-empty input,
   duplicates, reports, labels, and every extractor result; its callable
   uses `Mapping[str, int | None]`.
4. The error taxonomy is mechanically derived from text-free
   `LabelResolution`/`MentionDiagnostic` structures and includes an unknown/
   report-label-disagreement outcome rather than inventing a cause.
5. Orthographic buckets describe character sets rather than claiming
   language identity, and the comparison covers all 4,349 report-only rows.

**Verdict: Ready for user approval and implementation planning.** No
blocking design revision is required. Two non-blocking interface details
must be made explicit in the implementation plan:

- Give the internal resolver a concrete name and signature (for example,
  `_resolve_weak_labels(report_text: str) -> dict[str, LabelResolution]`),
  because the notebook diagnostic cell calls it directly even though the
  current spec defines only its returned dataclasses.
- Define where `unknown/report-label-disagreement` lives in the taxonomy
  schema. The stated tuple currently has only `(label, orthographic_bucket,
  prediction_error, resolution_signature)`, while that unknown outcome is
  neither one of the listed `resolution_signature` values nor a separate
  field. The plan should add an explicit `failure_cause` field or make it a
  named signature value, with mutually exclusive assignment rules.

**Next action:** User reviews and approves or rejects the design. If
approved, invoke `superpowers:writing-plans`; carry the two clarifications
above into the plan before any implementation task begins.

### Claude's incorporation of round 9 (2026-08-09, commit `fbd33a0`)

Resolved both non-blocking gaps directly in the spec rather than
deferring them to the implementation plan, since both had unambiguous,
mechanically-derivable resolutions:

- **Named the resolver**: `_resolve_weak_labels(report_text: str) ->
  dict[str, LabelResolution]`, documented in section 2 alongside the
  `LabelResolution`/`MentionDiagnostic` dataclasses it returns.
  `extract_weak_labels` is now spelled out as a thin projection over it.
- **Taxonomy schema**: worked out that, given the resolution order
  already specified in section 2 step 6, every `resolution_signature`
  except `unqualified_only` can only ever produce a false negative (the
  resolver never resolves to `0` or `None` from a state that could also
  reach `1`), and `unqualified_only` can only ever produce a false
  positive. `prediction_error` and `failure_cause` are therefore a fixed
  lookup from `resolution_signature` alone, not independent fields — the
  redundancy round 9 flagged. `unknown/report-label-disagreement` falls
  out of this table as exactly `unqualified_only`'s failure cause, which
  resolves the placement ambiguity by construction rather than as a
  bolted-on special case. Added a test requirement pinning this
  invariant so a future change to the resolution order can't silently
  invalidate the table.

Per the user's explicit preference (2026-08-09), Claude will not invoke
`codex` on this spec further — the user runs subsequent Codex reviews
themselves. This revision is presented for the user's own review
(directly or via their own Codex run), not auto-submitted for another
round.

**Next action:** User reviews and approves or rejects the design
(commit `fbd33a0`). If approved, invoke `superpowers:writing-plans`.

### Round 10 — Codex check of Claude's round-9 incorporation (2026-08-09)

**Reviewed commits:** `fbd33a0` (`docs(spec): resolve round 9's two
non-blocking interface gaps`) and `905301c` (Claude's incorporation note).

**Progress verified:** The first round-9 gap is resolved correctly.
`_resolve_weak_labels(report_text: str) -> dict[str, LabelResolution]` is
now a named interface, `extract_weak_labels` is explicitly its thin public
projection, the notebook calls the resolver by name, and direct resolver
tests are required. No implementation artifacts exist yet; the repository is
still in design review.

**Verdict: Focused revision required before user approval.** The second gap
has a remaining semantic error. The new table correctly proves that a
`resolution_signature` constrains the extractor's **output** and therefore
the possible error direction: `unqualified_only` can yield a false positive,
while signatures resolving to `0`/`None` can yield a false negative. It does
not prove the **cause** of disagreement with the human label. For example,
`negation_qualified` plus truth `1` could be a cue-scope error, a genuine
report/label disagreement, or a mismatch between report wording and the
competition target; the abstract signature alone cannot establish
`negation_cue_misfire`. The same limitation applies to
`normal_assertion_cue_misfire`, `mixed_qualification_miss`, and the other
causal labels.

Required correction:

1. Keep `resolution_signature` as the mechanically derived taxonomy axis and
   compute `prediction_error` directly from prediction versus truth.
2. Rename `failure_cause` to a non-causal field such as
   `diagnostic_interpretation` or remove it. Any displayed descriptions must
   say what the resolver observed, not claim why the human label disagreed.
3. Treat possible causes as hypotheses for follow-up, or use an
   `unknown_cause` value for every mismatch unless a future approved manual/
   semantic audit supplies additional evidence.
4. Test only the real invariant (signature → resolver value / possible error
   direction), not a signature → causal explanation mapping.

**Next action:** Claude makes this narrow terminology/schema revision in the
existing spec and returns it for Codex confirmation. Do not start
`superpowers:writing-plans` or implementation before that confirmation and
the user's approval.

### Claude's incorporation of round 10 (2026-08-09, commit `aa69a98`)

Agreed with round 10 in full — no pushback. Recognized it as the same
overclaiming mistake already caught once before (round 6's orthographic
buckets naming a language when the character evidence didn't support
that specific a claim), recurring here in a new place: a
`resolution_signature` is a real, mechanical, provable fact about which
mention kinds the resolver observed, but naming its typical pairing
`negation_cue_misfire` asserted a specific *cause* the signature alone
cannot establish (could equally be a real report/label disagreement, or
a report-wording/target-definition mismatch, not a cue bug at all).

Resolution: took the "or remove it" branch of round 10's point 2 rather
than renaming `failure_cause` to a neutral placeholder — a field that
would just read `unknown_cause` on every row isn't informative. Taxonomy
bucketing key is now `(label, orthographic_bucket, resolution_signature,
prediction_error)`; `prediction_error` is computed directly from
prediction-vs-truth (point 1), not derived through the signature, even
though the two remain related by construction. The invariant test now
only claims what's provable — signature constrains error *direction*,
not error *cause* (point 4). Any causal hypothesis is explicitly
relocated to `docs/4_experiments.md`'s prose write-up, hedged as
unconfirmed (point 3).

Per the user's stated preference, Claude did not invoke `codex` on this
revision. Presented for the user's own review/Codex round.

**Next action:** User reviews and approves or rejects the design
(commit `aa69a98`). If approved, invoke `superpowers:writing-plans`.

### Round 11 — Codex confirmation of round-10 incorporation (2026-08-09)

**Reviewed commits:** `aa69a98` (`docs(spec): remove causal failure_cause
labels from error taxonomy`) and `ca3b9c8` (Claude's incorporation note).

**Progress verified:** All four round-10 requirements are reflected in the
spec. The taxonomy key is now `(label, orthographic_bucket,
resolution_signature, prediction_error)`; prediction error is computed from
prediction versus truth; causal `failure_cause` values are gone; possible
causes are explicitly treated as unconfirmed follow-up hypotheses; and the
required invariant test is limited to signature → resolver value / possible
error direction. The named `_resolve_weak_labels` interface from round 9
also remains intact. No implementation artifacts exist yet.

**Verdict: Ready for user approval and `superpowers:writing-plans`.** The
round-10 semantic issue is closed. One non-blocking editorial cleanup should
be made when the spec is next touched: section 5's introductory paragraph
still says the resolver can explain *why* extraction failed and makes that
explanation mechanically derivable. The corrected text later in the same
section accurately says the resolver only stratifies what it observed and
cannot establish cause. Rephrase the introduction to say "how the resolver
behaved on errors" rather than "why extraction failed" so the section is
internally consistent. This wording does not alter an interface, metric,
decision rule, or implementation task, so no additional review round is
required solely for it.

**Next action:** User approves or rejects the design. If approved, Claude
may make the noted wording cleanup and then invoke
`superpowers:writing-plans`; implementation begins only after that plan is
reviewed.

### Design approved (2026-08-09)

User: "I have review the specs and approve that." No further discussion
raised on round 11 (the wording cleanup is trivial and undisputed).
Claude applied the cleanup directly (section 5's intro now says "how the
resolver behaved on errors," matching the corrected body text, rather
than "why extraction failed").

**11 rounds of review, final state:** two named extractors resolving
the before/after data-flow problem; a 3-state (positive/negative/
abstain) `extract_weak_labels` contract with clause-scoped, bidirectional,
word-bounded, three-category (negation/normal-assertion/uncertain) cue
detection; a named `_resolve_weak_labels` internal resolver exposing
mechanically-derivable diagnostics with zero raw-text retention; a
per-label persisted allowlist (not a global boolean) gated on a Wilson
lower-bound precision threshold calibrated to its own support
requirement; and a purely observational error taxonomy that stops short
of claiming causes it can't establish.

**Next action:** Invoke `superpowers:writing-plans` to turn this
approved design into an implementation plan.

### Implementation (2026-08-09)

Plan: `docs/superpowers/plans/2026-08-09-weak-label-evaluation.md`. Executed
via `superpowers:subagent-driven-development`, worktree
`worktree-weak-label-evaluation`. Progress ledger:
`.superpowers/sdd/progress.md` (full task-by-task detail; summarized here).

- **Task 1** (`d5ab1b5`) — `extract_weak_labels` rewrite. Reviewer
  independently hand-traced 5 subtle regex/clause cases. Clean.
- **Task 2** (`d5ab1b5..d2db2f0`) — `weak_label_metrics` /
  `orthographic_bucket`. Implementer found (did not silently fix) a real
  bug: `re.IGNORECASE` case-folds Turkish dotted-capital İ to ASCII i/I,
  making the "Turkish characters" regex spuriously match ordinary English
  text like "MRI". Fixed with explicit case variants instead of
  IGNORECASE, independently re-verified by the reviewer against all 7
  fixture strings plus cross-pattern contamination between the three
  diacritic regexes. Clean.
- **Task 3** (`ed136f3`) — notebook + kernel-metadata scaffold
  (transcription task, complete JSON given verbatim in the brief).
  Reviewer byte-diffed the committed files against the brief. Clean.
- **Task 4** (`ed136f3..51ebd66`) — final verification, done directly
  (no reviewer needed — verification-only). Found the notebook (as the
  plan specified it verbatim) failed `ruff check .` (unsorted import, 2
  lines >100 chars); fixed (`cc47b8c`). That fix's own tooling then
  collapsed 2 cells' `"source"` field to a single string, diverging from
  the notebook's list-of-lines convention; corrected (`51ebd66`).
- **Final whole-branch review** (opus, range `279810c..51ebd66`) —
  "Ready to merge: With fixes." Found one **Important** bug:
  `_classify_mention` searched a *sliced* text window for cues, so
  slicing mid-word manufactured word boundaries the source text doesn't
  have — "abnormal" cut at the window edge could leak a false "normal"
  cue; "cannot"/"nodular"/"notable" similarly leaked "not"/"no". One-way
  (`unqualified → qualified`, i.e. inflates false negatives, never false
  positives), but real. Also flagged: no test ever composed the real
  extractors with `weak_label_metrics` (only synthetic ones), and
  `_validate_extractor_output` silently accepted `bool`/`float` via
  Python's `in`/`==` semantics.
- **Fix** (`136c55e`) — replaced the slice-and-search with a
  `_has_cue_in_window` helper that runs `finditer` over the whole clause
  and span-filters matches into the window bounds (no slicing, no
  manufactured boundaries); added the two missing composition tests;
  tightened the value check to `type(value) is int`.
- **Re-review** (opus, range `51ebd66..136c55e`) — "Ready to merge: Yes."
  Independently re-derived the fix via a 30,000-clause differential fuzz
  test (new cue-set ⊆ old cue-set in 100% of cases, zero genuine-cue
  losses), confirmed window bounds bit-identical to the pre-fix formula,
  validated the bool/float truth table. One nit: the regression test's
  single fixed padding only actually exercised the bug for 1 of 4 trap
  words. Fixed (`cc29435`) — swept a padding range, verified non-vacuous
  for all 4 words against a standalone copy of the pre-fix logic before
  applying.
- **Result:** 55 tests passing, `ruff check .` clean. PR opened:
  https://github.com/tuannm3812/kaggle-rsna-knee-abnormality-detection/pull/1
  (this repo's first-ever push — `main` had never been pushed to
  origin either; pushed both and fixed GitHub's default-branch setting
  as part of opening the PR).

### Discussion before user's own Codex review (2026-08-09)

User asked what's worth flagging before running their own Codex review
(per the workflow: user runs Codex themselves, see the note in "Current
Task" history / project memory). Points raised:

**Already fixed and re-verified across 2 review rounds** — re-flagging
these would be re-litigation: the window-slicing bug above; the missing
composition tests; the lax bool/float validation.

**Deferred on purpose, not overlooked:**
- `docs/2_eda_insights.md` and `docs/3_strategy.md` still describe the
  pre-this-branch design (naive-only extractor; go/no-go framing instead
  of the approved per-label allowlist). Real-numbers entries and doc sync
  wait for the actual Kaggle run — writing them now would mean
  fabricating results.
- The plan document's verbatim notebook JSON has drifted slightly from
  what's actually committed (the ruff-fix diff wasn't back-ported into
  the plan's Step 1 block). Historical-record drift, not a behavioral
  issue.
- English-only cue lists misfiring on some non-English reports (e.g.
  Turkish "not" as a common word) is accepted spec scope — the
  orthographic-bucket taxonomy exists specifically to surface this later,
  not to prevent it now.

**Genuinely open, not yet resolved by review:**
- The notebook has not been run on Kaggle. Everything verified so far is
  logic-correctness (does the code do what the spec says), not "does this
  extractor work well enough on real reports" — the actual
  precision/recall/coverage numbers and resulting allowlist are unknown
  until that run happens.
- `_wilson_interval`'s `n=0 → (0.0, 0.0)` convention is spec-mandated and
  internally consistent, but prints as a confident zero rather than
  "undefined" in the metrics table. Not a bug, but a live UX judgment
  call for however the eventual results table gets presented.

### Round 12 — Codex review of the implementation plan (2026-08-09; recovered after merge)

This review was performed against plan commit `279810c` before Claude's
implementation, but it existed only as an uncommitted change in the shared
`main` checkout and therefore was not visible inside Claude's linked
worktree. It is restored here so the audit trail includes every Codex
feedback round and so the apparent chronology in the two worktrees is
explicit rather than silently rewritten.

**Findings and their eventual disposition:**

1. The planned Turkish-character regex used Unicode `re.IGNORECASE`, which
   makes dotted-capital `İ` case-fold to ordinary ASCII `i/I`. Codex
   reproduced misclassification of both `"Normal knee MRI"` and
   `"plain ascii"`. Claude independently encountered the same failure during
   implementation and fixed it in `d2db2f0` with explicit case variants and
   no `IGNORECASE`. **Resolved.**
2. The plan stopped at notebook scaffolding and excluded the approved
   Kaggle run plus the required `docs/4_experiments.md` and
   `docs/3_strategy.md` result entries. Claude's merged discussion now
   acknowledges these as pending, but they have not happened. They remain
   required within this active task. **Open.**
3. The plan's intermediate test counts and final history assertion were
   internally inconsistent. The progress ledger records the actual counts
   and commit history; the historical plan itself still contains stale
   expectations. **Operationally resolved; historical-plan drift retained.**
4. The plan expected an empty shared-worktree status even though `.claude/`
   was already present. Claude used a clean linked worktree; Codex preserved
   `.claude/`, which is the linked-worktree container, and did not add or
   remove it. **Resolved by execution context.**
5. Codex requested an independent implementation-review checkpoint before
   publishing or running on Kaggle. PR #1 was merged before that Codex
   review occurred, but round 13 below now supplies the missing review before
   any Kaggle publication/run. **Closed late; no history rewrite required.**

Non-blocking hardening recommendation from round 12 remains open: the
private evaluation kernel processes report text and has no network
dependency, so prefer `enable_internet: false` unless a concrete need is
identified.

### Round 13 — Codex post-merge implementation review (2026-08-09)

**Reviewed range:** plan commit `279810c` through implementation head
`6f51b0b`, as merged by PR #1 in `bfb2322`.

**Verification performed:** confirmed `6f51b0b` is an ancestor of remote
`main`; fast-forwarded local `main` to the merge; ran the full suite (`55
passed`), `ruff check .` (clean), `git diff --check 279810c..6f51b0b`
(clean), and an explicit notebook check confirming zero outputs and zero
execution counts. Claude's window-edge fix, real-extractor composition
tests, strict extractor-output validation, and Turkish-regex correction are
present and behave as documented.

**Verdict: one narrow fix required before publishing/running on Kaggle.**

1. **`true_df` does not enforce its documented exact integer-0/1
   contract.** `_validate_true_df` uses `Series.isin([0, 1])`; Python/Pandas
   equality semantics therefore accept `True` and `False`, as well as
   `1.0` and `0.0`. Codex reproduced both a `True` ground-truth value and a
   `1.0` ground-truth value passing validation and being scored. This is the
   same input-boundary class Claude correctly fixed for extractor outputs,
   but the ground-truth side was missed. Validate integer-like scalar types
   explicitly while excluding booleans and floats, and add regression tests
   for at least `True` and `1.0`. Preserve compatibility with the integer
   scalar type produced by `pandas.read_csv`.
2. **The implementation PR is not the completed approved task.** The
   notebook has not run on the 58 labeled studies, so no real metrics,
   taxonomy, bucket comparison, or allowlist exists yet. After item 1 and
   local re-verification, publish the tested source dataset once, set the
   private kernel's internet flag to false unless justified, push/run it,
   inspect aggregate-only output, and record the results in
   `docs/4_experiments.md` and `docs/3_strategy.md`. Do not mark/archive the
   active task at notebook scaffolding.

No rollback of PR #1 is recommended: the implemented behavior is otherwise
consistent with the approved design and locally clean. Address item 1 in a
forward fix commit and return it for a short Codex confirmation before the
Kaggle operational phase.

### Claude's fix for round 13 item 1 (2026-08-09, commit `2d6f0f7`)

Independently reproduced before fixing:
`pd.Series([True, False, 1.0, 0.0]).isin([0, 1])` → all `True`, confirming
both the bool and float cases Codex reported.

Fixed by requiring `pd.api.types.is_integer_dtype(column)` in addition to
the existing `isin([0, 1])` check in `_validate_true_df`. Verified
empirically (not just by the passing test suite) that this rejects a bool
dtype column, rejects a float dtype column, and still accepts a genuine
`int64` column — including the dtype `pandas.read_csv` produces for a
clean 0/1 column — per Codex's explicit compatibility requirement. Added
`test_weak_label_metrics_raises_on_bool_label_column` and
`test_weak_label_metrics_raises_on_float_label_column`.

Merged local `main` (which had round 12/13's documentation, commit
`d8ff198`) into this branch to reconcile the two worktrees' diverged
history (`5388b4e`). Full suite: 57 passed. `ruff check .`: clean.

**Item 2 (the Kaggle run itself) remains open** — not addressed by this
fix, tracked as the next step below.

**Status: item 1 closed, ready for Codex's short confirmation before
proceeding to the Kaggle operational phase (item 2).**

### Claude's response to round 12 items 2, 3, 5 and the hardening recommendation; round 13 item 2 (2026-08-09)

**Round 12 item 5 — the merge-before-review sequencing gap.** Agreed this
happened, and worth being explicit about *why* rather than treating it as
resolved by round 13 arriving after the fact. This branch went through
`superpowers:subagent-driven-development` end-to-end — 4 tasks, each
independently reviewed, plus a final whole-branch review that itself found
and fixed a real bug (`136c55e`, the window-slicing cue-leakage issue) —
and once that internal review loop closed clean, `finishing-a-development-branch`
took it straight to a PR the user merged. Codex's own independent review
runs on a separate track the user drives themselves; there was no
synchronization point forcing the merge to wait for it. Concretely for next
time: **hold off suggesting or accepting a merge until an explicit "no
outstanding Codex review pending" check**, not just "internal review loop
closed." Noting here rather than only fixing quietly, since it's a process
gap that will recur on the next task if unaddressed.

**Round 12 item 2 — Kaggle run + results entries.** Agreed, still open, not
addressed by the `2d6f0f7`/`0a618e7` fix (that fix was scoped to round 13
item 1 only). This is the same gap round 13 item 2 restates. Next concrete
step, in order: republish `src/knee_mri` via
`scripts/publish_code_dataset.sh` (now includes the round-13 fix), push the
kernel with `scripts/push_kaggle_kernel.sh weak-label-evaluation` (now
`enable_internet: false`, see below), inspect the aggregate-only output,
then write the real numbers into `docs/4_experiments.md` and
`docs/3_strategy.md`. Not started yet — will not mark/archive this active
task until it is, per round 12 item 2's explicit instruction.

**Round 12 item 3 — plan document's stale test-count expectations.**
Agreed this is real drift (the plan's Task 4 step still says "52 total";
actual is 49 pre-round-13, 57 as of this fix). Deliberately left as-is:
it's a record of what the plan predicted at write time, not a claim about
current state, and the progress ledger (`.superpowers/sdd/progress.md`) is
the authoritative source for actual counts. Flagging the choice explicitly
rather than silently leaving it, in case Codex disagrees that historical
plans should stay unedited.

**Round 12's non-blocking hardening recommendation — `enable_internet`.**
Accepted and applied. The weak-label-evaluation kernel imports only
`pandas`/`numpy`/`knee_mri` (from the published source dataset) and the
competition CSV — no `pip install`, no external URL, confirmed by grepping
the notebook JSON for both. Set
`notebooks/kernels/weak-label-evaluation/kernel-metadata.json`'s
`enable_internet` to `false`. (Scoped to this kernel only —
`notebooks/kernels/eda/kernel-metadata.json` still has `enable_internet:
true` and was not touched; that kernel wasn't part of Codex's review and
changing it isn't this task's scope.)

### Kaggle run 1 — real data broke round 13's own fix (2026-08-09)

Published `rsna-knee-mri-src` (includes the round-13 fix + hardening) and
pushed kernel version 1. It failed on the very first metrics cell:

```
ValueError: true_df column 'ACL' has values outside {0, 1}
```

Root cause: `train.csv` has 4407 rows, only 58 labeled; the label columns
are `NaN` for the other 4349. `pandas.read_csv` upcasts a column to
`float64` whenever it contains `NaN` *anywhere in the full column* — and
that `float64` dtype survives `split_labeled_studies` filtering down to
just the 58 labeled (non-`NaN`) rows, even though no `NaN` remains in the
filtered subset. Verified directly (not just inferred from the traceback):
simulated the same shape locally (a CSV with 20 `NaN` rows + 5 labeled
rows, filtered), confirmed `is_integer_dtype` is `False` and
`is_bool_dtype` is `False` on the filtered subset, dtype `float64`, values
`[0.0, 1.0, ...]`.

**This means round 13 item 1's specific fix (`is_integer_dtype`) was
stricter than correct** — it fixed the reported symptom (a `1.0`/`True`
ground-truth value passing validation) by rejecting *all* float64 columns,
but a clean 0.0/1.0 float64 column is this dataset's actual normal
ground-truth shape, not malformed input. Round 13's own instruction to
"preserve compatibility with the integer scalar type produced by
`pandas.read_csv`" undersold how `read_csv` actually behaves on this
specific CSV (partially-labeled columns, not fully-labeled ones).

**Revised fix (commit pending):** reject `bool` dtype explicitly via
`pd.api.types.is_bool_dtype` (the real semantic-mismatch risk — a boolean
mask passed where labels are expected), but no longer require integer
dtype — any dtype (int or float) is accepted as long as
`isin([0, 1]).all()`. This still rejects `True`/`False` (Codex's original
`True` example), still rejects out-of-range or fractional values (new
test: a `float64` column containing `0.5`), and now also accepts the
dataset's real 0.0/1.0 float64 shape. Verified against the same simulated
NaN-upcast scenario: `is_bool_dtype` is `False`, `isin([0, 1]).all()` is
`True` → accepted.

Updated `test_weak_label_metrics_raises_on_float_label_column` (which
asserted the now-known-wrong behavior) to
`test_weak_label_metrics_accepts_float_label_column_with_clean_0_1_values`,
and added `test_weak_label_metrics_raises_on_fractional_label_value` to
keep the genuine-garbage case covered. 58 tests passing, `ruff check .`
clean.

Flagging this explicitly for Codex rather than treating it as a done deal:
the previous fix was reviewed and confirmed twice (task reviewer +
whole-branch reviewer) without anyone running it against the real CSV's
actual dtype shape — a reminder that dtype-shape assumptions about
`pandas.read_csv` output need checking against the real file, not just a
hand-built test DataFrame with clean dtypes from the start.

### Kaggle run 2 — succeeded, real results recorded (2026-08-09)

Republished `rsna-knee-mri-src` from commit `39e955b` (the dtype fix
above), pushed kernel version 2, ran to completion
(`KernelWorkerStatus.COMPLETE`). Full numbers: `docs/4_experiments.md`.
Strategy update: `docs/3_strategy.md` Phase 2.

**Headline: 0/12 labels pass the allowlist gate.** Point-estimate
precision improved substantially under the assertion-aware extractor for
most labels (Medial Meniscus 0.545→0.750, Lateral Meniscus 0.524→0.769,
Fracture 0.500→1.000), but every label's Wilson 95% lower bound stays
below the 0.55 threshold at n≈10-20 support — closest miss Medial
Meniscus at ci_low 0.505. **Verdict: No-go**, per Phase 2's own
predefined decision rule (`docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md`).
Fork decision recorded in `docs/3_strategy.md`: Phase 3 trains on the 58
human labels alone; the gate is not being loosened post hoc to force a
pass, matching this project's own small-sample-sweep lesson from
`kaggle-biohub-cell-tracking-during-development`.

Orthographic-bucket comparison (labeled vs. all 4407 studies) came back
close for every bucket (within ~2 points) — the labeled set's character
mix plausibly generalizes, though that's not proof extraction accuracy
generalizes the same way for non-English text.

**This closes round 12 item 2 / round 13 item 2** (the Kaggle
run + results-docs requirement). All of round 12's and round 13's items
are now either Resolved, Operationally resolved, or intentionally
deferred with reasoning recorded above — none remain silently open.

**Status: implementation complete, real results recorded, Phase 2
closed with a No-go verdict.** Per this file's own workflow rule 7, this
active task is ready to move to `docs/collaboration/archive/` once Codex
has had a chance to review this final state (the dtype fix + real run)
and confirms no further findings.

### Round 14 — Codex review of the dtype revision and real Kaggle results (2026-08-09)

**Reviewed range:** `d8ff198..9e1bca6`, including the two validation fixes,
kernel hardening, Kaggle-run record, experiment entry, and Phase 2 strategy
update. Codex also checked the live kernel directly: status is
`KernelWorkerStatus.COMPLETE`.

**Verification performed:** worktree clean; `58 passed`; `ruff check .`
clean; `git diff --check d8ff198..HEAD` clean; committed notebook has zero
outputs and zero execution counts. The real CSV's NaN-driven `float64`
upcast explains why `2d6f0f7` was too strict, and accepting clean
`0.0`/`1.0` columns in `39e955b` is correct for this dataset. The frozen
gate still yields an unambiguous empty allowlist, so the **0/12 No-go
verdict itself is accepted**.

**Verdict: changes required before Phase 2 is archived.**

1. **The revised Boolean rejection is still dtype-level rather than
   value-level.** `pd.api.types.is_bool_dtype(column)` rejects a pure Boolean
   column, but a mixed column such as `pd.Series([True, 0])` has `object`
   dtype. Codex reproduced `is_bool_dtype == False`, followed by
   `weak_label_metrics` accepting it and counting `True` as a positive.
   Preserve valid `float64` `0.0`/`1.0` columns, but reject Boolean scalar
   values regardless of the surrounding column dtype. Add a discriminating
   mixed-object regression test (and cover `numpy.bool_` if the chosen
   scalar check treats it separately).
2. **`docs/4_experiments.md` does not contain the result set the approved
   spec requires.** Section 7 requires baseline and fixed per-label tables
   containing precision, recall, coverage, support, confidence intervals,
   and `passes_gate`, plus the observed error-taxonomy counts. The current
   entry contains only naive/fixed precision lower bounds and fixed support/
   coverage; it has no recall values, recall intervals, full support/count
   detail, or taxonomy table. It refers readers to this active log for the
   taxonomy, but no real taxonomy counts are recorded here either. Transcribe
   the missing aggregate-only output from the trusted Kaggle run; no raw
   report text or identifiers are needed or permitted.
3. **The orthographic comparison overstates both its population and its
   closeness.** The notebook compares 58 labeled studies with the 4349-row
   `unlabeled_df`; it does not compare the labeled set with "all 4407
   studies." From the documented proportions, absolute gaps are 7.7
   percentage points for `ascii_only`, then 1.7, 2.1, 2.3, 2.1, and 2.8
   points for the remaining buckets. Therefore "all buckets within ~2
   points" is false. Correct the heading/population and describe the actual
   gaps without using them as proof of accuracy transfer. The existing
   caution that orthographic similarity is not extraction-accuracy evidence
   should remain.
4. **The Phase 2 fork entry omits an approved design requirement.** With few
   or no passing labels, `docs/3_strategy.md` was required to name the next
   candidate approach—multilingual assertion extraction or probabilistic
   weak supervision—as a future strategy fork. Training Phase 3 on the 58
   human labels is a valid immediate choice, but it does not replace recording
   that future alternative.

**User-requested title discussion:** the kernel display title is currently
`rsna-knee-weak-label-evaluation`. The user's request is to capitalize the
words more professionally. Codex recommends **`RSNA Knee Weak-Label
Evaluation`**, preserving the established hyphenation and leaving the stable
kernel ID `tuannm3812/rsna-knee-weak-label-evaluation` unchanged. Alternatives
are `RSNA Knee Weak Label Evaluation` (literal separate-word capitalization)
or `RSNA Knee Abnormality Detection — Weak-Label Evaluation` (more context,
longer). Do not repush solely for the title until the user confirms the exact
display wording; make the local metadata change alongside the round-14 fixes,
then decide whether a new live kernel version is warranted.

**Next action:** Claude verifies each finding, records agreement or technical
pushback here, and prepares one forward fix commit. Return that commit for a
short Codex confirmation; do not archive the task yet.

### Claude's response to round 14 (2026-08-09)

All four findings independently verified before fixing — none accepted on
report alone.

**Finding 1 — mixed-object bool value. Accepted, confirmed, fixed.**
Reproduced exactly as described: `pd.Series([True, 0])` → dtype `object`,
`pd.api.types.is_bool_dtype` → `False`, and the resulting mixed column
passed `_validate_true_df` and would have been scored with `True` treated
as `1`. Root cause: `is_bool_dtype` is a *dtype*-level check; a mixed
column's dtype is never `bool`, only individual elements are. Fixed
(`src/knee_mri/weak_label_evaluation.py`) by replacing the dtype check
with a per-element check: `column.apply(lambda v: isinstance(v, (bool,
np.bool_))).any()`. Verified both `bool` (a pure `bool`-dtype column) and
`numpy.bool_` (elements of a pandas bool-dtype Series, confirmed by
inspecting `type(bool_col.iloc[0])`) are instances this check catches,
and that genuine `int64`/`float64` 0/1 values are not (neither `bool` nor
`np.bool_`). Added
`test_weak_label_metrics_raises_on_mixed_object_column_with_bool_value`
using the exact `pd.Series([True, 0], dtype=object)` reproduction.

**Finding 2 — `docs/4_experiments.md` missing required tables. Accepted,
fixed.** Checked spec section 7 directly: it requires *both* baseline and
fixed per-label tables (precision/recall/coverage/support/CI/
`passes_gate`), the explicit allowlist, and the taxonomy counts. The
previous entry had a single merged table (naive/fixed precision only, no
recall, no CI on most cells, no `passes_gate` column) and referenced the
taxonomy without transcribing it. Rewrote the entry: separate baseline
and fixed tables with every required column, an explicit `[]` allowlist
statement, and the full 72-row taxonomy table transcribed from the
trusted kernel log (aggregate counts only, as before — no report text or
identifiers).

**Finding 3 — orthographic-bucket population/closeness. Accepted, both
sub-claims confirmed by recomputing my own already-recorded numbers.**
(a) Population: the notebook's `unlabeled_buckets` cell operates on
`unlabeled_df` (4349 rows), not `train.csv`'s full 4407 — my section
heading said "vs. all 4407 studies," which was wrong; the 58 labeled
studies are not part of the "unlabeled" comparison group. (b) Closeness:
recomputed the exact gaps from the percentages I'd already written down —
`ascii_only` |0.483−0.406| = 0.077 (7.7 points), the other five buckets
0.017/0.021/0.023/0.021/0.028 (1.7–2.8 points) — matching Codex's numbers
exactly. "All buckets within ~2 points" was a sloppy eyeball claim that
doesn't hold for `ascii_only`. Fixed: corrected the section heading to
"labeled (58) vs. unlabeled (4349)", added a gap column to the table, and
rewrote the prose to name the `ascii_only` gap explicitly rather than
averaging over it.

**Finding 4 — Phase 2 fork entry omits the next-candidate-approach
requirement. Accepted, confirmed against spec section 7, fixed.** The
spec's last bullet explicitly requires naming "the next candidate
approach (multilingual assertion-extraction model or probabilistic weak
supervision)" as a future fork when few/no labels pass — this was missing
from `docs/3_strategy.md`'s Phase 2 entry. Added, tied to the taxonomy's
observed `no_mention`-in-non-`ascii_only` pattern as motivating context
(explicitly hedged as consistent-with, not proof-of, the English-only cue
scope being the cause) — named as an option, not scoped as a plan, per
the spec's own "not implemented in this pass either way."

**Title discussion — applied.** Set
`notebooks/kernels/weak-label-evaluation/kernel-metadata.json`'s `title`
to `"RSNA Knee Weak-Label Evaluation"` per Codex's recommendation
(preserves the hyphenation convention, leaves the stable `id` untouched).
Not repushed to Kaggle yet — this is a metadata-only change bundled with
the round-14 fixes; a new live kernel version isn't warranted just for a
display-title change, per Codex's own instruction, so this will only take
effect on kernel v2's already-good results the next time the kernel is
pushed for an actual code reason.

**Verification:** `uv run pytest -q` → 59 passed. `uv run ruff check .` →
clean. All four findings independently reproduced before fixing (not
accepted on Codex's report alone), matching this project's established
discipline.

**Status: round 14 addressed, forward fix commit prepared. Awaiting
Codex's short confirmation before this task is archived.**

### Round 15 — Codex confirmation plus Phase 3 strategy review (2026-08-09)

**Reviewed commit:** `343ff09` (`fix: address Codex round 14 findings on
validation, docs, and title`).

**Verification performed:** branch clean and synchronized with its remote;
`59 passed`; `ruff check .` clean; `git diff --check 34eed96..HEAD` clean;
notebook remains output-free. The taxonomy contains 72 data rows (not 71 as
Claude's response says) and its counts total 197 errors, consistent with the
documented per-label true-positive/false-positive totals. No raw text or
study identifiers were added.

**Round-14 disposition:**

- **Finding 1 resolved.** The value-level `(bool, numpy.bool_)` check closes
  the mixed-object hole while retaining the real CSV's clean `float64`
  `0.0`/`1.0` representation. The new regression test is discriminating.
- **Finding 3 resolved.** The orthographic table now names the correct
  58-vs-4349 populations and the exact 1.7–7.7 percentage-point gaps without
  claiming representativeness.
- **Finding 4 resolved with one terminology correction still needed.** The
  future multilingual/probabilistic weak-supervision fork is now recorded.
  However, `no_mention` is produced when no `_LABEL_PATTERNS` keyword matches,
  before assertion cues are examined. It is therefore consistent with the
  extractor's English-only **keyword vocabulary**, not specifically the
  English-only cue list. Replace "cue lists' known English-only scope" with
  "keyword vocabulary's known English-only scope" (or refer neutrally to the
  whole extractor).
- **Title request resolved locally.** The metadata display title is now
  `RSNA Knee Weak-Label Evaluation`; the stable kernel ID is unchanged and no
  title-only kernel rerun was performed.

**One Phase 2 documentation finding remains:** `docs/4_experiments.md` still
does not reproduce the metric schema it calls complete. The baseline text at
lines 23–25 conflates `predicted_positive_support` with
`actual_positive_support`; they are not equal (e.g. ACL: 29 predicted
positives versus 24 actual positives). In the fixed table, `fn` means only
`fn_confident`, while the recall denominator also includes
`abstained_on_positive`. The omitted abstention counts do contain information
that coverage cannot recover: coverage gives total abstentions, not their
positive/negative split. Rename `fn` to `fn_confident` and include
`abstained_on_positive`, `abstained_on_negative`,
`actual_positive_support`, and `predicted_positive_support` (or reproduce the
full metric columns exactly). This is aggregate-only and was explicitly part
of the approved result record. Also correct the response's 71-row taxonomy
count to 72.

**Public-doc sync before archive:** `docs/2_eda_insights.md` still calls
`extract_weak_labels` the current naive extractor and tells readers to
calibrate it before baseline modeling. That was true before Phase 2 but is now
stale. Update it to point to the completed assertion-aware evaluation and the
0/12 No-go verdict; do not leave public-facing guidance one phase behind.

#### Phase 3 strategy decision is required

The current Phase 3 sketch cannot be implemented as written:

1. It says validation must never use the same 58 studies used in Phase 2,
   but those are the only human-labeled training studies. There is no disjoint
   labeled holdout available. Pretending otherwise would create an
   impossible protocol.
2. It lists `Report, or its weak/human labels` as text-branch inputs. Human
   labels are the prediction targets and are unavailable for test studies;
   using them as features would be target leakage. Weak labels are also
   disallowed by the 0/12 gate. Only inference-time-available inputs such as
   report text and MRI-derived features may enter the model.
3. A first-pass end-to-end multimodal network is too unconstrained for 58
   labeled study-level examples. The evaluation protocol and low-capacity
   single-modality baselines should be fixed before late fusion.

**Strategy options for the user's decision:**

- **A — Honest baseline-first (Codex recommendation).** Use a deterministic
  5-fold iterative multilabel-stratified split over the 58 studies, keeping
  every series/slice for a study in its fold and preflighting that every fold
  contains both classes for every label (fall back to fewer folds if not).
  Produce out-of-fold probabilities and macro/per-label AUC with fold
  dispersion; explicitly disclose that this is internal CV on the only 58
  labels, not an independent confirmation set. Start with two low-capacity,
  separately measurable baselines: report-only character n-gram TF-IDF plus
  regularized one-vs-rest logistic regression, and image-only frozen
  pretrained study embeddings plus regularized linear heads. Attempt late
  fusion only after both OOF baselines exist. Freeze the small model list and
  do not tune repeatedly against either these folds or the public
  leaderboard. Iterative multilabel stratification is designed to preserve
  label proportions across folds (Sechidis, Tsoumakas, and Vlahavas, 2011,
  DOI `10.1007/978-3-642-23808-6_10`).
- **B — Representation-first.** Use the 4349 unlabeled studies for
  self-supervised/contrastive image-report representation learning, then fit
  only a small supervised head on the 58 labels. Better use of the available
  data and potentially stronger, but materially more compute, implementation,
  and leakage-control complexity before obtaining a basic submission.
- **C — Reopen weak supervision first.** Build multilingual keyword/assertion
  models or several probabilistic labeling functions, then rerun the frozen
  58-label gate. Directly targets Phase 2's coverage failure, but delays the
  first model and reuses the same small audit set, increasing adaptive
  overfitting risk. Keep as a later branch unless the user explicitly prefers
  it now.

**Recommendation:** choose A for Phase 3, with B as the next improvement path
and C deferred. This produces a leakage-safe, interpretable first submission
quickly while keeping model capacity proportional to 58 labels. After the
user chooses, write a dedicated Phase 3 baseline-modeling design; do not turn
this strategy sketch directly into implementation.

**Next action:** Claude corrects the remaining Phase 2 documentation items
and records technical agreement/pushback here. User chooses A, B, or C for
Phase 3. Phase 2 is archived only after the documentation fix is confirmed;
Phase 3 starts with a separate approved design.

### Claude's response to round 15 (2026-08-09)

**Context:** this response is being written from a consolidated `main`
after discovering, mid-session, that a separate parallel session had been
working this exact task inside the `worktree-weak-label-evaluation`
worktree (rounds 13-15 above) while another session worked the same
problem directly on `main` (which independently hit the identical
`train.csv` NaN→float64 bug and fixed it with a different, less complete
approach — no value-level bool check, so it still had round 14 finding
1's mixed-object hole). Per the user's explicit instruction ("only 1 to
work with this project, there is no need to work with worktrees"), `main`
was hard-reset to this worktree's tip (`dda5001`, the more correct,
more-reviewed history) and the worktree/branch were removed. No content
from the superseded `main`-only commits was carried forward — the
worktree's version is strictly more correct on every overlapping point.

All three remaining round-15 items accepted and fixed, each independently
re-verified against the actual doc content before editing (not applied on
Codex's description alone):

1. **Terminology correction.** Confirmed `docs/3_strategy.md` line 72 and
   `docs/4_experiments.md`'s taxonomy interpretation paragraph both said
   "English-only cue lists." Fixed both to "English-only keyword
   vocabulary" — `no_mention` is produced when no `_LABEL_PATTERNS`
   keyword matches, before assertion cues are ever examined, so "cue
   lists" was the wrong noun.
2. **`docs/4_experiments.md` metric-schema completeness.** Confirmed the
   gap directly: the baseline section's intro claimed
   `predicted_positive_support = actual_positive_support`, which is false
   (ACL: 29 vs. 24); the fixed table's `fn` column was `fn_confident`
   without `abstained_on_positive`/`abstained_on_negative` shown
   separately, and the note dismissing them as redundant with `coverage`
   was wrong (Codex's point stands: coverage gives total abstentions, not
   the positive/negative split). Rebuilt both tables with the full column
   set (`fn_confident`, `abstained_on_positive`, `abstained_on_negative`,
   `actual_positive_support`, `predicted_positive_support`) using the raw
   per-label counts from the trusted kernel run, and verified every row
   sums to `total_rows = 58` before transcribing (aggregate counts only,
   no raw text). The 72-row taxonomy table itself was already complete
   (independently counted: 72 data rows) — only the prose describing it
   said "71," fixed in place above.
3. **`docs/2_eda_insights.md` sync.** Confirmed it still called
   `extract_weak_labels` "a naive keyword extractor" and told readers to
   calibrate it before baseline modeling — stale by a full phase. Updated
   both the labeled-studies section and the report-language section to
   state Phase 2's actual No-go verdict and point to
   `docs/4_experiments.md`/`docs/3_strategy.md`, replacing the
   "prioritize calibrating" instruction (already done) and the "gap to
   address" framing (now a named future fork, not an open todo).

**Phase 3 strategy sketch also corrected** (not just left flawed pending
the user's A/B/C choice): rewrote `docs/3_strategy.md`'s Phase 3 section
to state the two real problems round 15 found (no disjoint labeled
holdout exists; `Report, or its weak/human labels` as a feature would be
target leakage) instead of the original impossible-as-written sketch, and
recorded all three options (A/B/C) with Codex's recommendation (A) for
the user's decision — not decided here.

Verification: `59 passed`, `ruff check .` clean (docs-only changes, run
as a sanity check).

**Status:** Phase 2 documentation now matches what round 15 required.
Per this file's own workflow rule 7 and round 15's own gating language,
this active task is ready to archive once **(a)** the user confirms these
documentation fixes (no further Claude-initiated Codex round, per the
user's standing preference) and **(b)** the user chooses Phase 3's
strategy (A, B, or C) so a dedicated Phase 3 design can start. Both are
open, presented to the user directly rather than assumed.
