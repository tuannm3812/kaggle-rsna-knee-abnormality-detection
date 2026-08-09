# Weak-Label Evaluation — Design

Date: 2026-08-09
Status: Revised after two rounds of Codex review — pending user approval
(see `docs/7_codex_review_log.md` for the full review/disposition
history)

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
gap (justified below, not decided from baseline numbers — see
"Decision rule"), and reports a concrete go/no-go verdict rather than
open-ended iteration.

## Constraint: competition data never leaves Kaggle

Same "Kaggle-only execution" principle as the rest of this project
(`docs/0_coding_standards.md`), extended to this work specifically: **no
raw report text is copied into this git repo** — not into notebooks,
docs, or test fixtures. Competition data-usage terms don't permit
redistributing the dataset, and copying substantial verbatim excerpts
into git history (especially given the winners' obligation to eventually
open-source solution code) would do exactly that. This extends beyond
raw text, per Codex's review:

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

### 1. `extract_weak_labels`'s return contract changes to 3-state

`src/knee_mri/labels.py::extract_weak_labels` currently returns
`dict[str, int]` (always 0 or 1). It changes to `dict[str, int | None]`:

- `None` ("abstain") — no textual evidence found for this label at all
  (today's behavior forces this to `0`, which is wrong: absence of
  evidence is not evidence of absence).
- `0` — the label's keyword(s) matched, but immediately preceded by a
  negation cue (see below) — a confident negative assertion.
- `1` — the label's keyword(s) matched with no negation cue — a
  positive assertion (the common case for an explicitly mentioned
  finding in a radiology report).

This is a genuine interface change, made now rather than later because
(per Codex's review) `extract_weak_labels` has **no consumers yet** —
`split_labeled_studies` operates on human-label completeness in
`train.csv` and does not consume the extractor's output at all, so this
change has zero migration cost today and only grows more expensive to
make later once something depends on the old contract.

**Assertion detection mechanism**: for each pattern match, check a short
window of characters immediately before the match (e.g. 30 characters)
against a small set of negation cue words/phrases per language actually
confirmed present (English: `no`, `without`, `negative for`; German:
`kein`/`keine`; further languages added only if the error taxonomy below
shows they matter — not speculatively). If a cue is found in the window,
the match contributes to a negative (`0`) rather than positive (`1`)
determination for that label.

`LABEL_COLUMNS` (the 12-name schema) is unaffected by this change — only
the *value type* per label changes.

### 2. `src/knee_mri/weak_label_evaluation.py` (new, renamed per Codex review)

```python
def weak_label_metrics(true_df: pd.DataFrame) -> pd.DataFrame:
    """Score extract_weak_labels against ground-truth labels.

    For each of the 12 LABEL_COLUMNS, runs extract_weak_labels on every
    row's Report and compares the result to that row's true label.

    Confusion counts treat "abstain" (extract_weak_labels returning
    None for a label) as neither a positive nor a confident-negative
    prediction:
        TP = predicted 1, true 1
        FP = predicted 1, true 0
        FN = predicted 0 or None (abstain), true 1  -- abstaining on a
             true positive is still a missed recovery, counted the same
             as a confidently-wrong negative for recall purposes
        TN = predicted 0, true 0
        abstained_on_negative = predicted None, true 0  -- reported
             separately, not folded into TN (an abstain is not a
             confirmed-correct negative, just an uninformative one)

    precision = TP / (TP + FP)
    recall = TP / (TP + FN)
    coverage = (predictions that are not None) / total rows for that
        label -- how much of the data this label's extraction actually
        produces a confident (non-abstain) prediction for.

    Precision/recall/coverage are all 0.0 (not an error) when their
    denominator is 0 -- unlike metrics.py::per_label_auc, which
    intentionally raises on a degenerate single-class column (a
    different metric with a different degenerate case; do not conflate
    the two, and do not change per_label_auc/macro_auc as part of this
    work).

    Also computes a Wilson score 95% confidence interval for precision
    and for recall per label (see "Decision rule" below for why, and
    the exact formula/parameters used).

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

    Returns:
        A DataFrame indexed by label, one row per LABEL_COLUMNS entry,
        with columns tp, fp, fn, tn, abstained_on_negative, support
        (tp+fp+fn+tn, i.e. non-abstained rows), precision, recall,
        coverage, precision_ci_low, precision_ci_high, recall_ci_low,
        recall_ci_high.

    Raises:
        ValueError: On any of the three schema violations above.
    """
```

Tested locally with small synthetic report/label fixtures (hand-written
sentences, not real competition data) covering: a clean true positive, a
clean true negative, a negated mention (true negative, correctly
detected via the assertion-status check), an abstain case (report
mentions nothing about a label, ground truth is either 0 or 1 — verify
abstain is excluded from TP/FP/TN and counted toward FN when ground
truth is 1), a false positive (unnegated keyword present but ground
truth is negative — a real extractor miss, not a schema issue), a
zero-support label (precision/recall/coverage all `0.0`, no exception),
and each of the three `ValueError` schema-violation cases (duplicate
`StudyInstanceUID`, non-binary label value, missing/non-string
`Report`).

### 3. Wilson score interval and the concrete decision rule

Codex's review correctly flagged "Wilson score or similar" and an
unspecified stop criterion as not actually predefined decisions. This
section is the predefined decision rule, written before the Kaggle run:

- **Interval method**: Wilson score interval (not the normal
  approximation, which is unreliable at small `n` and can produce
  bounds outside `[0, 1]` — exactly the small-`n` regime expected here),
  95% confidence, computed with `statsmodels.stats.proportion
  .proportion_confint(count, nobs, alpha=0.05, method="wilson")` (adds
  `statsmodels` to `pyproject.toml`'s `dev` or a new `stats` optional
  dependency group — small, common, already a `scikit-learn`
  transitive dependency in this environment).
- **Adequate support threshold**: a label's precision (or recall)
  estimate only counts toward the aggregate decision below if its
  denominator (`TP + FP` for precision; `TP + FN` for recall) is `>= 5`.
  Below that, the Wilson interval is wide enough to be uninformative for
  a go/no-go call, though it is still reported in the output table.
- **Primary metric for the decision: precision.** A false positive
  actively corrupts a pseudo-label used for training later; a missed
  positive (abstain or false negative) is comparatively less harmful,
  especially once training code can treat abstain as "no signal" rather
  than "confirmed negative" (a later piece of work, out of scope here,
  but the 3-state contract above exists specifically to make that
  possible).
- **Go/no-go rule**, evaluated after the assertion-detection fix (there
  is no "choose between candidate fixes" step anymore — assertion
  detection is the fix, justified directly by Codex's review argument
  in the Problem section above, not chosen from baseline numbers):
  - **Go** if at least 4 of the 12 labels reach adequate precision
    support (`TP + FP >= 5`) **and** the macro-average precision across
    those adequately-supported labels is `>= 0.7`.
  - **No-go** otherwise (either too few labels have adequate support to
    judge at all, or the supported labels' precision is too low to
    trust). A no-go result means: stop iterating on regex-based
    extraction in this project phase. Record the result in
    `docs/3_strategy.md` as a decision point — the next step would be a
    fundamentally different approach (multilingual assertion-extraction
    model, or probabilistic weak supervision combining multiple
    labeling functions), not another regex tweak. Do not attempt a
    second regex iteration in the same pass if the first result is
    no-go.
  - These thresholds (`5` for support, `0.7` for precision, `4/12` for
    label coverage) are reasonable defaults, not derived from this
    project's data — flagged explicitly as adjustable if the user
    disagrees, rather than presented as objectively correct.
- Recall and coverage are reported for every label regardless of the
  go/no-go outcome (context for how much of the 4349 report-only studies
  would get a usable label at all), but do not gate the decision.

### 4. Error taxonomy and language-distribution checks (Kaggle-only, counts only)

Two additional notebook cells, both producing only aggregate counts:

- **Error taxonomy**: for each false positive/negative, bucket by
  `(label, coarse report-language, failure cause)` where failure cause
  is one of `{keyword-not-present, assertion-status-wrong,
  abstained-on-true-positive}` — print counts per bucket only, never the
  underlying report text. This is what actually explains *why*
  precision/recall land where they do, rather than leaving it as an
  unexplained aggregate number.
- **Language-distribution comparison**: a coarse per-report language
  heuristic (reuse the non-ASCII-fraction check already in
  `01_eda.ipynb`, or a lightweight `langdetect`-style call if that
  proves too coarse) run over both the 58 labeled studies and a sample
  of the 4349 unlabeled studies, compared as counts/proportions only.
  If the labeled set's language mix doesn't resemble the unlabeled set's,
  state that explicitly as a caveat on how far the go/no-go result
  generalizes — do not silently assume it does.

### 5. `notebooks/02_weak_label_evaluation.ipynb` (new, renamed)

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
4. **Baseline measurement**: call `weak_label_metrics` on the labeled
   subset against the *current* (pre-fix) `extract_weak_labels`; print
   the full per-label table (including Wilson CIs, support, coverage).
5. Error taxonomy and language-distribution cells (section 4 above).
6. Apply the assertion-detection fix to `extract_weak_labels` (this
   requires the fixed `src/knee_mri` to already be published — see
   below); re-run the same `weak_label_metrics` call; print the after
   table.
7. Apply the go/no-go rule from section 3; print the verdict explicitly
   (`"GO"` or `"NO-GO"` plus the numbers that produced it).
8. Insight cells with real, timeless findings only (no report excerpts,
   no per-study identifiers beyond aggregate counts).

Needs its own `notebooks/kernels/weak-label-evaluation/
kernel-metadata.json`, pushed via `scripts/push_kaggle_kernel.sh
weak-label-evaluation`. Since `weak_label_evaluation.py` and the fixed
`extract_weak_labels` live in `src/knee_mri`, this kernel needs
`dataset_sources: ["tuannm3812/rsna-knee-mri-src"]`, and the dataset
must be republished (`scripts/publish_code_dataset.sh version "add
weak_label_evaluation, assertion-status extract_weak_labels"`) with the
finished, tested code **before** this notebook's first push — implement
and unit-test the code changes from Design sections 1-2 above (the
`extract_weak_labels` contract change and `weak_label_evaluation.py`)
locally first, publish once, then run the notebook once end-to-end (not
iteratively re-publishing mid-notebook-run the way `01_eda.ipynb`'s
mount-path debugging needed to).

### 6. `docs/4_experiments.md` and `docs/3_strategy.md` entries

- `docs/4_experiments.md`: one entry — baseline per-label table
  (precision/recall/coverage/support/CI), the go/no-go verdict, the
  after table, language-distribution finding, and a one-line conclusion.
- `docs/3_strategy.md`: only written to if the result is **no-go** — a
  short decision-point entry naming the next candidate approach
  (multilingual assertion-extraction model or probabilistic weak
  supervision) as a future strategy fork, not implemented in this pass
  either way.

## Out of scope for this pass

- A second regex iteration within this same pass if the first result is
  no-go — the go/no-go rule exists specifically to prevent open-ended
  regex tweaking; a no-go result is itself the deliverable (a documented
  decision point), not a trigger to keep trying.
- Multilingual keyword expansion beyond what the error taxonomy shows is
  needed for languages already confirmed present — no speculative
  coverage for languages not yet observed.
- Applying weak labels (positive/negative/abstain) to actually expand
  the training set for a baseline model, or designing how a future
  training pipeline should treat the abstain state — that's the next
  piece of work after this one, not part of it.
- Any change to `metrics.py`'s `per_label_auc`/`macro_auc` — those score
  continuous predictions against ground truth for the competition
  metric; `weak_label_metrics` is a separate concern (scoring a 3-state
  weak-label *extractor* against ground truth) and must not be confused
  with or merged into the competition metric.
