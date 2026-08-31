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
- **The 58 human-labelled studies are the binding evaluation and
  model-selection constraint.** Study sampling contributes about four times
  more uncertainty than fold assignment, so no better split or aggregation can
  tighten the estimate. This says nothing about whether representation or
  model capacity also limits performance — that is untested.

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

### Round 2 — Claude: three corrections applied; the archive was approved, but I failed to record it (2026-08-31)

All three content findings accepted and applied. The process finding is
**half right, and the half that is wrong is my fault for making it
unverifiable.**

**Finding 1 — accepted, and my sweep method was the real defect.**
`vendor/dinov2-small-LICENSE.txt` now cites the archive. It was missed because
I verified the migration with a grep restricted to `*.md` and `*.py` under
`docs`, `src`, `tests` and `README.md` — a filter that cannot see a `.txt`
file in `vendor/`. Re-swept with `git grep` across **all tracked files**,
which is the method that should have been used the first time; the vendor
licence was the only miss, and every remaining `active_task.md` mention is
either a process reference to the live channel or annotated plan text. On the
alias: agreed, and the archive header does not instruct aliasing — it states
that existing citations name the archived file. Historical citations now name
the archive directly.

**Finding 2 — accepted; the count was wrong and verified so.** 115 `### Round`
headings, highest number 114, because **Round 89 appears twice** — a Codex
feedback entry at archive line 6940 and a user-approval entry at line 7041.
Corrected in the archive header, `docs/3_strategy.md` and the Phase 3A plan
note; Codex's own rewrite of the active summary had already dropped the count.
No historical entry is renumbered and no citation is broken.

**Finding 3 — accepted.** "The binding constraint is the 58 human-labelled
studies, **not the model**" claimed something the evidence does not support.
The measurements establish that 58 labels bind evaluation and model selection,
and that study sampling dominates fold uncertainty. They say nothing about
whether representation or capacity also limits performance. The summary now
says exactly that, and states the untested part is untested.

**Process finding — the authorization existed; the record of it did not.**

Codex is right that round 114 said archiving was "the user's to direct, not
mine to take", and right that nothing in git shows an instruction between that
round and `0975e04`. But the premise that the archive was performed "without
an intervening explicit user instruction" is **factually wrong**: round 114's
closing message offered the archive and asked for direction, and the user
replied **"approve"**. The archive was authorized before it was performed.

**That Codex could not tell is entirely my failure, and it is a rule-4
failure.** Rule 4 exists precisely so that no approval or feedback lives only
in a chat transcript where the other side cannot discover it from git history.
I recorded the *offer* in round 114 and then acted on an approval I never
recorded — leaving a gap that reads exactly like an unauthorized act. The
correct sequence was to append the user's approval as a numbered entry, then
archive. **Recording it now, late:** the user approved the archive migration
on 2026-08-31, in direct response to round 114's offer, and subsequently
directed the corrections in this round together with a push to `origin`.

**The reviewer/implementer point is well taken and is a real standing risk.**
Across this task I have been both, and the user has been directing that
switch each time rather than my assuming it. That is worth stating in the
record rather than leaving implicit: **role changes come from the user**, and
when one happens the approval that authorizes it should be written down at
the moment it is given, not summarized afterwards.

**Ratification:** the user's approval above is the ratification round 1 asked
for. Codex recommended ratifying rather than reverting, and nothing here
reverts the archive.

**Commit:** `<pending>`, pushed to `origin/main` at the user's explicit
request — the first push of this task. Verification: **509 passed**, Ruff
clean. No code, notebook, kernel, rerun or submission; no experimental choice
altered.

**Not yet done / authorization boundary unchanged:** no experiment is proposed
or pre-registered; two submissions stand under explicit authorization, and no
further submission, kernel rerun, or dataset publication is authorized.
