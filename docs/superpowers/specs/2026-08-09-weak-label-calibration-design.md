# Weak-Label Evaluation — Design

Date: 2026-08-09
Status: Final revision after 4 rounds of Codex review — pending user
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
gap (justified above, not decided from baseline numbers — see "Decision
rule"), and reports a concrete go/no-go verdict rather than open-ended
iteration.

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

## Design

### 1. Two named extractors, so one notebook run can measure both

`weak_label_metrics` (section 2) takes an extractor function as an
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
- **`extract_weak_labels`**: the new, fixed implementation (below),
  `dict[str, int | None]`.

Both live in `src/knee_mri/labels.py`, both are unit-tested, both are
published together, and the notebook calls `weak_label_metrics` twice —
once per extractor — against the same published package, in the same
run.

### 2. `extract_weak_labels`'s new contract and mechanism

Returns `dict[str, int | None]`:

- `None` ("abstain") — no textual evidence found for this label at all.
- `1` — an unqualified positive mention (the label's keyword matched,
  with no negation or normal-assertion cue nearby).
- `0` — a negated or normal-asserting mention (the label's keyword
  matched, with a negation/normal-assertion cue nearby — see below;
  these two cue types are not distinguished in the output, only in the
  error-taxonomy diagnostic in section 4).

This is a genuine interface change, made now rather than later because
`extract_weak_labels` has **no consumers yet** — `split_labeled_studies`
operates on human-label completeness in `train.csv` and does not consume
the extractor's output at all, so this change has zero migration cost
today and only grows more expensive to make later once something depends
on the old contract.

**Mechanism — clause-scoped, bidirectional cue detection:**

1. Split `report_text` into clauses on `[.;:\n]` (sentence/clause
   boundaries — a cue belonging to an adjacent clause about a different
   finding must never be attributed to this match).
2. For each of a label's keyword pattern matches, determine which clause
   contains it.
3. Within that clause only, and within a further fixed maximum distance
   of 40 characters on each side of the match (so one very long clause
   still can't pull in an unrelated cue), search for any cue in a single
   combined cue list (case-insensitive): `no`, `not`, `without`,
   `negative for`, `absence of`, `rule out`, `intact`, `preserved`,
   `unremarkable`, `normal`, `within normal limits`. A hit on either
   side classifies this mention as **qualified** (negated or
   normal-asserting); no hit classifies it as **unqualified**
   (asserted-positive).
   - **Intentionally English-only for this pass.** Multilingual cue
     lists are out of scope here (see "Out of scope" below) — the error
     taxonomy (section 4) will show whether non-English reports have a
     materially different assertion-detection failure pattern, which
     would justify a follow-up pass with real evidence behind it, rather
     than speculative translated cue lists now.
4. Collect the set of mention classifications found for the label across
   the whole report (a label's keyword can match more than once). Resolve:
   - No mentions at all → `None` (abstain).
   - Only unqualified mention(s) → `1`.
   - Only qualified mention(s), or qualified + unqualified mixed → `0`
     (a qualified mention dominates an unqualified one — a report that
     both mentions the anatomy plainly and separately negates/normalizes
     it is read as negative).

   **Open question, flagged for Codex confirmation before implementation
   (not yet resolved):** round 4's hierarchy included a fourth case —
   "explicit abnormal assertion AND negated/normal-asserting mention for
   the same label → `None`, ambiguous" — distinct from "qualified +
   unqualified mixed → `0`". This design collapses that distinction:
   with only two mention categories (qualified/unqualified) as defined
   above, "qualified + unqualified mixed" and "explicit abnormal +
   qualified" would be the same case, and resolving it to `0` (qualified
   dominates) rather than `None` (ambiguous) is a simplification, not
   something derived from round 4's stated hierarchy. Whether this
   simplification is acceptable, or whether a real third mention
   category (a stronger "explicit abnormal assertion" distinct from a
   bare "unqualified mention") is needed to preserve the intended
   ambiguous/abstain case, needs Codex's confirmation before this is
   implemented as written.

`LABEL_COLUMNS` (the 12-name schema) is unaffected by this change — only
the *value type* per label changes.

### 3. `src/knee_mri/weak_label_evaluation.py` (new)

```python
def weak_label_metrics(
    true_df: pd.DataFrame,
    extractor: Callable[[str], dict[str, int | None]],
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
    see "Decision rule" below).

    Validates true_df at the evaluation boundary before scoring
    anything, and raises ValueError (not a silent skip) on:
      - a duplicate StudyInstanceUID (would silently double-count in
        every confusion tally)
      - any LABEL_COLUMNS value that isn't exactly 0 or 1 (including
        NaN)
      - a missing or non-string Report value
    These checks run even though split_labeled_studies is the only
    current caller and already prevents most of them -- validation
    belongs at the function's own boundary, not only upstream.

    Args:
        true_df: A frame with StudyInstanceUID, Report, and all 12
            LABEL_COLUMNS as ground-truth 0/1 values (e.g. the labeled
            subset of train.csv from split_labeled_studies).
        extractor: A weak-label extractor function with the same
            signature as extract_weak_labels (e.g.
            extract_weak_labels_naive or extract_weak_labels itself) --
            passed explicitly so the same function can score either
            extractor from the same published package in the same run.

    Returns:
        A DataFrame indexed by label, one row per LABEL_COLUMNS entry,
        with columns tp, fp, tn, fn_confident, abstained_on_positive,
        abstained_on_negative, actual_positive_support,
        predicted_positive_support, non_abstained_count, precision,
        recall, coverage, precision_ci_low, precision_ci_high,
        recall_ci_low, recall_ci_high.

    Raises:
        ValueError: On any of the three schema violations above.
    """
```

Tested locally with small synthetic report/label fixtures (hand-written
sentences, not real competition data) covering: a clean true positive, a
clean true negative, a negated mention (true negative, correctly
detected), a post-match cue (`"ACL intact"` — the exact case Codex's
review identified as missed by a before-only window), cue leakage across
a clause boundary (a cue for a *different* finding in an adjacent clause
must not affect this label's classification), repeated concordant
mentions of the same label (multiple matches, all unqualified — still
resolves to `1`), an abstain case (no mention at all — verify it's
excluded from `tp`/`fp`/`tn`/`fn_confident` and counted toward
`abstained_on_positive` or `abstained_on_negative` correctly depending on
truth), a false positive (unqualified keyword present but ground truth
is negative — a real extractor miss, not a schema issue), a
zero-support label (precision/recall/coverage all `0.0`, no exception),
and each of the three `ValueError` schema-violation cases (duplicate
`StudyInstanceUID`, non-binary label value, missing/non-string
`Report`).

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
  center = (k + z**2 / 2) / (n + z**2)
  margin = z * sqrt((k * (n - k) / n + z**2 / 4) / n) / (1 + z**2 / n)
  lower, upper = center - margin, center + margin
  ```

  where `n` is the metric's own denominator (`predicted_positive_support`
  for precision, `actual_positive_support` for recall) and `k` is `tp`.
  Undefined (`n == 0`) → interval is `(0.0, 0.0)`, matching the
  point-estimate convention above.
- **Adequate support threshold**: a label only counts toward the
  go/no-go decision if `predicted_positive_support >= 5`. Below that,
  the interval is wide enough to be uninformative for a decision, though
  still reported in the output table.
- **Primary metric for the decision: precision.** A false positive
  actively corrupts a pseudo-label used for training later; a missed
  positive (abstain or confident false negative) is comparatively less
  harmful, especially once training code can treat abstain as "no
  signal" rather than "confirmed negative" (a later piece of work, out
  of scope here, but the 3-state contract exists specifically to make
  that possible).
- **Go/no-go rule**, evaluated once, after both extractors have been run
  in the same notebook execution:
  - For each label with `predicted_positive_support >= 5`, compute the
    Wilson **lower bound** of precision. The label individually "passes"
    if that lower bound is `>= 0.55`.
  - **Go** if at least 4 of the 12 labels individually pass.
  - **No-go** otherwise.
  - **No macro-averaging** — passing is per-label and counted, not
    averaged. Averaging lower bounds across labels could let a few
    strong labels conceal one untrustworthy label that would still be
    used downstream for that label specifically; a per-label pass/fail
    count doesn't have that failure mode.
  - **Why `0.55`, not a rounder number like `0.6` or `0.7`**: calibrated
    directly against the `support >= 5` threshold's own achievable
    range. At `n=5`, even a flawless `5/5` result has a Wilson lower
    bound of only ≈`0.566`; at `n=6`, `6/6` ≈`0.610`; at `n=8`, `7/8`
    ≈`0.529`. A `0.60` threshold would make `support >= 5` internally
    self-contradictory — claiming 5 examples is enough evidence to judge
    a label, while requiring a bound that even zero-error evidence at
    that sample size usually can't clear. `0.55` is intentionally
    conservative: it demands close to spotless evidence at the smallest
    supported sample sizes, and a no-go result from it means "the
    evidence is insufficient," not "the extractor is proven bad" —
    appropriate for a diagnostic gate at this data scale.
  - A no-go result means: stop iterating on regex-based extraction in
    this project phase. Record the result in `docs/3_strategy.md` as a
    decision point — the next step would be a fundamentally different
    approach (multilingual assertion-extraction model, or probabilistic
    weak supervision combining multiple labeling functions), not another
    regex tweak. Do not attempt a second regex iteration in the same
    pass if the result is no-go.
  - These thresholds (`5` support, `0.55` lower-bound precision, `4/12`
    label count) are this design's frozen decision rule, set before any
    real result is viewed. They may still be changed during user review
    of this spec — but not after the Kaggle run produces real numbers.
- Recall and coverage are reported for every label regardless of the
  go/no-go outcome (context for how much of the 4349 report-only studies
  would get a usable label at all), but do not gate the decision.

### 5. Error taxonomy and language-distribution checks (Kaggle-only, counts only)

Two additional notebook cells, both producing only aggregate counts:

- **Error taxonomy**: for each false positive/false negative/abstained-
  on-positive case, bucket by `(label, coarse report-language, failure
  cause)` where failure cause is one of `{no-keyword-match,
  qualified-when-should-be-unqualified, unqualified-when-should-be-
  qualified, abstained-on-true-positive}` — print counts per bucket
  only, never the underlying report text. This is what actually explains
  *why* precision/recall land where they do, and directly surfaces
  whether the English-only cue-list limitation (section 2) is a real
  problem worth a follow-up pass.
- **Language-distribution comparison**: a coarse **orthographic/script
  bucket** heuristic — explicitly *not* language identification, framed
  honestly as such in the notebook and in `docs/4_experiments.md`:
  - Greek script (Unicode ranges `Ͱ`–`Ͽ`, `ἀ`–`῿`) →
    `greek`.
  - Contains `ä`/`ö`/`ü`/`ß` (case-insensitive) → `german`.
  - Contains `ğ`/`ş`/`ı`/`İ` → `turkish`.
  - Contains `č`/`ć`/`đ`/`š`/`ž` → `croatian`.
  - Matches more than one of the above → `mixed`.
  - Entirely ASCII → `ascii_only` (not claimed to be English — merely
    undifferentiated from it by this heuristic).
  - Any other non-ASCII Latin-script text → `other_latin_undetermined`.

  Run over both the 58 labeled studies and a sample of the 4349
  unlabeled studies, compared as counts/proportions of these buckets
  only. If the labeled set's bucket mix doesn't resemble the unlabeled
  set's, state that explicitly as a caveat on how far the go/no-go
  result generalizes — do not silently assume it does.

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
   extract_weak_labels)`; print the full per-label table. Both this and
   step 4 run against the same published package — no republish between
   them.
6. Error taxonomy and language-distribution cells (section 5 above),
   computed against the fixed extractor's errors.
7. Apply the go/no-go rule from section 4; print the verdict explicitly
   (`"GO"` or `"NO-GO"` plus the exact numbers that produced it).
8. Insight cells with real, timeless findings only (no report excerpts,
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
  CI), the go/no-go verdict with the exact numbers, the language-
  distribution/error-taxonomy findings, and a one-line conclusion.
- `docs/3_strategy.md`: Phase 2's entry is updated with the real result
  either way (go or no-go) — a no-go result additionally gets a short
  decision-point note naming the next candidate approach (multilingual
  assertion-extraction model or probabilistic weak supervision) as a
  future strategy fork, not implemented in this pass either way.

## Out of scope for this pass

- A second regex iteration within this same pass if the result is
  no-go — the go/no-go rule exists specifically to prevent open-ended
  regex tweaking; a no-go result is itself the deliverable (a documented
  decision point), not a trigger to keep trying.
- Multilingual cue/keyword expansion — the assertion-detection cue list
  in section 2 is intentionally English-only for this pass; the error
  taxonomy will show whether this is a real, evidenced gap worth a
  follow-up, rather than speculative translated cue lists added now.
- A more sophisticated resolution mechanism for genuinely conflicting
  same-label mentions beyond the qualified/unqualified split in section
  2 — not attempted speculatively; a candidate for a follow-up only if
  the real error taxonomy shows it matters.
- Applying weak labels (positive/negative/abstain) to actually expand
  the training set for a baseline model, or designing how a future
  training pipeline should treat the abstain state — that's the next
  piece of work after this one, not part of it.
- Any change to `metrics.py`'s `per_label_auc`/`macro_auc` — those score
  continuous predictions against ground truth for the competition
  metric; `weak_label_metrics` is a separate concern (scoring a 3-state
  weak-label *extractor* against ground truth) and must not be confused
  with or merged into the competition metric.
