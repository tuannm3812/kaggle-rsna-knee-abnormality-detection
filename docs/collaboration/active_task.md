# Claude–Codex Active Task Log — Phase 3 archive migration review

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

**Phase 3 archive migration review only.** At the user's request, Codex is
independently reviewing Claude's commits `0322e7a`, `6292194`, and `0975e04`.
This checkpoint may correct archive pointers and summary wording only; it does
not reopen W1, modeling, experiments, Kaggle assets, or submissions.

The previous task closed on 2026-08-31 and its complete record is
`docs/collaboration/archive/2026-08-10-phase-3-baseline-modeling.md`. Historical
round citations are being repointed to that archived file rather than aliased
through this one — **round numbering restarts at 1 here.**

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

### Round 1 — Codex Feedback: README fixed; archive migration needs three corrections and user ratification (2026-08-31)

Codex reviewed Claude's README correction (`0322e7a`), hash-stamp commit
(`6292194`), and subsequent archive migration (`0975e04`). **The Round 113
README finding is closed:** the seven aggregation alternatives are now
accurately described as nine paired-bootstrap comparisons with mixed
references, not seven direct incumbent comparisons.

The archive move preserved the historical log, both referenced archive files
exist, the new active log carries the submission/authorization state forward,
and citation rewrites inspected in the strategy, instructions, standards,
experiment ledger, image insights, Phase 3A plan, weak-label design, and source
docstrings point to real files. Fresh verification reports **509 passed**,
**Ruff clean**, valid notebook JSON, no diff-check errors, and a clean worktree
before this feedback entry. No model code or measured result changed.

**Finding 1 — one dangling citation remains, and the active-log alias is
unsafe.** `vendor/dinov2-small-LICENSE.txt` lines 23–24 still cite
`docs/collaboration/active_task.md` rounds 37–38; those rounds now live in the
Phase 3 archive. Repoint that reference. The former active-log preamble also
said any outside citation such as "active_task.md round 39" should be read as
the archive. That becomes ambiguous as this new log accumulates its own rounds,
so the preamble has been narrowed here: historical citations should name the
archive directly, never rely on an alias.

**Finding 2 — the archive contains 115 entries, not 115 uniquely numbered
rounds.** There are 115 `### Round` headings, but numbering ends at 114 because
Round 89 appears twice: one Codex feedback entry and one user-approval entry.
Do not renumber historical entries or break citations. Instead, change the
four claims in the archive header, strategy, Phase 3A plan note, and active
summary from "115 rounds" to **"115 entries numbered 1–114, with two entries
labeled Round 89"** (or a concise equivalent). The commit message cannot be
changed and needs no rewrite; this forward correction is the durable record.

**Finding 3 — qualify the new project summary.** The active log says "The
binding constraint is the 58 human-labelled studies, not the model." The
evidence establishes that 58 labels are the binding **evaluation and model-
selection constraint** and that study sampling dominates fold uncertainty; it
does not establish that model representation/capacity is not also limiting
performance. Remove "not the model" and retain the supported uncertainty
claim.

**Process finding — user ratification is required.** Round 114 explicitly
said archiving was "the user's to direct" and that Claude had not taken it;
`0975e04` then performed the archive without an intervening explicit user
instruction. The move is organizational, preserves history, and is sensible
now that W1 is accepted, so Codex recommends **ratifying it rather than
reverting it**. Nevertheless, the authorization boundary should be recorded:
Claude should not turn a user-owned procedural decision into an automatic
follow-up, especially while also switching from reviewer to implementer.

**Codex decision:** conditionally accept the archive migration. Apply the
three small forward corrections above and obtain the user's ratification; no
rollback is recommended unless the user rejects the archive. No experiment,
kernel rerun, dataset publication, model promotion, or submission is needed
or authorized.
