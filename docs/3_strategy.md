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

## Phase 2 — Weak-Label Evaluation — in progress, target ~2026-08-16

Measure `extract_weak_labels` against the 58 real labeled studies, fix
the assertion-detection gap Codex's review identified (mentions an
anatomy keyword is not the same as asserting an abnormality), and reach
an explicit go/no-go verdict on whether regex-based weak labels are good
enough to use, rather than iterating indefinitely.

- Design: `docs/superpowers/specs/2026-08-09-weak-label-calibration-design.md`
  (filename kept for history; content is titled "Weak-Label Evaluation").
- Status: mid-review (3 rounds with Codex so far) — see
  `docs/collaboration/active_task.md` for the full thread. Not yet
  approved, not yet implemented.
- **This phase's result is a real fork in the road, not a formality:**
  - **Go** → Phase 3 trains against human labels (58) plus weak labels
    (however many studies the extractor produces a confident,
    high-precision label for).
  - **No-go** → Phase 3 either trains against the 58 human labels alone
    (likely too little data to be competitive) or Phase 2 gets a second,
    different pass (multilingual assertion-extraction model, or
    probabilistic weak supervision combining multiple labeling
    functions) before Phase 3 starts. Recorded as a real decision point
    when/if it happens, not assumed now.

## Phase 3 — Baseline Modeling — target ~2026-09-06, shape depends on Phase 2

First trainable multi-label model producing a real macro-AUC number and
a first `submission.csv`. Concrete design deferred until Phase 2's
verdict is known (see fork above) — sketching the shape now, not a full
spec:

- Multimodal: an imaging branch (DICOM series → per-study features or
  embeddings, series selected via `knee_mri.dataset.select_primary_series`)
  and a text branch (`Report`, or its weak/human labels) — both are real
  signal sources per the competition's own framing, and combining them is
  the point of this being a multimodal competition rather than
  image-only or text-only.
- Trains and evaluates via `knee_mri.metrics.macro_auc` — the actual
  competition metric — with a grouped/held-out validation split
  (never validate on the same 58 studies used to justify Phase 2's
  weak-label fix, to avoid the exact small-sample overfitting trap
  Codex's review warned about there).
- First real Kaggle GPU training run, first real submission.

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
| `4_experiments.md` | 2+ | Stub — first entry lands when Phase 2's Kaggle run produces real numbers |
| `5_submissions.md` | 3+ | Stub — first entry lands at Phase 3's first real submission |
| A future baseline-modeling doc (numbered when written) | 3 | Not created yet |
