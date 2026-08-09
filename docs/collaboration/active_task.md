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
4. Codex reviews independently (`codex exec -s read-only` / `codex
   review`) without changing any files. Findings and evidence are recorded
   here, not left only in the chat transcript.
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
- Task: Weak-Label Evaluation — Design Review (no implementation yet)
- Status: **Design confirmed ready after 8 review rounds (Codex round
  8: "READY for user approval and implementation planning... No further
  revision round warranted").** Awaiting user approval. Once approved,
  next step is `superpowers:writing-plans`.
- Implementation has not started. No code exists for this task yet.

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
