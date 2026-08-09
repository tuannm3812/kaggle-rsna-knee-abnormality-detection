# Claude–Codex Active Task Log — Phase 3 Baseline Modeling

This tracked file is the shared handoff and review channel for the current
task. Codex is the implementer and Claude is the independent reviewer. Both
must read this file, the approved design, and the implementation plan before
starting or resuming work.

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

- **Roadmap phase:** Phase 3 — Baseline Modeling, strategy A (honest
  baseline-first), selected by the user on 2026-08-09.
- **Roles:** Codex = implementer/design author; Claude = reviewer.
- **Design:** not yet written.
- **Implementation plan:** not yet written.
- **Status:** pre-design task audit; implementation is not authorized yet.
- **Previous task:** Phase 2 is accepted and archived at
  `archive/2026-08-09-weak-label-evaluation.md`.

## Review Thread

### Round 1 — Codex Feedback: pre-implementation plan and task audit (2026-08-10)

**Reviewed:** the complete roadmap, both historical design specs and
implementation plans, current source/tests/notebooks, competition and coding
standards, Phase 2's final documentation, and commits through `25dde46`.

**Repository verification:** `main` is clean and synchronized with
`origin/main`; there is one working tree; `59 passed`; Ruff is clean; both
committed notebooks are output-free. Phase 2's final table arithmetic and
taxonomy counts were independently reconciled before its log was archived.

**Progress reclassification:** Phase 0 (setup), Phase 1 (EDA), and Phase 2
(weak-label evaluation, No-go) are complete. The unchecked boxes in the two
existing implementation-plan files are historical authoring artifacts, not
unstarted work and must not be executed again. Phase 3 has a chosen strategy
but no approved design or implementation plan. Phases 4 and 5 remain roadmap
items and are not current work.

**Verdict: revision/decisions required before implementation.** Strategy A
is sound, but it is still too broad to execute safely as one task. Codex
recommends preserving strategy A while splitting delivery into reviewed
gates:

1. **Phase 3A — evaluation and report baseline:** deterministic study-level
   folds, fold-safe report TF-IDF/logistic regression, pooled out-of-fold
   predictions and metrics, full-data refit, offline-safe inference, and the
   first valid `submission.csv` path.
2. **Phase 3B — frozen image-embedding baseline:** choose and freeze the
   pretrained asset, preprocessing, series/slice sampling, study aggregation,
   and regularized heads; evaluate on the exact same folds.
3. **Phase 3C — late fusion:** attempt only after both unimodal OOF prediction
   sets exist, using one predefined blend rule rather than a weight sweep.

This is sequencing, not a change from the user's strategy-A decision. It
gets a leakage-safe, CPU-cheap report baseline and submission contract working
before committing to the materially larger imaging subsystem.

**Design issues the dedicated Phase 3A spec must resolve:**

- Treat pooled OOF macro-AUC across all 58 studies as the primary internal
  score; report per-label OOF AUC and fold scores/dispersion as diagnostics.
  Per-fold AUC alone is fragile at this sample size.
- Preflight the proposed deterministic five-fold iterative multilabel split
  for both classes of all 12 labels in every validation fold, and define a
  deterministic lower-fold fallback. Fit every text transform and classifier
  only on each training fold. The repository currently has no iterative
  multilabel-stratification dependency, so the design must choose and package
  an established offline-safe implementation rather than silently assuming
  it exists.
- Freeze the report model configuration before seeing OOF results; include a
  constant-0.5 sanity baseline; fit the final inference model on all 58 labels
  only after OOF evaluation. Human labels, weak labels, fold-global text
  features, and leaderboard feedback are forbidden model inputs/tuning
  signals.
- Define submission-schema validation, failure behavior, artifacts, and what
  aggregate-only evidence is copied into `docs/4_experiments.md` and
  `docs/5_submissions.md`. Real reports, identifiers, fitted features, and
  predictions stay off git.
- Resolve notebook numbering. `02_weak_label_evaluation.ipynb` already owns
  step 02, while `docs/0_coding_standards.md` still reserves
  `02_baseline_modeling.ipynb`. Codex recommends
  `03_baseline_modeling.ipynb` and a corresponding standards update.

**Items deliberately deferred to the Phase 3B design:** exact pretrained
image encoder/weights, 2D versus 3D representation, plane and series
selection, slice sampling, image normalization, embedding aggregation,
offline asset packaging, GPU memory/runtime, and missing/corrupt-series
behavior. None is specified well enough in the roadmap to implement now.

**Documentation debt to include in the next bounded docs change:** the README
badge and Status section still say “Scaffolding,” despite completed EDA and
weak-label evaluation. Historical plans should receive an explicit completed
status note (without rewriting their original unchecked execution trace) so
future agents do not mistake them for active work.

**Decision requested from the user:** approve or reject the Phase
3A → 3B → 3C decomposition, with Phase 3A designed first. No modeling code or
notebook should be written until that choice is recorded and the resulting
design has been reviewed by Claude and approved by the user.

**Claude review request:** after Codex commits the Phase 3A design, review the
validation contract, fold-safety, fixed model configuration, Kaggle offline
dependency/submission path, and scope boundary independently. Record technical
agreement or concrete pushback here before Codex writes the implementation
plan.

### Round 2 — Codex Feedback: user-approved notebook architecture (2026-08-10)

**User decisions recorded:**

- Approved the staged strategy-A delivery: Phase 3A report baseline, then
  Phase 3B frozen image embeddings, then Phase 3C late fusion.
- Selected the public-first, end-to-end notebook approach rather than an
  editorial-only pass or separate analysis/submission notebooks.
- Confirmed that kernels remain private during development and become public
  only after an explicit publication decision.
- Required kernel-native submission following the shared Kaggle coding
  standard section 11: push and execute the whole notebook, verify its
  generated `submission.csv`, and submit that exact completed kernel version
  through Kaggle's code-submission API rather than upload a separately
  generated CSV.

**Approved architecture section:**

1. `01_eda.ipynb` becomes a professional aggregate-only data story. Remove
   raw report excerpts, study identifiers, platform/version prints,
   troubleshooting prose, and internal path explanations. End with findings,
   limitations, and modeling implications supported by the trusted run.
2. `02_weak_label_evaluation.ipynb` replaces every stale “pending” insight
   with the trusted Phase 2 aggregate results: baseline-versus-fixed metrics,
   coverage, error taxonomy, and the 0/12 No-go implication. It never displays
   report text or identifiers.
3. New `03_baseline_modeling.ipynb` is one end-to-end Phase 3A workflow:
   load and validate data, construct folds, create OOF predictions and
   interpretations, refit on all 58 labels, predict test studies, validate
   submission schema, and write `/kaggle/working/submission.csv`. There is no
   evaluation/submission mode split.
4. Retain only meaningful scientific configuration such as the seed, fold
   count, and frozen model parameters. Remove `NOTEBOOK_VERSION`,
   `IS_KAGGLE`, environment diagnostics, internal workflow notes, and printed
   filesystem paths. Every important result receives adjacent Markdown
   interpretation.
5. Repository notebook copies remain output-free. Trusted Kaggle runs may
   display only safe aggregate outputs. Before eventual public release, every
   attached dependency must be public or replaced with self-contained code.

**Standards impact:** these user decisions supersede the current project
boilerplate requirement for `NOTEBOOK_VERSION` and `IS_KAGGLE`, and resolve
the notebook-number collision in favor of `03_baseline_modeling.ipynb`.
The dedicated design must update `docs/0_coding_standards.md` accordingly so
the implementation is not judged against contradictory rules.

**Status:** architecture approved by the user and ready for Claude's early
review. The validation/model, error-handling, and testing sections are still
being designed; no implementation is authorized. Claude should record any
architecture-level objection here without editing the notebooks or proposed
specification.

### Round 3 — Claude's early architecture review (2026-08-10)

**Reviewed:** rounds 1-2 above against the actual repository state — not
accepted on description alone.

**Independently verified, all confirmed accurate:**

- Repo state: `main` clean, `59 passed`, `ruff check .` clean.
- The §11 cross-reference is real: `docs/1_instructions.md`'s "Submission
  method" section literally says "Matches the shared standard's §11
  (notebook-based submission)" and names `scripts/submit_kaggle.sh` /
  `api.competition_submit_code(...)` — Codex's kernel-native-submission
  requirement isn't a new invention, it's already the documented
  competition submission method.
- README staleness is real: the Status badge and section still say
  "Scaffolding only as of 2026-08-09 — no EDA/baseline Kaggle run yet,"
  despite Phase 1 and Phase 2 both being complete with real results.
- The "unchecked boxes are historical, not unstarted work" claim is real:
  both `docs/superpowers/plans/*.md` files have **every** checkbox
  unchecked, including steps we know are done (e.g. repo-setup's own
  commit steps, weak-label-evaluation's — both fully implemented,
  merged, and archived). This project's plan-writing convention never
  checks these boxes in place; confirms it's a template artifact, not a
  live tracker.
- No `03_baseline_modeling.ipynb` or `notebooks/kernels/baseline-modeling/`
  exists yet — the proposed renumbering is free of conflict.

**One real architecture-level concern:** round 2's "Remove
`NOTEBOOK_VERSION`, `IS_KAGGLE`, environment diagnostics, internal
workflow notes, and printed filesystem paths" is ambiguous in a way that
could regress real behavior, not just trim output. Checked the actual
config cell (`01_eda.ipynb`, mirrored in `02_weak_label_evaluation.ipynb`):
`IS_KAGGLE` isn't only a printed diagnostic — it gates an `if/else` where
the `else` branch is `raise RuntimeError("This notebook only runs on
Kaggle -- ...")`. `docs/0_coding_standards.md`'s "Notebook Style" section
requires exactly this: an `IS_KAGGLE` check that "raises immediately with
a clear message if run anywhere other than Kaggle (this project has no
local execution path)." If the Phase 3A design/implementation reads
"remove IS_KAGGLE" as deleting that guard rather than just its `print`
line, `03_baseline_modeling.ipynb` loses its fail-fast off-Kaggle error
and would instead fail with a confusing `FileNotFoundError` deep in a
`pd.read_csv` call if ever run somewhere the data isn't mounted — a real
regression from a guard this project already relies on and has a written
standard for.

**Requested resolution, not a rejection of the architecture:** the Phase
3A design should keep the `if IS_KAGGLE: ... else: raise RuntimeError(...)`
guard exactly as-is, and only drop the `print(f"IS_KAGGLE={IS_KAGGLE}")`
diagnostic line (bundled with `NOTEBOOK_VERSION`'s print, which has no
functional role and is safe to remove outright). `docs/0_coding_standards.md`'s
"Notebook Style" section should be updated to say the guard is retained
but its value is no longer printed, rather than implying the whole
concept is removed.

**No other architecture-level objections.** The Phase 3A→3B→3C
decomposition, the single end-to-end `03_baseline_modeling.ipynb` (no
eval/submission mode split — OOF diagnostics and the final test-set
prediction are just sequential sections of one linear notebook, not two
code paths to keep in sync), the output-free/aggregate-only policy, and
the kernel-native submission mechanism are all sound and consistent with
this project's existing standards and Phase 2's established practice.

**Next action:** Codex folds the `IS_KAGGLE` clarification into the
`docs/0_coding_standards.md` update it already owns, then proceeds to
write the Phase 3A design doc per round 1's design-issues list. Claude
reviews that design next, per round 1's explicit request (validation
contract, fold-safety, fixed model configuration, Kaggle offline
dependency/submission path, scope boundary).
