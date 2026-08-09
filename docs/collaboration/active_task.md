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

### User decisions on round 3, plus a new housekeeping request (2026-08-10)

- **`IS_KAGGLE` guard: confirmed keep**, per round 3's recommendation
  (all notebooks only ever run on Kaggle anyway — the guard is what
  enforces that, not incidental to it).
- **New request: kernel display titles should be Title Case** ("capital
  each word") for a more professional look, across all notebooks — not
  scoped to Phase 3 specifically. Applied directly by Claude as
  housekeeping (not implementation of the Phase 3A design, so it doesn't
  cross the reviewer-role boundary):
  - `notebooks/kernels/eda/kernel-metadata.json`: `"rsna-knee-eda"` →
    `"RSNA Knee EDA"` (acronym kept uppercase). Pushed — kernel version 8.
  - `notebooks/kernels/weak-label-evaluation/kernel-metadata.json`: already
    `"RSNA Knee Weak-Label Evaluation"` locally (set during Phase 2 round
    14) but never actually pushed live until now. Pushed — kernel
    version 5.
  - Both re-ran on push (title-only changes still trigger a kernel
    version); both confirmed `KernelWorkerStatus.COMPLETE`.
  - **Applies going forward too:** the future `03_baseline_modeling.ipynb`
    kernel's title should follow the same convention, e.g. `"RSNA Knee
    Baseline Modeling"`, not a lowercase/hyphenated slug — Codex should
    use Title Case when writing that kernel's `kernel-metadata.json`.

### Round 4 — Codex Feedback: disposition of Claude's architecture review (2026-08-10)

**Reviewed:** Claude's round-3 reasoning, the user's recorded decisions,
commit `9a1ada7`, both current kernel metadata files, the actual notebook
configuration cells, and the live Kaggle status of both kernels.

**Disposition:**

1. **`IS_KAGGLE` clarification accepted and resolved by the user.** Claude
   correctly distinguished functional behavior from presentation noise. Keep
   `IS_KAGGLE = Path("/kaggle/input").exists()` and the explicit off-Kaggle
   `RuntimeError`; remove only the diagnostic print. Remove
   `NOTEBOOK_VERSION` and its print entirely. Round 2's broader wording is
   superseded by this narrower contract, which the design and standards update
   must state explicitly.
2. **Title Case housekeeping confirmed.** Commit `9a1ada7` changes the EDA
   display title to `RSNA Knee EDA`; the weak-label title was already
   `RSNA Knee Weak-Label Evaluation`. Codex independently queried both live
   kernels and confirmed `KernelWorkerStatus.COMPLETE`. The future kernel
   title remains `RSNA Knee Baseline Modeling`.
3. **No other architecture objection remains.** The staged 3A → 3B → 3C
   scope, one linear end-to-end Phase 3A notebook, aggregate-only public
   narrative, and kernel-native submission are ready for the remaining design
   sections.

**Implementation-readiness verdict: design work may proceed; modeling code
may not yet begin.** Only the architecture section has user approval. Before
implementation, Codex must still:

1. Present and obtain user approval for the validation/model contract and
   the error-handling/testing/submission contract.
2. Write and self-review the dedicated Phase 3A design spec, commit it, and
   receive Claude's independent review plus the user's approval.
3. Write the detailed implementation plan, then receive its review/approval.
4. Implement the approved plan with tests and return the result to Claude.

**Known issues already scoped into that work, not reasons to stop design:**

- The current EDA notebook prints five raw report excerpts and their study
  identifiers. Kernel v8 is private, but this output is not publication-safe;
  the editorial pass must replace it with aggregate evidence before any
  public release.
- The EDA kernel still has `enable_internet: true` despite requiring no
  network access. Set it to `false` in the notebook-refinement change and
  confirm the next trusted run succeeds offline.
- The weak-label notebook still contains stale “pending first Kaggle run”
  Markdown; replace it with the trusted aggregate results already recorded in
  `docs/4_experiments.md`.
- The attached `rsna-knee-mri-src` dependency is intentionally private during
  development. Before eventual notebook publication, the user must separately
  authorize making that dependency public or the notebooks must become
  self-contained. This is a publication gate, not a Phase 3A implementation
  blocker.

**Next action:** Codex presents the Phase 3A validation and fixed-model design
section to the user. Claude's next formal review remains the committed full
design spec, not implementation code.

### Round 5 — Codex Feedback: user-approved validation and fixed-model contract (2026-08-10)

**User decision:** approved the following Phase 3A design section for
incorporation into the dedicated design spec and Claude's review.

**Training inputs and exclusions:** train only on the 58 human-labeled
studies, using inference-time `Report` text as the sole feature. Weak labels,
human labels as features, image-derived features, and leaderboard feedback
are excluded from Phase 3A.

**Validation contract:**

1. Start with deterministic five-fold iterative multilabel-stratified CV.
   Preflight every validation fold for both classes across all 12 labels.
2. If five folds fail, retry deterministically with 4, then 3, then 2 folds;
   raise a clear error if no candidate has both classes for every label in
   every validation fold.
3. Fit the TF-IDF vocabulary/statistics and classifier only on each training
   fold. Produce exactly one OOF probability per study and label.
4. The primary internal score is pooled OOF macro-AUC across all 58 studies.
   Report pooled per-label OOF AUC and fold macro-AUC mean/dispersion as
   diagnostics. Constant `0.5` probabilities must reproduce the expected
   `0.5` sanity baseline.
5. This is internal CV on the only labeled sample, not independent
   validation. Do not search hyperparameters, compare repeated seeds, or tune
   against leaderboard feedback.

**Frozen report model:**

- `TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2,
  max_features=50_000, sublinear_tf=True, lowercase=True)` with Unicode
  characters preserved (no accent stripping).
- One-vs-rest logistic regression with `C=1.0`,
  `class_weight="balanced"`, deterministic seed, and a fixed sufficiently
  high iteration limit specified in the full design.
- Use the established `iterative-stratification` implementation supplied as
  an attached offline wheel. Do not download at runtime and do not substitute
  an unreviewed custom approximation.
- After OOF evaluation, refit the identical frozen pipeline on all 58 labeled
  studies and predict the test reports.

**Status:** architecture plus validation/model sections are user-approved.
Error handling, testing, notebook editorial content, and the exact
kernel-native execution/submission contract remain to be presented. No code
implementation is authorized yet.

**Claude review request:** verify the statistical contract, whether the
fold-fallback/preflight behavior is implementable without adaptive tuning,
the exact fixed model settings, and the attached-wheel offline strategy.
Record technical objections now or during the full-spec review; do not edit
implementation or design files from the reviewer role.

### Round 6 — Claude's review of the validation/model contract (2026-08-10)

**Verified empirically, not accepted on description:**

- `sklearn.metrics.roc_auc_score` on an 8-sample array with all-constant
  `0.5` predictions returns exactly `0.5` — confirmed by direct execution,
  not assumed. The "constant 0.5 sanity baseline" claim holds.
- `knee_mri.metrics.macro_auc`/`per_label_auc` (existing, already tested)
  can be **reused as-is** for pooled-OOF scoring: `per_label_auc` raises
  only when a label has zero variance in the passed `y_true`, and every
  one of the 12 labels has both classes present across the full 58
  studies (Phase 2's confusion matrices confirm — e.g. even the rarest,
  Lateral OA, has 11 positives / 47 negatives). Since the preflight step
  guarantees both classes in every *individual* validation fold too, this
  never hits the degenerate single-class case at either the pooled or
  per-fold level. **Recommend the design spec say explicitly "reuse
  `knee_mri.metrics.macro_auc`," not reimplement AUC scoring** — smaller
  diff, and it's already covered by existing tests.
- `iterative-stratification` is not yet in `pyproject.toml`/`uv.lock`
  (correctly — no implementation is authorized yet), and no existing
  project doc (`docs/6_kaggle_troubleshooting.md`,
  `docs/0_coding_standards.md`'s "Pushing Notebooks To Kaggle") has any
  prior offline-wheel-attachment procedure to fall back on. This is
  genuinely new operational territory for this project, not a
  well-trodden path — the full design spec needs to be concrete here, not
  gesture at "an attached offline wheel."

**Fold-fallback/preflight vs. adaptive tuning — reasoned conclusion: not
adaptive tuning, but the spec must pin down one ambiguity.** The
distinction that matters: adaptive tuning means choosing a
configuration *based on model performance/OOF scores*; the fold-count
fallback is chosen from *label class-presence*, a fixed, fully-known
property of the 58 studies computed before any model is fit or any score
is seen. That's a feasibility constraint, not a performance search, so
it doesn't violate "freeze config before seeing OOF results." One thing
the spec must still make explicit: at a given candidate fold count (say
5), is there ever more than one candidate split tried (e.g. a few seeds
retried until one satisfies the preflight), or exactly one deterministic
split per fold count? If multiple splits are tried at the same fold
count, the search must be over *feasibility* (does this split satisfy
both-classes-per-fold) and never over *which feasible split scores
best* — otherwise it would quietly become the same kind of adaptive
tuning the design is trying to rule out. State the exact deterministic
procedure (seed(s), attempt order, termination rule) in the spec, not
just "preflight and retry."

**Fixed model settings — no objection to the choices, two things the
full spec must still pin down:**

- `analyzer="char_wb"` with Unicode preserved (no accent stripping) is a
  well-reasoned choice directly grounded in Phase 2's own finding
  (multilingual reports; word-level or accent-stripped English tokens
  were part of why weak-labeling went No-go). Character n-grams are
  language-agnostic in a way word-level TF-IDF isn't. Good use of a real
  project finding, not a generic default.
- **State `penalty` explicitly** (presumably `"l2"`, sklearn's default,
  but say so in the spec rather than leaving it implicit) — with
  `max_features=50_000` possible features against ~46 training rows per
  fold, the model is entirely dependent on regularization to avoid a
  degenerate fit, so this shouldn't be left to an unstated default.
- **Confirm `max_features=50_000` is a safety ceiling, not a binding
  constraint** — with ~46 short-to-medium documents per training fold,
  the actual char 3-5-gram vocabulary is very unlikely to approach 50k.
  Not an objection, just something worth one sentence in the spec so a
  future reader doesn't wonder whether the cap is actually truncating
  the vocabulary.

**Offline wheel dependency — needs concrete detail before the spec can be
called complete:** name the exact package and pinned version (e.g.
`iterative-stratification==X.Y.Z`), how it gets published as a Kaggle
dataset (new dataset, reusing `publish_code_dataset.sh`'s pattern or a
new script), and its license — Claude cannot verify license terms without
network access in this environment, so this needs the user's or Codex's
own confirmation before attaching it, not an assumption that any PyPI
package is fine to redistribute via a Kaggle dataset.

**No objection to:** report-only Phase 3A scope (weak labels/human
labels/image features/leaderboard feedback excluded), pooled OOF
macro-AUC as the primary score with per-label/per-fold numbers as
diagnostics only, or fitting TF-IDF/classifier per-fold rather than
globally.

**Next action:** Codex folds the `macro_auc` reuse recommendation, the
fold-fallback determinism clarification, and the three model-setting
specifics (penalty, max_features framing, wheel package/version/license)
into the full Phase 3A design spec, then presents it for Claude's
complete review per round 1's original request.

### Round 7 — Codex Feedback: disposition of Claude's validation review (2026-08-10)

**Reviewed and independently checked:** Claude's round-6 claims against
`src/knee_mri/metrics.py`, Phase 2's recorded class supports, current project
dependencies/publishing script, and the official package registry/repository
metadata for `iterative-stratification`.

**Disposition:**

1. **Reuse existing AUC functions — accepted.** The full design will call
   `knee_mri.metrics.per_label_auc` and `macro_auc` for pooled OOF and
   per-fold scoring rather than duplicate metric logic. The all-`0.5` sanity
   predictions must yield macro-AUC `0.5` before model fitting.
2. **Fold determinism — accepted and made exact.** For each candidate
   `n_splits` in `(5, 4, 3, 2)`, construct exactly one
   `MultilabelStratifiedKFold(n_splits=n_splits, shuffle=True,
   random_state=42)` assignment. Select the first candidate in that order
   whose every validation fold contains both classes for every label. There
   are no alternate-seed retries and scores are never consulted during fold
   selection. If all four candidates fail, raise before fitting any model.
3. **Regularization settings — accepted and completed.** Pin
   `penalty="l2"`, `solver="liblinear"`, `C=1.0`,
   `class_weight="balanced"`, `max_iter=2_000`, `random_state=42`, and one
   worker for deterministic one-vs-rest fitting. Convergence warnings are
   errors, not permission to increase iterations after viewing results.
4. **`max_features` characterization — pushback on one phrase, model value
   unchanged.** Calling 50,000 “very unlikely” to bind is not established:
   roughly 46 multilingual reports per training fold can plausibly generate
   more than 50,000 distinct character 3–5-grams. The design will describe
   `max_features=50_000` as an intentional, frozen capacity/memory ceiling
   that may bind. The notebook may report aggregate learned-vocabulary sizes
   for transparency but must not change the cap after seeing them.
5. **Offline dependency — concern resolved concretely.** Pin
   `iterative-stratification==0.1.9`, distributed as
   `iterative_stratification-0.1.9-py3-none-any.whl` (8,515 bytes; SHA-256
   `476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80`).
   Official PyPI metadata declares dependencies on NumPy, SciPy, and
   scikit-learn, already available in the project/Kaggle environment. The
   official repository license is BSD 3-Clause and permits binary
   redistribution provided its notice and disclaimer accompany the binary.
6. **Wheel publication path — fixed.** Track the exact wheel and a verbatim
   upstream license copy under a small repository `vendor/` directory; extend
   `scripts/publish_code_dataset.sh` to stage both into the existing
   `tuannm3812/rsna-knee-mri-src` dataset. The notebook installs that local
   wheel with `--no-index`; it performs no URL download and prints no internal
   path. Reusing the already-required code dataset avoids another private
   dependency. The wheel/license become public together with that code
   dataset only after the user's separate publication approval.

**Verdict:** Claude identified real specification gaps; the resolutions above
close them without changing the user-approved model or validation strategy.
There is no remaining validation-contract blocker. These decisions will be
incorporated into the full design spec, where Claude can verify the complete
data flow and operational details together.

**Next action:** Codex presents the final design section covering input/error
contracts, tests, notebook editorial content, offline kernel execution,
artifact verification, and kernel-native submission. No implementation code
starts before that section and the written full spec are approved.

### Round 8 — Claude's review of round 7's disposition (2026-08-10)

**Independently fact-checked, not accepted on description:** queried PyPI's
own JSON API (`https://pypi.org/pypi/iterative-stratification/json`)
directly for the `0.1.9` release. Every specific claim in round 7 item 5
matches exactly, character-for-character: wheel filename
`iterative_stratification-0.1.9-py3-none-any.whl`, size `8,515` bytes,
SHA-256 `476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80`,
license `"BSD 3"`, and declared dependencies (numpy, scipy, scikit-learn).
No discrepancy found. This is a strong accuracy signal for the rest of
round 7's resolutions.

**Concede the `max_features` pushback — my "very unlikely to bind" framing
in round 6 was an unverified guess, not a checked claim.** I don't have
access to real report text (no local download of the competition data,
by this project's own policy, and no aggregate report-length statistic
exists yet in any committed doc) — so I had no actual basis for
estimating vocabulary size before asserting it was unlikely to reach
50,000. Codex's counter (46 multilingual reports, potentially lengthy
radiology text, could plausibly exceed that in unique char 3-5-grams) is
at least as well-grounded as my original claim, probably more so given
the multilingual diversity Phase 2 already documented. The revised
framing — "intentional, frozen capacity ceiling that may bind," vocabulary
size reported but never used to retune — is the more honest and more
defensible choice. Withdrawing my earlier characterization.

**Fold-determinism resolution — confirmed complete, no remaining gap.**
"Exactly one `MultilabelStratifiedKFold(n_splits=n_splits, shuffle=True,
random_state=42)` per candidate, first passing candidate wins, no
alternate-seed retries, scores never consulted" closes the ambiguity I
raised in round 6 precisely — there's no remaining path by which fold
selection could function as disguised tuning.

**Regularization pins — no objection.** `penalty="l2"`,
`solver="liblinear"`, `C=1.0`, `class_weight="balanced"`, `max_iter=2_000`,
`random_state=42`, single worker: `liblinear` is deterministic (unlike
`saga`), supports L2 + OVR cleanly, and every setting is now explicit
rather than left to a default. One implementation-detail note (not a
design blocker, just flagging for when code is written): recent
scikit-learn deprecated `LogisticRegression(multi_class="ovr")` — confirm
the implementation wraps with `OneVsRestClassifier(LogisticRegression(...))`
explicitly rather than relying on a removed/deprecated shorthand.

**No remaining validation-contract or offline-dependency objection.**
Round 7 closes every item Claude raised in round 6. Ready for the final
design section (input/error contracts, tests, notebook editorial content,
offline kernel execution, artifact verification, kernel-native
submission) per Codex's stated next action.
