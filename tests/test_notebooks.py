from __future__ import annotations

import ast
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]


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


def test_eda_notebook_is_valid_and_output_free() -> None:
    notebook = _load_json("notebooks/01_eda.ipynb")

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["name"] == "python3"
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell.get("execution_count") is None
            assert cell.get("outputs", []) == []


def test_eda_notebook_retains_guard_without_internal_diagnostics() -> None:
    notebook = _load_json("notebooks/01_eda.ipynb")
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
    assert "sample_reports" not in code
    assert "PatientSex" not in code
    assert "head" not in _called_names(code)
    assert "sample" not in _called_names(code)


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


def test_eda_notebook_interprets_each_aggregate_result() -> None:
    notebook = _load_json("notebooks/01_eda.ipynb")

    for cell_index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell.get("source", []))
        if "display(" not in source and "plt.show()" not in source:
            continue
        next_cell = notebook["cells"][cell_index + 1]
        assert next_cell["cell_type"] == "markdown"
        assert "Interpretation" in "".join(next_cell.get("source", []))


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

    assert metadata["id"] == "tuannm3812/rsna-knee-eda"
    assert metadata["title"] == "RSNA Knee Abnormality Detection — EDA"
    assert metadata["code_file"] == "01_eda.ipynb"
    assert metadata["is_private"] is True
    assert metadata["enable_gpu"] is False
    assert metadata["enable_tpu"] is False
    assert metadata["enable_internet"] is False
