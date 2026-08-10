from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

WHEEL_NAME = "iterative_stratification-0.1.9-py3-none-any.whl"
WHEEL_SHA256 = "476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80"


def test_vendored_iterative_stratification_wheel_is_exact_release() -> None:
    wheel = Path("vendor") / WHEEL_NAME

    assert wheel.stat().st_size == 8_515
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == WHEEL_SHA256


def test_vendored_iterative_stratification_license_is_bsd_3_clause() -> None:
    license_text = Path("vendor/iterative-stratification-LICENSE.txt").read_text()

    assert "BSD 3-Clause License" in license_text
    assert "Redistribution and use in source and binary forms" in license_text
    assert "THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS" in license_text


def test_code_dataset_publisher_stages_vendor_directory(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    captured_stage = tmp_path / "captured-stage"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "stage_dir=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ $1 == '-p' ]]; then stage_dir=$2; shift 2; else shift; fi\n"
        "done\n"
        "cp -R \"${stage_dir}\" \"${CAPTURED_STAGE}\"\n"
    )
    fake_uv.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "CAPTURED_STAGE": str(captured_stage),
    }

    subprocess.run(
        ["bash", "scripts/publish_code_dataset.sh", "create"],
        check=True,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert (captured_stage / "vendor" / WHEEL_NAME).is_file()
    assert (captured_stage / "vendor" / "iterative-stratification-LICENSE.txt").is_file()
