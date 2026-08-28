from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]

NOTEBOOK_PATHS = (
    "notebooks/01_eda.ipynb",
    "notebooks/02_weak_label_evaluation.ipynb",
    "notebooks/03_baseline_modeling.ipynb",
    "notebooks/04_image_baseline_preflight.ipynb",
    "notebooks/05_image_baseline.ipynb",
)


def _load_json(relative_path: str) -> dict:
    return json.loads((REPO_ROOT / relative_path).read_text())


def _code_source(notebook: dict) -> str:
    return "\n\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )


def _markdown_source(notebook: dict) -> str:
    return "\n\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "markdown"
    )


def _called_names(code: str) -> list[str]:
    names = []
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.append(node.func.attr)
    return names


# -- Generic policy checks, parameterized across every public notebook --


@pytest.mark.parametrize("notebook_path", NOTEBOOK_PATHS)
def test_notebook_is_valid_and_output_free(notebook_path: str) -> None:
    notebook = _load_json(notebook_path)

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["name"] == "python3"
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell.get("execution_count") is None
            assert cell.get("outputs", []) == []


@pytest.mark.parametrize("notebook_path", NOTEBOOK_PATHS)
def test_notebook_retains_guard_without_internal_diagnostics(notebook_path: str) -> None:
    notebook = _load_json(notebook_path)
    code = _code_source(notebook)
    tree = ast.parse(code)

    assigned_names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else [node.target]
        )
        if isinstance(target, ast.Name)
    }
    raised_exceptions = {
        node.exc.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
    }

    assert "IS_KAGGLE" in assigned_names
    assert "SEED" in assigned_names
    assert "RuntimeError" in raised_exceptions
    assert "NOTEBOOK_VERSION" not in code
    assert "print" not in _called_names(code)
    assert "http://" not in code and "https://" not in code


@pytest.mark.parametrize("notebook_path", NOTEBOOK_PATHS)
def test_notebook_avoids_raw_report_and_row_level_display(notebook_path: str) -> None:
    notebook = _load_json(notebook_path)
    code = _code_source(notebook)

    assert "sample_reports" not in code
    assert "head" not in _called_names(code)
    assert "sample" not in _called_names(code)


@pytest.mark.parametrize("notebook_path", NOTEBOOK_PATHS)
def test_notebook_interprets_each_aggregate_result(notebook_path: str) -> None:
    notebook = _load_json(notebook_path)

    for cell_index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell.get("source", []))
        if "display(" not in source and "plt.show()" not in source:
            continue
        next_cell = notebook["cells"][cell_index + 1]
        assert next_cell["cell_type"] == "markdown"
        assert "Interpretation" in "".join(next_cell.get("source", []))


# Repository/planning language that describes review workflow or internal
# state rather than the analysis -- found leaking into public prose four
# separate times (weak-label, baseline-modeling, EDA, then the image
# baseline preflight), each under slightly different exact wording. Checked
# as one consolidated policy across every public notebook rather than
# per-notebook ad hoc phrases.
INTERNAL_WORKFLOW_PHRASES = (
    "committed output-free",
    "design spec",
    "real fork",
    "not a formality",
    "not-yet-scoped",
    "src/knee_mri",
    "separately reviewed",
    "trusted",
    "review workflow",
)


# Citations into the project's own review history and process documents.
# These read as bookkeeping to anyone outside the project and carry no
# analytical content, so they are matched by shape rather than by an
# ever-growing list of exact phrases.
INTERNAL_PROVENANCE_PATTERNS = (
    r"\bround \d+",
    r"\bfinding \d+",
    r"\bthe specification\b",
    r"\brelease gate",
    r"\brelease contract\b",
    r"\bsign-off\b",
    r"-approved\b",
)


@pytest.mark.parametrize("notebook_path", NOTEBOOK_PATHS)
def test_notebook_prose_cites_no_internal_provenance(notebook_path: str) -> None:
    """Public prose should carry the reasoning, never the paper trail.

    Naming the round a decision was made in, or the gate it has to clear,
    tells a reader nothing about the data and everything about a process
    they cannot see.
    """
    markdown = _markdown_source(_load_json(notebook_path))

    for pattern in INTERNAL_PROVENANCE_PATTERNS:
        match = re.search(pattern, markdown, re.IGNORECASE)
        assert match is None, f"internal provenance in prose: {match.group(0)!r}"


@pytest.mark.parametrize("notebook_path", NOTEBOOK_PATHS)
def test_notebook_avoids_internal_workflow_language(notebook_path: str) -> None:
    notebook = _load_json(notebook_path)
    markdown = _markdown_source(notebook)

    for phrase in INTERNAL_WORKFLOW_PHRASES:
        assert phrase not in markdown


# -- EDA-specific checks --


def test_eda_notebook_displays_only_aggregate_objects() -> None:
    notebook = _load_json("notebooks/01_eda.ipynb")
    code = _code_source(notebook)
    tree = ast.parse(code)
    displayed_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "display" and len(node.args) == 1:
                argument = node.args[0]
                if isinstance(argument, ast.Name):
                    displayed_names.append(argument.id)

    assert displayed_names
    assert set(displayed_names) <= {
        "overview",
        "file_shapes",
        "train_schema",
        "column_glossary",
        "protocol_combinations",
        "prevalence_table",
        "series_summary",
        "plane_counts",
        "sequence_summary",
        "report_summary",
        "orthographic_counts",
        "slice_summary",
    }
    assert "PatientSex" not in code


def test_eda_notebook_schema_section_covers_all_five_competition_files() -> None:
    notebook = _load_json("notebooks/01_eda.ipynb")
    code = _code_source(notebook)

    for filename in (
        "train.csv",
        "test.csv",
        "sample_submission.csv",
        "train_series.csv",
        "test_series.csv",
    ):
        assert filename in code


def test_eda_notebook_correctly_scopes_report_column_to_train_and_test() -> None:
    notebook = _load_json("notebooks/01_eda.ipynb")
    markdown = _markdown_source(notebook)

    # Report exists in both train.csv and test.csv; only the 12 targets are
    # train-only. Pin the corrected sentence so this distinction can't
    # silently regress back to implying Report is train-exclusive too.
    assert "`test.csv` shares the same" in markdown
    assert "never carries targets" in markdown


def test_eda_notebook_has_public_facing_narrative() -> None:
    notebook = _load_json("notebooks/01_eda.ipynb")
    markdown = _markdown_source(notebook)

    assert markdown.startswith("# RSNA Knee Abnormality Detection — Exploratory Data Analysis")
    assert "4,407" in markdown
    assert "58" in markdown
    assert "internal cross-validation" in markdown
    assert "Findings, Limitations, and Modeling Implications" in markdown
    assert "docs/" not in markdown


def test_eda_kernel_metadata_is_private_cpu_and_offline() -> None:
    metadata = _load_json("notebooks/kernels/eda/kernel-metadata.json")

    assert metadata["id"] == "tuannm3812/rsna-knee-abnormality-detection-eda"
    assert metadata["title"] == "RSNA Knee Abnormality Detection — EDA"
    assert metadata["code_file"] == "01_eda.ipynb"
    assert metadata["is_private"] is True
    assert metadata["enable_gpu"] is False
    assert metadata["enable_tpu"] is False
    assert metadata["enable_internet"] is False


# -- Weak-label-evaluation-specific checks --


def test_weak_label_notebook_displays_only_aggregate_objects() -> None:
    notebook = _load_json("notebooks/02_weak_label_evaluation.ipynb")
    code = _code_source(notebook)
    tree = ast.parse(code)
    displayed_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "display" and len(node.args) == 1:
                argument = node.args[0]
                if isinstance(argument, ast.Name):
                    displayed_names.append(argument.id)

    assert displayed_names
    assert set(displayed_names) <= {
        "study_counts",
        "decision_rule",
        "baseline_metrics",
        "fixed_metrics",
        "taxonomy_table",
        "comparison",
        "allowlist_summary",
    }


def test_weak_label_notebook_has_trusted_conclusion() -> None:
    notebook = _load_json("notebooks/02_weak_label_evaluation.ipynb")
    markdown = _markdown_source(notebook)

    assert markdown.startswith(
        "# RSNA Knee Abnormality Detection — Weak-Label Evaluation"
    )
    assert "0/12" in markdown
    assert "No-go" in markdown
    assert "58" in markdown
    assert "7.7" in markdown
    # Public-facing prose intentionally renders the unlabeled-study count
    # as 4,349 for readability; keep the check semantic rather than
    # coupling it to punctuation.
    assert "4349" in markdown.replace(",", "")
    assert "pending" not in markdown.lower()
    assert "docs/" not in markdown


def test_weak_label_notebook_does_not_claim_ascii_only_is_english() -> None:
    notebook = _load_json("notebooks/02_weak_label_evaluation.ipynb")
    markdown = _markdown_source(notebook)

    # An orthographic bucket observes characters, not language; ASCII-only
    # text is not necessarily English. Must state the character-set/
    # language distinction explicitly, not just avoid the wrong claim.
    assert "skew more English" not in markdown
    assert "character-set difference" in markdown


def test_weak_label_kernel_metadata_is_private_cpu_and_offline() -> None:
    metadata = _load_json("notebooks/kernels/weak-label-evaluation/kernel-metadata.json")

    assert metadata["id"] == "tuannm3812/rsna-knee-weak-label-evaluation"
    assert metadata["title"] == "RSNA Knee Abnormality Detection — Weak-Label Evaluation"
    assert metadata["code_file"] == "02_weak_label_evaluation.ipynb"
    assert metadata["is_private"] is True
    assert metadata["enable_gpu"] is False
    assert metadata["enable_tpu"] is False
    assert metadata["enable_internet"] is False


# -- Baseline-modeling-specific checks --


def test_baseline_notebook_displays_only_aggregate_objects() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    code = _code_source(notebook)
    tree = ast.parse(code)
    displayed_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "display" and len(node.args) == 1:
                argument = node.args[0]
                if isinstance(argument, ast.Name):
                    displayed_names.append(argument.id)

    assert displayed_names
    assert set(displayed_names) <= {
        "frozen_contract",
        "schema_overview",
        "data_summary",
        "selected_fold_summary",
        "fold_sizes",
        "fold_validation_positive_counts",
        "sanity_check",
        "fold_diagnostics",
        "pooled_summary",
        "per_label_summary",
        "test_probability_summary",
        "submission_summary",
    }


def test_baseline_notebook_imports_every_package_boundary() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    code = _code_source(notebook)

    for interface in (
        "prepare_modeling_inputs",
        "select_multilabel_folds",
        "build_report_vectorizer",
        "build_report_classifier",
        "cross_validate_report_model",
        "fit_report_model",
        "build_submission",
    ):
        assert interface in code


def test_baseline_notebook_verifies_wheel_before_import() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    code = _code_source(notebook)

    assert "iterative_stratification-0.1.9-py3-none-any.whl" in code
    assert (
        "476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80" in code
    )
    assert 'importlib.metadata.version("iterative-stratification")' in code
    assert "--no-index" in code
    assert "http://" not in code and "https://" not in code


def test_baseline_notebook_wheel_setup_precedes_every_knee_mri_import() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    code = _code_source(notebook)

    # Full required order: checksum -> install -> return-code check ->
    # installed-version check -> sys.path.insert -> first knee_mri import.
    # Checking only the endpoints would still pass if, say, the version
    # check silently moved after the package import.
    checksum_index = code.index("hashlib.sha256(wheel_path.read_bytes())")
    install_index = code.index("subprocess.run(")
    returncode_index = code.index("install_result.returncode != 0")
    version_check_index = code.index(
        'importlib.metadata.version("iterative-stratification")'
    )
    sys_path_index = code.index("sys.path.insert(")
    first_knee_mri_import_index = code.index("from knee_mri")

    assert (
        checksum_index
        < install_index
        < returncode_index
        < version_check_index
        < sys_path_index
        < first_knee_mri_import_index
    )
    # Both the wheel and the source package are discovered under the same
    # attached dataset root, not two independent whole-tree searches.
    assert "_dataset_root.rglob(WHEEL_NAME)" in code


def test_baseline_notebook_wheel_install_failure_is_path_free() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    code = _code_source(notebook)

    # check=True would embed the full command (including the resolved
    # wheel path) in CalledProcessError's message; the return code must
    # be checked explicitly instead, with stderr suppressed too.
    assert "check=True" not in code
    assert "stderr=subprocess.DEVNULL" in code
    assert "install_result.returncode != 0" in code
    assert "except OSError" in code


def test_baseline_notebook_has_constant_sanity_assertion() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    code = _code_source(notebook)

    assert "pd.DataFrame(0.5, index=y.index, columns=LABEL_COLUMNS)" in code
    assert "assert macro_auc(y, constant_predictions) == 0.5" in code


def test_baseline_notebook_writes_exactly_one_submission_path() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    code = _code_source(notebook)

    assert code.count("to_csv(") == 1
    assert '"/kaggle/working/submission.csv"' in code


def test_baseline_notebook_uses_only_frozen_settings() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    code = _code_source(notebook)

    # No inline hyperparameter that could silently diverge from the
    # frozen build_report_vectorizer()/build_report_classifier() factories
    # or the frozen (5, 4, 3, 2) fold candidates.
    assert "TfidfVectorizer(" not in code
    assert "LogisticRegression(" not in code
    assert "candidate_splits=" not in code


def test_baseline_notebook_asserts_no_result_before_the_trusted_run() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    markdown = _markdown_source(notebook)

    assert "computed live" in markdown
    assert "none is asserted here in advance" in markdown


def test_baseline_notebook_frozen_contract_is_complete() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    code = _code_source(notebook)

    # Every approved frozen setting must be displayed, not a subset --
    # this section's whole purpose is exposing the complete configuration.
    for attribute in (
        "_vectorizer.analyzer",
        "_vectorizer.ngram_range",
        "_vectorizer.min_df",
        "_vectorizer.max_features",
        "_vectorizer.sublinear_tf",
        "_vectorizer.lowercase",
        "_vectorizer.strip_accents",
        "_classifier.estimator.penalty",
        "_classifier.estimator.solver",
        "_classifier.estimator.C",
        "_classifier.estimator.class_weight",
        "_classifier.estimator.max_iter",
        "_classifier.estimator.random_state",
        "_classifier.n_jobs",
    ):
        assert attribute in code

    # The fold candidates/seed rows and the explicit seed=SEED call are
    # part of the same "complete contract" correction -- protect them
    # alongside the factory attributes, not as a separate, droppable fact.
    assert '{"Setting": "Fold candidates"' in code
    assert '{"Setting": "Fold seed", "Value": SEED}' in code
    assert "select_multilabel_folds(y, seed=SEED)" in code


def test_baseline_notebook_does_not_claim_low_auc_is_a_bug() -> None:
    notebook = _load_json("notebooks/03_baseline_modeling.ipynb")
    markdown = _markdown_source(notebook)

    # A correctly-wired model can legitimately score below 0.5 (e.g. if
    # anti-predictive) -- only the constant-0.5 wiring/metric check
    # itself is guaranteed, not every later score.
    assert "not proof of a scoring error" in markdown
    assert "would indicate a scoring problem" not in markdown
    assert "12 separate small-sample fold scores" not in markdown


def test_baseline_kernel_metadata_is_private_cpu_and_offline() -> None:
    metadata = _load_json("notebooks/kernels/baseline-modeling/kernel-metadata.json")

    assert metadata["id"] == "tuannm3812/rsna-knee-abnormality-detection-report-baseline"
    assert metadata["title"] == "RSNA Knee Abnormality Detection — Report Baseline"
    assert metadata["code_file"] == "03_baseline_modeling.ipynb"
    assert metadata["is_private"] is True
    assert metadata["enable_gpu"] is False
    assert metadata["enable_tpu"] is False
    assert metadata["enable_internet"] is False
    assert metadata["dataset_sources"] == ["tuannm3812/rsna-knee-mri-src"]
    assert metadata["competition_sources"] == ["rsna-knee-abnormality-detection"]


# -- Image-baseline-preflight-specific checks --


def test_preflight_notebook_displays_only_aggregate_objects() -> None:
    notebook = _load_json("notebooks/04_image_baseline_preflight.ipynb")
    code_source = _code_source(notebook)
    tree = ast.parse(code_source)
    displayed_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "display" and len(node.args) == 1:
                argument = node.args[0]
                if isinstance(argument, ast.Name):
                    displayed_names.append(argument.id)

    assert displayed_names
    assert set(displayed_names) <= {
        "agreement_summary",
        "plane_coverage_summary",
        "codec_availability",
        "geometry_summary",
        "study_laterality_summary",
        "orientation_distribution_summary",
        "orientation_threshold_summary",
        "orientation_axis_summary",
        "orientation_sign_summary",
        "plane_selection_summary",
        "pixel_spacing_summary",
        "slice_count_summary",
        "decode_by_transfer_syntax",
        "transfer_syntax_census",
        "census_coverage",
        "environment_summary",
        "timing_summary",
    }


def test_preflight_notebook_never_stores_study_or_series_identifiers() -> None:
    notebook = _load_json("notebooks/04_image_baseline_preflight.ipynb")
    code_source = _code_source(notebook)

    # audit_rows/audit_df must only ever collect the aggregate SeriesAudit
    # fields, never a StudyInstanceUID/SeriesInstanceUID/path column.
    assert "StudyInstanceUID\":" not in code_source
    assert "SeriesInstanceUID\":" not in code_source
    assert "study_id\":" not in code_source
    assert "series_dir\":" not in code_source


def test_preflight_notebook_orientation_audit_is_aggregate_and_complete() -> None:
    notebook = _load_json("notebooks/04_image_baseline_preflight.ipynb")
    code_source = _code_source(notebook)

    assert "patient_lr_axis_metrics" in code_source
    for threshold in ("0.80", "0.85", "0.90", "0.95"):
        assert threshold in code_source
    for field in (
        "orientation_distribution",
        "orientation_threshold_counts",
        "orientation_axis_counts",
        "orientation_sign_by_plane_and_side",
    ):
        assert f'"{field}"' in code_source


def test_preflight_kernel_metadata_is_private_gpu_offline_with_dinov2() -> None:
    metadata = _load_json("notebooks/kernels/image-baseline-preflight/kernel-metadata.json")

    assert metadata["id"] == "tuannm3812/rsna-knee-image-baseline-preflight-audit"
    assert metadata["title"] == "RSNA Knee — Image Baseline Preflight Audit"
    assert metadata["code_file"] == "04_image_baseline_preflight.ipynb"
    assert metadata["is_private"] is True
    assert metadata["enable_gpu"] is True
    # Kaggle allocates the accelerator nondeterministically when only
    # enable_gpu is set. Version 7 landed on a Tesla P100 (sm_60), which the
    # installed PyTorch does not support (sm_70 and above), and the run died
    # after the dataset mount. Earlier runs had silently been getting T4s.
    # Pinned so the hardware is part of the reproducibility contract rather
    # than a coin flip.
    assert metadata["machine_shape"] == "NvidiaTeslaT4"
    assert metadata["enable_tpu"] is False
    assert metadata["enable_internet"] is False
    assert metadata["dataset_sources"] == ["tuannm3812/rsna-knee-mri-src"]
    assert metadata["competition_sources"] == ["rsna-knee-abnormality-detection"]
    assert metadata["model_sources"] == ["metaresearch/dinov2/PyTorch/small/1"]


# -- Image-baseline-specific checks --


def test_image_baseline_notebook_displays_only_aggregate_objects() -> None:
    notebook = _load_json("notebooks/05_image_baseline.ipynb")
    tree = ast.parse(_code_source(notebook))
    displayed_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "display" and len(node.args) == 1:
                argument = node.args[0]
                if isinstance(argument, ast.Name):
                    displayed_names.append(argument.id)

    assert displayed_names
    assert set(displayed_names) <= {
        "frozen_contract",
        "environment_summary",
        "extraction_telemetry",
        "fold_identity",
        "pooled_summary",
        "per_label_summary",
        "flag_variance",
        "uncertainty_summary",
        "variant_summary",
        "density_summary",
        "dense_per_label",
        "pooling_summary",
        "pooling_per_label",
        "concat_summary",
        "concat_per_label",
        "displacement_summary",
        "timing_by_stratum",
        "timing_summary",
        "submission_summary",
    }


def test_image_baseline_notebook_writes_exactly_one_submission_path() -> None:
    code = _code_source(_load_json("notebooks/05_image_baseline.ipynb"))

    assert code.count("to_csv(") == 1
    assert '"/kaggle/working/submission.csv"' in code


def test_image_baseline_notebook_verifies_the_wheel_before_importing_knee_mri() -> None:
    """Same ordering guarantee notebook 03 pins: checksum, install, return
    code, version, sys.path, and only then the first knee_mri import.
    """
    code = _code_source(_load_json("notebooks/05_image_baseline.ipynb"))

    checksum_index = code.index("hashlib.sha256(wheel_path.read_bytes())")
    install_index = code.index("subprocess.run(")
    returncode_index = code.index("install_result.returncode != 0")
    version_index = code.index('importlib.metadata.version("iterative-stratification")')
    sys_path_index = code.index("sys.path.insert(")
    first_import_index = code.index("from knee_mri")

    assert (
        checksum_index
        < install_index
        < returncode_index
        < version_index
        < sys_path_index
        < first_import_index
    )
    assert "check=True" not in code
    assert "stderr=subprocess.DEVNULL" in code


def test_image_baseline_notebook_uses_the_vendored_processor_statistics() -> None:
    """Section 6 forbids a remembered-constant fallback, so the notebook must
    load the attached model's own statistics and must not restate them.
    """
    code = _code_source(_load_json("notebooks/05_image_baseline.ipynb"))

    assert "load_processor_statistics" in code
    assert "dinov2-small-preprocessor_config.json" in code
    for forbidden in ("0.485", "0.456", "0.406", "0.229", "0.224", "0.225"):
        assert forbidden not in code


def test_image_baseline_notebook_asserts_the_encoder_is_frozen() -> None:
    code = _code_source(_load_json("notebooks/05_image_baseline.ipynb"))

    assert "requires_grad_(False)" in code
    assert "Encoder trainable parameters" in code


def test_image_baseline_notebook_keeps_the_constant_prediction_sanity_check() -> None:
    code = _code_source(_load_json("notebooks/05_image_baseline.ipynb"))

    assert "constant_predictions" in code
    assert "Metric wiring check failed" in code


def test_image_baseline_notebook_never_stores_identifiers_in_telemetry() -> None:
    code = _code_source(_load_json("notebooks/05_image_baseline.ipynb"))

    assert 'telemetry["study' not in code
    assert 'telemetry["series' not in code
    assert "StudyInstanceUID\":" not in code
    assert "SeriesInstanceUID\":" not in code


def test_image_baseline_kernel_metadata_is_private_gpu_offline_with_dinov2() -> None:
    metadata = _load_json("notebooks/kernels/image-baseline/kernel-metadata.json")

    # Kaggle derives the slug from the TITLE, not the requested id, and
    # silently migrates it -- the same trap round 39 hit. Pinned to the
    # server-assigned slug so a push and a status query cannot diverge.
    assert metadata["id"] == "tuannm3812/rsna-knee-frozen-image-baseline"
    assert metadata["title"] == "RSNA Knee — Frozen Image Baseline"
    assert len(metadata["title"]) <= 50
    assert metadata["code_file"] == "05_image_baseline.ipynb"
    assert metadata["is_private"] is True
    assert metadata["enable_gpu"] is True
    # Kaggle allocates the accelerator nondeterministically when only
    # enable_gpu is set. Version 7 landed on a Tesla P100 (sm_60), which the
    # installed PyTorch does not support (sm_70 and above), and the run died
    # after the dataset mount. Earlier runs had silently been getting T4s.
    # Pinned so the hardware is part of the reproducibility contract rather
    # than a coin flip.
    assert metadata["machine_shape"] == "NvidiaTeslaT4"
    assert metadata["enable_tpu"] is False
    assert metadata["enable_internet"] is False
    assert metadata["dataset_sources"] == ["tuannm3812/rsna-knee-mri-src"]
    assert metadata["competition_sources"] == ["rsna-knee-abnormality-detection"]
    assert metadata["model_sources"] == ["metaresearch/dinov2/PyTorch/small/1"]
