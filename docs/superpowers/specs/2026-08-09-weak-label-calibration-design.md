# Weak-Label Evaluation — Design

Date: 2026-08-09
Status: Codex-confirmed ready after 8 review rounds — pending user
approval (see `docs/collaboration/active_task.md` for the full
review/discussion history)

## Problem

`docs/2_eda_insights.md`'s first trusted EDA run (kernel
`tuannm3812/rsna-knee-eda` v7) found that only **58 of 4407 training
studies (1.3%) carry human-annotated labels**; the remaining 4349 have
only `Report` text. `src/knee_mri/labels.py::extract_weak_labels` exists
to derive weak labels for those 4349 studies, but it is currently a naive,
English-only regex extractor with two documented limitations: no negation
handling, and — more fundamentally, per Codex's review — it detects an
anatomical **mention**, not an **asserted abnormality**. `"ACL intact"`
reads as positive today regardless of negation handling, because the
extractor matches on the anatomy keyword alone. The same EDA run confirmed
reports are genuinely multilingual (German, Turkish, Croatian, Greek, and
English observed in a 5-report sample), so the English-only gap is real,
not hypothetical, but is secondary to the assertion-detection gap:
extending keyword coverage before fixing assertion detection would
amplify a broken mechanism rather than fix it.

This work is named **weak-label evaluation**, not "calibration" — no
probability calibration happens here. It measures the extractor against
real ground truth (the 58 labeled studies), fixes the assertion-detection
gap, and produces a **persisted per-label allowlist** (which specific
labels are trustworthy enough to weak-label with) rather than a single
project-wide go/no-go boolean.

## Constraint: competition data never leaves Kaggle

Same "Kaggle-only execution" principle as the rest of this project
(`docs/0_coding_standards.md`), extended to this work specifically: **no
raw report text is copied into this git repo** — not into notebooks,
docs, or test fixtures. Competition data-usage terms don't permit
redistributing the dataset, and copying substantial verbatim excerpts
into git history (especially given the winners' obligation to eventually
open-source solution code) would do exactly that. This extends beyond
raw text:

- Only aggregate counts/metrics leave Kaggle — never a table of
  per-study predictions, never printed report excerpts (not even
  truncated/paraphrased ones close enough to reconstruct real text).
- `02_weak_label_evaluation.ipynb` is committed **output-free** — unlike
  `01_eda.ipynb`, which keeps outputs once trusted, this notebook's cells
  touch real report text directly, so no execution output is ever
  committed to the repo, and outputs are cleared before every push.
- The corresponding Kaggle kernel stays `is_private: true` (same as all
  kernels in this project) and its output artifacts are never downloaded
  locally beyond the aggregate numbers transcribed into
  `docs/4_experiments.md`.
- Study identifiers (`StudyInstanceUID`) may appear in aggregate counts
  (e.g. "12 studies") but never as a list that could be joined back to
  specific report text outside Kaggle.
- The error-taxonomy mechanism (section 5) is specifically designed so
  no manual/human inspection of real report text is ever needed — see
  that section for why, and what was rejected instead.

## Design

### 1. Two named extractors, so one notebook run can measure both

`weak_label_metrics` (section 3) takes an extractor function as an
explicit parameter rather than hardcoding a call to
`extract_weak_labels` internally. This exists because publishing the
fixed `src/knee_mri` package before the notebook's first run — required
so the notebook can import it at all — would otherwise make the
*pre-fix* behavior unrecoverable: there is no way to measure "before" a
change using a package that already has the change baked in. Two
functions solve this without needing two separate publish/run cycles:

- **`extract_weak_labels_naive`**: the extractor exactly as it exists in
  the repository today — unchanged, `dict[str, int]`, always `0` or `1`,
  no assertion detection. This is the true "before" — not a
  re-implementation, the literal current function, renamed and frozen as
  the historical baseline for this one comparison. (Candidate for
  removal in a later cleanup once the before/after result is recorded in
  `docs/4_experiments.md` — not this pass's concern.)
- **`extract_weak_labels`**: the new, fixed implementation (section 2),
  `dict[str, int | None]` — a thin wrapper over an internal resolver
  (also section 2) that keeps the richer diagnostic detail needed for
  the error taxonomy (section 5) out of the public return value.

Both live in `src/knee_mri/labels.py`, both are unit-tested, both are
published together, and the notebook calls `weak_label_metrics` twice —
once per extractor — against the same published package, in the same
run.

### 2. `extract_weak_labels`'s new contract and mechanism

Public contract: returns `dict[str, int | None]`.

- `None` ("abstain") — no textual evidence found for this label, or the
  only evidence found was uncertain (see below).
- `1` — an unqualified positive mention (the label's keyword matched,
  with no negation, normal-assertion, or uncertainty cue nearby).
- `0` — a negated or normal-asserting mention dominates (see resolution
  order below).

This is a genuine interface change, made now rather than later because
`extract_weak_labels` has **no consumers yet** — `split_labeled_studies`
operates on human-label completeness in `train.csv` and does not consume
the extractor's output at all, so this change has zero migration cost
today and only grows more expensive to make later once something depends
on the old contract.

**Mechanism — clause-scoped, bidirectional, word-bounded cue detection:**

1. Split `report_text` into clauses on `[.;\n]` only — **not** `:`,
   which would incorrectly separate a common heading form like `"ACL:
   intact"` into two clauses, leaving the keyword's own clause with no
   cue to find.
2. For each of a label's keyword pattern matches, determine which clause
   contains it (its `clause_index`).
3. Within that clause only, and within a further fixed maximum distance
   of 40 characters on each side of the match (so one very long clause
   still can't pull in an unrelated cue), search for a cue from three
   categories, each matched as a **word-bounded** phrase (`\b`-delimited
   for alphanumeric cues; `r/o` matched as a whitespace/punctuation-
   delimited literal token, since `\b` doesn't work cleanly around `/`)
   so `"notable"` can never match the cue `"no"`:
   - **Negation** (case-insensitive): `no`, `not`, `without`, `negative
     for`, `absence of`.
   - **Normal assertion** (case-insensitive): `intact`, `preserved`,
     `unremarkable`, `normal`, `within normal limits`.
   - **Uncertain** (case-insensitive): `rule out`, `r/o`, `question of`,
     `possible`, `cannot exclude`. Distinct from negation — `"rule out
     fracture"` means the possibility is being considered, not
     confidently denied.
   - **Intentionally English-only for this pass.** Multilingual cue
     lists are out of scope here (see "Out of scope" below) — the error
     taxonomy (section 5) will show whether non-English reports have a
     materially different assertion-detection failure pattern, which
     would justify a follow-up pass with real evidence behind it, rather
     than speculative translated cue lists now.
4. Each mention is classified into exactly one `kind`: `unqualified` (no
   cue found), `qualified_negation`, `qualified_normal_assertion`, or
   `qualified_uncertain`.
5. **Internal resolver** (not part of `extract_weak_labels`'s public
   return value — see section 5 for why this distinction exists)
   produces, per label:

   ```python
   @dataclass(frozen=True)
   class MentionDiagnostic:
       kind: Literal[
           "unqualified",
           "qualified_negation",
           "qualified_uncertain",
           "qualified_normal_assertion",
       ]
       clause_index: int

   @dataclass(frozen=True)
   class LabelResolution:
       value: int | None
       mentions: tuple[MentionDiagnostic, ...]
   ```

   No clause text, matched text, character offsets, study identifiers,
   or the specific cue string are retained anywhere — only the abstract
   `kind` and which clause (by index, not content) it came from.

6. **Resolution order** (first matching rule wins, applied to the set of
   mention kinds found across all of a label's matches in the report):
   1. No mentions at all → `value = None`.
   2. Any `qualified_negation` or `qualified_normal_assertion` mention
      present (regardless of what else is also present) → `value = 0`.
      A confident qualification is the strongest signal and dominates
      everything else, including an unqualified mention elsewhere in
      the report.
   3. Else, any `qualified_uncertain` mention present (and no confident
      qualification) → `value = None`. Uncertainty language should not
      be forced into a confident positive or negative.
   4. Else (only `unqualified` mention(s)) → `value = 1`.
   - `extract_weak_labels(text)` returns `{label: resolution.value for
     label, resolution in ...}` — the thin public projection.

`LABEL_COLUMNS` (the 12-name schema) is unaffected by this change — only
the *value type* per label changes.

**Accepted simplification (confirmed with Codex, round 5):** this
mechanism does not attempt to distinguish a "bare mention" from a
"stronger explicit abnormal assertion" as two separate unqualified-tier
categories (which would add a genuine ambiguous/conflict resolution
outcome). A real third category would need its own positive-assertion
vocabulary (e.g. `tear`, `rupture`, `sprain`, `identified`, `present`)
distinct from the existing anatomy-name/finding-word `_LABEL_PATTERNS`,
plus label-specific grammatical proximity rules — a materially broader,
speculative extractor design not justified for this bounded pass.
Revisit only if real data specifically motivates it.

### 3. `src/knee_mri/weak_label_evaluation.py` (new)

```python
def weak_label_metrics(
    true_df: pd.DataFrame,
    extractor: Callable[[str], Mapping[str, int | None]],
) -> pd.DataFrame:
    """Score a weak-label extractor against ground-truth labels.

    For each of the 12 LABEL_COLUMNS, runs `extractor` on every row's
    Report and compares the result to that row's true label.

    Per-row prediction is one of {1, 0, None}; truth is {0, 1}. Confusion
    counts:
        tp = predicted 1, true 1
        fp = predicted 1, true 0
        tn = predicted 0, true 0
        fn_confident = predicted 0, true 1
        abstained_on_positive = predicted None, true 1
        abstained_on_negative = predicted None, true 0

    Reported support quantities (kept separate and unambiguous, each
    used as the correct denominator for its own metric/interval):
        actual_positive_support = tp + fn_confident + abstained_on_positive
            (every row where truth is 1 -- recall's denominator; an
            abstain on a true positive is still a missed recovery, so it
            counts here same as a confidently-wrong negative)
        predicted_positive_support = tp + fp
            (every row the extractor called 1 -- precision's denominator,
            unaffected by abstain)
        non_abstained_count = tp + fp + tn + fn_confident
            (rows where the extractor gave a confident 0/1 prediction)
        total_rows = len(true_df)

    precision = tp / predicted_positive_support
    recall = tp / actual_positive_support
    coverage = non_abstained_count / total_rows

    Precision/recall/coverage are all 0.0 (not an error) when their
    denominator is 0 -- unlike metrics.py::per_label_auc, which
    intentionally raises on a degenerate single-class column (a
    different metric with a different degenerate case; do not conflate
    the two, and do not change per_label_auc/macro_auc as part of this
    work).

    Also computes a Wilson score 95% confidence interval for precision
    (n=predicted_positive_support, k=tp) and for recall
    (n=actual_positive_support, k=tp) per label, using a directly
    implemented closed-form Wilson interval (no new runtime dependency —
    see "Decision rule" below), and a boolean `passes_gate` column (see
    "Decision rule").

    Validates true_df at the evaluation boundary before scoring
    anything, and raises ValueError (not a silent skip) on:
      - true_df missing StudyInstanceUID, Report, or any LABEL_COLUMNS
        column
      - true_df has zero rows
      - a duplicate StudyInstanceUID (would silently double-count in
        every confusion tally)
      - any LABEL_COLUMNS value that isn't exactly 0 or 1 (including
        NaN)
      - a missing or non-string Report value
    These checks run even though split_labeled_studies is the only
    current caller and already prevents most of them -- validation
    belongs at the function's own boundary, not only upstream.

    Also validates `extractor`'s output on every call: raises ValueError
    if the returned mapping's keys are not exactly LABEL_COLUMNS, or if
    any value is not in {0, 1, None} -- `extractor` is an arbitrary
    caller-supplied callable (needed so the same function scores both
    extract_weak_labels_naive and extract_weak_labels from one published
    package), so its output must be validated the same as any other
    external input, not trusted implicitly.

    Args:
        true_df: A frame with StudyInstanceUID, Report, and all 12
            LABEL_COLUMNS as ground-truth 0/1 values (e.g. the labeled
            subset of train.csv from split_labeled_studies).
        extractor: A weak-label extractor function with the same
            signature as extract_weak_labels (e.g.
            extract_weak_labels_naive or extract_weak_labels itself) --
            passed explicitly so the same function can score either
            extractor from the same published package in the same run.
            Typed as Mapping (not dict) so extract_weak_labels_naive's
            dict[str, int] return type satisfies the parameter without
            a dict-invariance typing conflict against dict[str, int |
            None].

    Returns:
        A DataFrame indexed by label, one row per LABEL_COLUMNS entry,
        with columns tp, fp, tn, fn_confident, abstained_on_positive,
        abstained_on_negative, actual_positive_support,
        predicted_positive_support, non_abstained_count, total_rows,
        precision, recall, coverage, precision_ci_low,
        precision_ci_high, recall_ci_low, recall_ci_high, passes_gate.

    Raises:
        ValueError: On any of the schema violations above, for either
            true_df or the extractor's output.
    """
```

Module-level constants (frozen decision-rule inputs, see section 4):
`MIN_SUPPORT = 5`, `MIN_PRECISION_LOWER_BOUND = 0.55`.

Tested locally with small synthetic report/label fixtures (hand-written
sentences, not real competition data) covering: a clean true positive, a
clean true negative, a negated mention (true negative, correctly
detected), a post-match cue (`"ACL: intact"` — the exact heading-colon
case Codex's round-6 review identified as broken by naive `:`-splitting),
an uncertain cue (`"rule out fracture"` — resolves to abstain, not
confident-negative), a substring trap (`"notable"` must not trigger the
`"no"` cue), cue leakage across a clause boundary (a cue for a
*different* finding in an adjacent clause must not affect this label's
classification), repeated concordant mentions of the same label
(multiple matches, all unqualified — still resolves to `1`), an abstain
case (no mention at all), a false positive (unqualified keyword present
but ground truth is negative), a zero-support label (precision/recall/
coverage all `0.0`, no exception), each `ValueError` schema-violation
case for `true_df` (missing column, empty input, duplicate
`StudyInstanceUID`, non-binary label value, missing/non-string
`Report`), and each `ValueError` case for a malformed extractor output
(wrong keys, a value outside `{0, 1, None}`).

### 4. Wilson score interval and the concrete decision rule

- **Interval method**: Wilson score interval, 95% confidence,
  implemented directly as a closed-form calculation (not the normal
  approximation, which is unreliable at small `n` and can produce bounds
  outside `[0, 1]` — exactly the small-`n` regime expected here; and not
  via `statsmodels`, which is absent from `pyproject.toml`/`uv.lock` and
  not otherwise needed — a ~5-line formula is small, deterministic,
  offline-safe, and directly unit-testable against known reference
  values):

  ```
  z = 1.959963985  # 95% two-tailed
  p_hat = k / n
  denom = 1 + z**2 / n
  center = (p_hat + z**2 / (2 * n)) / denom
  margin = (z / denom) * sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))
  lower, upper = center - margin, center + margin
  ```

  (Verified against Codex's round-5 reference value: `n=5, k=5` →
  `lower ≈ 0.5655`, matching the `≈0.566` figure cited below. Write the
  unit test for this formula against this exact reference value first.)
- **Adequate support threshold**: `predicted_positive_support >=
  MIN_SUPPORT` (`5`). Below that, the interval is wide enough to be
  uninformative for a decision, though still reported in the output
  table.
- **Primary metric: precision.** A false positive actively corrupts a
  pseudo-label used for training later; a missed positive (abstain or
  confident false negative) is comparatively less harmful, especially
  once training code can treat abstain as "no signal" rather than
  "confirmed negative" (a later piece of work, out of scope here, but
  the 3-state contract exists specifically to make that possible).
- **Per-label gate, not a global boolean**: a label's `passes_gate` is
  `True` if and only if `predicted_positive_support >= MIN_SUPPORT` and
  the Wilson **lower bound** of precision is `>=
  MIN_PRECISION_LOWER_BOUND` (`0.55`). No macro-averaging — averaging
  lower bounds across labels could let a few strong labels conceal one
  untrustworthy label that would still get used downstream for that
  label specifically; a per-label pass/fail doesn't have that failure
  mode.
  - **Why `0.55`, not a rounder number like `0.6` or `0.7`**: calibrated
    directly against `MIN_SUPPORT`'s own achievable range. At `n=5`,
    even a flawless `5/5` result has a Wilson lower bound of only
    ≈`0.566`; at `n=6`, `6/6` ≈`0.610`; at `n=8`, `7/8` ≈`0.529`. A
    `0.60` threshold would make `MIN_SUPPORT = 5` internally self-
    contradictory — claiming 5 examples is enough evidence to judge a
    label, while requiring a bound that even zero-error evidence at
    that sample size usually can't clear. `0.55` is intentionally
    conservative: it demands close to spotless evidence at the smallest
    supported sample sizes.
- **The deliverable is a persisted per-label allowlist** — the list of
  labels where `passes_gate == True` — not a single project-wide
  boolean. Any future work that applies weak labels to expand a
  training set (out of scope for this pass, see below) must only use
  labels on this allowlist; a label not on it stays abstained/
  unavailable for weak-labeling purposes regardless of how many *other*
  labels passed.
- **Project-phase signal** (informational, not a gate on individual
  labels): count how many of the 12 labels are on the allowlist, for
  `docs/3_strategy.md`'s Phase 2 fork. If very few labels pass (a
  threshold worth discussing at that point rather than frozen here,
  since it's about project direction, not per-label correctness), that's
  a signal to stop iterating on regex-based extraction and consider a
  fundamentally different approach (multilingual assertion-extraction
  model, or probabilistic weak supervision combining multiple labeling
  functions) — recorded as a decision point when/if it happens.
- These thresholds (`MIN_SUPPORT = 5`, `MIN_PRECISION_LOWER_BOUND =
  0.55`) are this design's frozen decision rule, set before any real
  result is viewed. They may still change during user review of this
  spec — but not after the Kaggle run produces real numbers.
- Recall and coverage are reported for every label regardless of
  `passes_gate` (context for how much of the 4349 report-only studies
  would get a usable label at all), but do not gate the decision.

### 5. Error taxonomy and orthographic-bucket comparison (Kaggle-only, counts only)

**Why the taxonomy needs the internal resolver, not just
`extract_weak_labels`'s public output:** aggregate precision/recall
alone can't explain *why* extraction failed (negation miscue? wrong
cue-vs-uncertain classification? no keyword at all?). Two ways to get
that explanation were considered: (a) have the resolver expose its
internal mention classification as a diagnostic structure, so the
explanation is mechanically derivable with zero raw-text access ever
needed, or (b) a bounded, explicitly-permitted human-in-the-loop
Kaggle-only triage step (transient inspection of real text during the
notebook session, only aggregate counts committed). Codex's
recommendation (round 7): **(a)**, firmly rejecting (b) as
"irreproducible, introduces reviewer judgment at exactly the smallest
and most consequential sample, and makes leakage prevention depend on
notebook discipline" rather than a mechanical guarantee.

**Error taxonomy**: for each false positive, confident false negative,
or abstained-on-true-positive case, bucket by `(label,
orthographic_bucket, prediction_error, resolution_signature)`, where:

- `prediction_error` is one of `false_positive`, `false_negative`
  (covers both confident-wrong-negative and abstained-on-positive —
  both are "missed the true positive," distinguished by
  `resolution_signature` instead, not a separate axis).
- `resolution_signature` derives mechanically from the set of distinct
  `MentionDiagnostic.kind` values found for that label in that report:
  `no_mention` (empty set), `unqualified_only`, `negation_qualified`,
  `normal_qualified`, `uncertain_qualified` (each a single-kind set), or
  `mixed_qualification` (more than one distinct kind present).
- Cases whose `resolution_signature` cannot mechanically explain the
  mismatch — most notably an `unqualified_only` false positive, where
  the report plainly mentions the finding but ground truth says negative
  — are bucketed as `unknown/report-label-disagreement` rather than
  assumed to be a cue-classification bug. This is deliberate: it avoids
  claiming the report text proves what actually happened when the
  resolver's own signature doesn't support that claim.

Print counts per bucket only — never report text, matched text, or
per-study identifiers.

**Orthographic-bucket comparison** — explicitly *not* language
identification, named and framed honestly as observed character sets,
per round 6's finding that language-named buckets overclaim (e.g. `ö`/
`ü` are shared by German *and* Turkish, not German-exclusive; the
originally-listed Croatian characters aren't Croatian-exclusive among
South Slavic languages either):

- Greek script (Unicode ranges `Ͱ`–`Ͽ`, `ἀ`–`῿`) →
  `greek_script`.
- Contains `ğ`/`ş`/`ı`/`İ` → `latin_with_turkish_chars` (this set is
  distinctive enough among the languages actually observed to keep as
  its own bucket).
- Contains `ä`/`ö`/`ü`/`ß` → `latin_with_german_turkish_umlaut` (named
  to reflect the real overlap, not asserting German specifically).
- Contains `č`/`ć`/`đ`/`š`/`ž` → `latin_with_south_slavic_diacritics`
  (named to reflect the broader language family, not Croatian
  specifically).
- Matches more than one of the above → `mixed_latin_diacritics`.
- Entirely ASCII → `ascii_only` (not claimed to be English — merely
  undifferentiated from it by this heuristic).
- Any other non-ASCII Latin-script text → `other_latin_undetermined`.

Run over the 58 labeled studies and **all 4349 unlabeled studies** (a
full scan of already-loaded CSV report strings is inexpensive — no
sampling, no sample-size/selection-rule question to leave unanswered),
compared as counts/proportions of these buckets only. If the labeled
set's bucket mix doesn't resemble the unlabeled set's, state that
explicitly as a caveat on how far the per-label allowlist generalizes —
do not silently assume it does.

### 6. `notebooks/02_weak_label_evaluation.ipynb` (new)

Kaggle-only, same shape as `01_eda.ipynb`: `IS_KAGGLE` check (raises
immediately if run anywhere else, same as `01_eda.ipynb`), deterministic
seed, `NOTEBOOK_VERSION`, real cells:

1. Purpose statement (including the output-free/no-raw-text policy from
   the Constraint section above, stated inline for anyone reading the
   Kaggle kernel page directly).
2. Config cell — same mount-path resolution as `01_eda.ipynb`
   (`docs/6_kaggle_troubleshooting.md`'s confirmed
   `/kaggle/input/datasets/<owner>/<slug>/src/knee_mri` path).
3. Load `train.csv`, split via `knee_mri.dataset.split_labeled_studies`,
   keep only the 58 labeled rows.
4. **Baseline measurement**: `weak_label_metrics(labeled_df,
   extract_weak_labels_naive)`; print the full per-label table.
5. **Fixed measurement**: `weak_label_metrics(labeled_df,
   extract_weak_labels)`; print the full per-label table, including
   `passes_gate`. Both this and step 4 run against the same published
   package — no republish between them.
6. Error taxonomy cell (section 5), using the internal resolver directly
   (not the public `extract_weak_labels` wrapper) to get
   `MentionDiagnostic` detail for every false positive/negative case.
7. Orthographic-bucket comparison cell (section 5), full 4349-row scan.
8. **Allowlist**: print the explicit list of labels where `passes_gate
   == True`, and the count out of 12, as the actual deliverable of this
   notebook — not a single "GO"/"NO-GO" string.
9. Insight cells with real, timeless findings only (no report excerpts,
   no per-study identifiers beyond aggregate counts).

Needs its own `notebooks/kernels/weak-label-evaluation/
kernel-metadata.json`, pushed via `scripts/push_kaggle_kernel.sh
weak-label-evaluation`. Since `weak_label_evaluation.py` and both
extractors live in `src/knee_mri`, this kernel needs
`dataset_sources: ["tuannm3812/rsna-knee-mri-src"]`, and the dataset
must be republished (`scripts/publish_code_dataset.sh version "add
weak_label_evaluation, extract_weak_labels_naive/extract_weak_labels"`)
with the finished, tested code **before** this notebook's first push —
implement and unit-test the code changes from Design sections 1-3 above
locally first, publish once, then run the notebook once end-to-end (not
iteratively re-publishing mid-notebook-run the way `01_eda.ipynb`'s
mount-path debugging needed to).

### 7. `docs/4_experiments.md` and `docs/3_strategy.md` entries

- `docs/4_experiments.md`: one entry — baseline (naive) per-label table,
  fixed per-label table (both with precision/recall/coverage/support/
  CI/`passes_gate`), **the explicit per-label allowlist** (not just a
  count), the orthographic-bucket comparison finding, and a one-line
  conclusion.
- `docs/3_strategy.md`: Phase 2's entry is updated with the real
  allowlist either way — few or no labels passing additionally gets a
  short decision-point note naming the next candidate approach
  (multilingual assertion-extraction model or probabilistic weak
  supervision) as a future strategy fork, not implemented in this pass
  either way.

## Out of scope for this pass

- A second regex iteration within this same pass — the per-label gate
  and the project-phase signal exist specifically to prevent open-ended
  regex tweaking; the allowlist (however many labels pass) is itself the
  deliverable, not a trigger to keep trying.
- Multilingual cue/keyword expansion — the assertion-detection cue lists
  in section 2 are intentionally English-only for this pass; the error
  taxonomy will show whether this is a real, evidenced gap worth a
  follow-up, rather than speculative translated cue lists added now.
- A more sophisticated resolution mechanism for genuinely conflicting
  same-label mentions beyond the qualified/unqualified/uncertain split
  in section 2 — not attempted speculatively; a candidate for a
  follow-up only if the real error taxonomy shows it matters.
- A human-in-the-loop manual triage step for ambiguous errors — rejected
  in round 7 in favor of the mechanically-derivable resolver-based
  taxonomy; may be revisited as a follow-up *investigation* after a
  low-allowlist result, not as part of this evaluation's committed
  design.
- Applying weak labels (positive/negative/abstain) to actually expand
  the training set for a baseline model, or designing how a future
  training pipeline should treat the abstain state — that's the next
  piece of work after this one, not part of it.
- Any change to `metrics.py`'s `per_label_auc`/`macro_auc` — those score
  continuous predictions against ground truth for the competition
  metric; `weak_label_metrics` is a separate concern (scoring a 3-state
  weak-label *extractor* against ground truth) and must not be confused
  with or merged into the competition metric.
