# Claude–Codex Active Task Log — no task open

This tracked file is the shared handoff and review channel for the current
task. Both sides must read this file, the approved design, and the
implementation plan before starting or resuming work. Roles are assigned per
task and stated explicitly in "Current Task" below.

## Workflow Rules

1. Work from the shared `main` checkout. The user prefers no worktrees; use
   one only if the user explicitly asks.
2. Before acting, read `git status`, recent `git log`, this file, and the
   relevant design or plan.
3. **Codex implements/drafts; Claude reviews independently.** Claude does not
   change implementation, specification, or result files while reviewing;
   its permitted review-side write is this collaboration log.
4. The user runs Codex directly. Every Codex or Claude feedback pass,
   including a clean confirmation, must be appended here as a clearly
   labeled numbered round and committed before handoff. Feedback must not
   exist only in chat or as an uncommitted change.
5. The implementer addresses accepted findings in a separate forward commit;
   never amend or rewrite a commit already reviewed.
6. Do not begin implementation while design findings or user approval
   decisions remain unresolved.
7. When the task is fully accepted, archive this record under
   `docs/collaboration/archive/` and create a fresh active log for the next
   task.

## Current Task

**None. Awaiting the user's direction on what comes next.**

The previous task closed on 2026-08-31 and its complete 115-round record is
`docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md`. Round
citations elsewhere in the repo ("active_task.md round 39", and similar) refer
to that archived file, not to this one — **round numbering restarts at 1 for
the next task.**

### Where the project actually stands

- **Phase 3B frozen image baseline is the incumbent and is submitted.** Pooled
  OOF macro AUC `0.6346`, bootstrap 95% `[0.5704, 0.6973]` on 58
  human-labelled studies. Two submissions under explicit authorization:
  mean pooling `0.681` and max pooling `0.687` public LB
  (`docs/5_submissions.md`).
- **The aggregation question is closed.** Seven alternatives across nine
  pre-registered comparisons; none resolved, and max pooling did not displace
  the reported baseline.
- **W1 is closed.** Report-derived weak labels scored `0.6056` against the
  baseline's `0.6346`, delta `-0.029`, 95% `[-0.102, +0.047]` — no
  displacement, and not shown to help or hurt. No follow-up was proposed,
  deliberately (`docs/4_experiments.md`).
- **The binding constraint is the 58 human-labelled studies**, not the model.
  Study sampling contributes about four times more uncertainty than fold
  assignment, so no better split or aggregation can tighten the estimate.

### Open items, none of them started or authorized

- **Phase 3C late fusion** — its stated precondition (Phase 3B exists) is met,
  but it has no design and nothing is authorized to start (`docs/3_strategy.md`).
- **Strategy B** (representation-first on the 4349 unlabelled studies) and
  **Strategy C** (multilingual or probabilistic weak supervision) remain
  documented candidates, neither proposed nor scoped.
- **A hybrid weak/human model** — falling back to the baseline for labels the
  reports cannot supply — was raised while closing W1 and would require its
  own pre-registration. Not proposed here.
- **Documentation maintenance:** the README's hard-coded `509 passing` test
  badge will drift on the next test added. Codex and Claude both noted a
  generated badge or no count would be more durable; the user's call.

**Authorization boundary carried forward:** two submissions have been made
under explicit authorization. **No further submission, kernel rerun, dataset
publication, or experiment is authorized.**

## Review Thread

*Empty — the next task's rounds start here at round 1.*
