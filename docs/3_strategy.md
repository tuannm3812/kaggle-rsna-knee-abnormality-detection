# Strategy

Phased plan against the competition timeline (`docs/1_instructions.md`):
entry/team-merger deadline **2026-10-15**, final submission
**2026-10-22**. Dates below are targets, not commitments — revised as
each phase's real findings change what the next phase should be. Written
2026-08-09 once real EDA findings (`docs/2_eda_insights.md`) existed to
plan against; before that, this file was an empty placeholder.

Status and detailed review history for whichever phase is currently in
progress: `docs/collaboration/active_task.md`. This file is the roadmap;
that one is the moment-to-moment work log.

## Phase 0 — Setup — done 2026-08-09

Repo scaffold, `uv`/`pyproject.toml` tooling, tested `src/knee_mri`
package (`labels`, `metrics`, `dicom_io`, `dataset`), stub `01_eda.ipynb`,
Kaggle CLI scripts. Full history:
`docs/superpowers/plans/2026-08-09-repo-setup.md`.

## Phase 1 — EDA — done 2026-08-09

`01_eda.ipynb` run to completion on Kaggle (kernel
`tuannm3812/rsna-knee-eda` v7). Real findings in `docs/2_eda_insights.md`
— the two that most shape everything below:

- **Only 58 of 4407 training studies (1.3%) carry human-annotated
  labels.** This is the central constraint on every later phase — a
  model trained on 58 labeled examples alone has almost no signal, so
  weak-label mining from `Report` isn't optional polish, it's close to
  required for having a usable training set at all.
- Reports are genuinely multilingual (German, Turkish, Croatian, Greek,
  English observed in a small sample) — no single-language shortcut.

## Phase 2 — Weak-Label Evaluation — done 2026-08-09, verdict: No-go

Measured `extract_weak_labels` against the 58 real labeled studies, fixed
the assertion-detection gap Codex's review identified (mentions an
anatomy keyword is not the same as asserting an abnormality), and
reached the predefined go/no-go verdict rather than iterating
indefinitely.

- Design: `docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md`
  (filename kept for history; content is titled "Weak-Label Evaluation").
  Full review history (11 design rounds + 2 post-merge Codex rounds):
  `docs/collaboration/active_task.md`. Real numbers:
  `docs/4_experiments.md`.
- **Verdict: No-go.** 0/12 labels clear the allowlist gate
  (`MIN_SUPPORT=5`, `MIN_PRECISION_LOWER_BOUND=0.55`, Wilson lower
  bound). The assertion-aware fix improved point-estimate precision
  substantially for most labels (e.g. Medial Meniscus 0.545→0.750,
  Fracture 0.500→1.000) — the mechanism is doing real work — but with
  only 58 labeled studies, per-label support is small enough (n≈10-20
  for most labels) that the 95% confidence interval stays below the
  gate even where the point estimate clears it. Closest miss: Medial
  Meniscus at ci_low 0.505 against a 0.55 threshold.
- **Fork decision:** Phase 3 trains against the 58 human labels alone
  for now — no weak-label expansion of the training set. This project's
  own "don't trust small-sample sweeps" lesson
  (`kaggle-biohub-cell-tracking-during-development`, Phase 4 below)
  argues against lowering the gate thresholds post hoc to force a pass;
  the honest read is that 58 labeled studies isn't enough evidence yet,
  not that the extractor is wrong. If more human-labeled studies become
  available before Phase 3 starts, re-run this evaluation rather than
  assume the verdict is stable at a different sample size.
- **Next candidate approach, if weak labels are revisited** (per the
  design spec section 7 — named now as a future strategy fork, not
  implemented in this pass): either a multilingual assertion-extraction
  model (the taxonomy in `docs/4_experiments.md` shows most false
  negatives are `no_mention` — no keyword matched at all — concentrated
  in non-`ascii_only` buckets, consistent with, though not proven by,
  the keyword vocabulary's known English-only scope), or probabilistic weak
  supervision combining multiple labeling functions (à la Snorkel,
  per round 1's original suggestion) rather than a single regex-based
  extractor. Neither is scoped or estimated here; this is a named
  option, not a plan.

## Phase 3 — Baseline Modeling — in progress, strategy A (2026-08-09)

First trainable multi-label model producing a real macro-AUC number and
a first `submission.csv`. The original sketch here (an unconstrained
multimodal network validated on a disjoint 58-study holdout) turned out
to be unimplementable once actually checked against Phase 2's result —
Codex's round-15 review of the active task caught two real problems:

1. There is no disjoint labeled holdout — the 58 human-labeled studies
   *are* the entire labeled set. "Never validate on the same 58 studies"
   was an impossible protocol, not a real constraint to design around.
2. `Report, or its weak/human labels` as a text-branch input would be
   target leakage (human labels are the prediction target, unavailable
   at test time) and weak labels are unusable anyway per Phase 2's 0/12
   gate. Only inference-time-available inputs (report text itself,
   MRI-derived features) may enter the model.

**User chose strategy A — Honest baseline-first** (Codex's own
recommendation) over B (representation-first) and C (reopen weak
supervision first). Strategy A is delivered as three reviewed
sub-phases — **not** to be confused with the A/B/C strategy choice
above, this is a delivery decomposition within strategy A itself,
proposed by Codex's round-1 task audit and accepted:

### Phase 3A — Report Baseline — implemented, but cannot be submitted as designed

Deterministic 5-fold iterative multilabel-stratified CV over the 58
labeled studies (preflight both classes present per label per fold,
falling back to fewer folds if not); a frozen character n-gram TF-IDF
plus regularized one-vs-rest logistic regression, trained on report text
only; pooled out-of-fold macro-AUC as the primary internal score.

- Design: `docs/superpowers/specs/2026-08-10-phase-3a-report-baseline-design.md`
  — approved by the user after Claude's whole-spec review.
- Plan: `docs/superpowers/plans/2026-08-10-phase-3a-report-baseline.md`
  — 12 tasks, approved for execution. Full review history (33+ Codex/
  Claude rounds across design, plan, and implementation):
  `docs/collaboration/active_task.md`.
- **Status:** all 9 local implementation tasks were completed and
  independently accepted, and Task 10 (private Kaggle execution) ran the
  EDA and weak-label kernels successfully. The baseline kernel's first real
  run then surfaced a design-breaking fact no earlier review could see
  locally: the real competition `test.csv` has no `Report` column at all
  (`docs/1_instructions.md`, round 37). A model that only accepts report
  text as input cannot produce test-time predictions, so this design **can
  never be submitted as originally specified** — Task 10 is stopped at this
  step, not proceeding to Tasks 11–12. The implementation itself is not
  discarded: its pooled out-of-fold macro-AUC on the 58 labeled studies
  remains a valid **train-only signal audit**, and it's a candidate
  "teacher" for a future weak-label pipeline if that path is ever reopened
  (its own reliability gate, not assumed) — but not a component that can be
  blended into a real submission the way Phase 3C originally assumed (round
  40, finding 1).

### Phase 3B — Frozen Image-Embedding Baseline — design proposed, not yet approved

Since Phase 3A cannot be submitted, this phase is being pulled forward to
be the actual first submittable baseline: a frozen pretrained image
encoder evaluated on the exact same Phase 3A folds. **Not yet designed or
approved** — a proposal exists (round 37) and a project-owned DICOM/series
preflight audit has run twice to inform it (rounds 39–41,
`docs/7_image_baseline_insights.md`), but the formal design spec, plan, and
implementation have not started. No dataset publication, kernel run, or
submission beyond this preflight work is authorized until that design is
written and independently reviewed.

### Phase 3C — Late Fusion — not started, premise needs revisiting

Originally scoped as one predefined blend rule combining Phase 3A and
Phase 3B's out-of-fold predictions for the real submission. Since Phase 3A
has no test-time predictions to blend, a direct submission-time fusion of
the two is not viable as originally described — any fusion role for Phase
3A's signal (e.g. as a weak-label teacher feeding Phase 3B's training
targets) would need its own design and reliability gate, not an assumed
blend rule. Still not designed or scoped; revisit only after Phase 3B
exists.

---

Beyond this 3A/3B/3C sequence: strategy B (representation-first, using
the 4349 unlabeled studies for self-supervised/contrastive learning) is
recorded as a longer-term improvement path once Phase 3B exists; strategy
C (reopening weak supervision with a multilingual/probabilistic approach
before modeling) remains deferred, not ruled out.

## Phase 4 — Model Improvement & Ensemble — target ~2026-10-08

Informed directly by lessons pulled from this user's prior Kaggle repos
(not guessed abstractly):

- **Prioritize architecturally diverse signal sources over per-label
  calibration tuning.** `kaggle-birdclef-2026`'s biggest real score jumps
  came from adding a genuinely different second model/modality, not from
  hand-tuning per-class blend weights — and per-label threshold tuning on
  a handful of positive examples (exactly our situation with only 58
  human labels) produced noise, not signal, in that project too. A
  distinct text-based classifier combined with an imaging model is a
  stronger lever here than fine-tuning either one further.
- **Consider a post-processing/label-cleaning layer, not just model
  architecture.** `kaggle-biohub-cell-tracking-during-development` found
  every top public solution — trained or classical — converged on the
  same core pipeline shape, and a deterministic repair/cleanup layer on
  top mattered more than the model itself. Weak-label quality (Phase 2)
  is this project's analogous lever.
- **Don't trust small-sample threshold/hyperparameter sweeps.** Biohub's
  own `DET_THRESHOLD` sweep on 19 held-out examples predicted a gain that
  reversed at 3x the sample size. With only 58 human-labeled studies
  total, any "pick the best of several configurations" step here carries
  the same risk — prefer single, hypothesis-driven tests over sweeps
  where the labeled set is this small.
- **Efficiency Track awareness**: the competition scores a separate
  efficiency track combining accuracy and wall-clock scoring runtime
  (`docs/1_instructions.md`). Revisit inference cost (model size, TTA,
  ensemble breadth) once a working accuracy baseline exists — not before,
  since optimizing runtime on an unproven model is premature.

## Phase 5 — Final Submission — target lock-in by ~2026-10-20 (buffer before 2026-10-22)

- Freeze the champion configuration; re-run end-to-end on Kaggle once
  more to confirm reproducibility before the final submission.
- Confirm the ≤9h runtime / internet-disabled Code Requirements
  (`docs/1_instructions.md`) against the actual frozen notebook, not
  assumed from an earlier faster run.
- Submit with enough buffer before the deadline to recover from a failed
  Kaggle run.
- Record the final result and a short "what worked / what didn't" in a
  closing doc (numbered when written, per this file's own convention —
  reserve a new doc number for a promoted, project-owned finding, not
  every step).

## Planned docs (created as each phase produces results)

| Doc | Phase | Status |
|---|---|---|
| `4_experiments.md` | 2+ | First entry recorded 2026-08-09 (Phase 2's weak-label evaluation, verdict: No-go) |
| `5_submissions.md` | 3+ | Stub — first entry lands at Phase 3's first real submission |
| `7_image_baseline_insights.md` | 3 | First entry recorded 2026-08-11: preflight audit v1 real measurements informing the Phase 3B pipeline design |
