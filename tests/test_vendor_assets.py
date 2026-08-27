from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

WHEEL_NAME = "iterative_stratification-0.1.9-py3-none-any.whl"
WHEEL_SHA256 = "476f8deff6753fb1725612fe41e59cc2058f8f2524ae5d1ccee88eb8c8d3de80"

PROCESSOR_NAME = "dinov2-small-preprocessor_config.json"
PROCESSOR_SHA256 = "14e780d86fa1861f8751f868d7f45425b5feb55c38ca26f152ca5097ab30f828"

# Kaggle runs CPython 3.12 (observed in kernel logs); a wheel built for any
# other interpreter version will not load there, so the tags are pinned too.
CODEC_WHEELS = {
    "pylibjpeg-2.1.0-py3-none-any.whl":
        "25df9496a69e64e98c887fddee12a1271e275b5f74ba804f9bf98a08bb80993e",
    "pylibjpeg_openjpeg-2.5.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl":
        "a22fcb649ba9849209d8e43dba88632445a5941f0cd6765338b3652a4c686140",
    "pylibjpeg_libjpeg-2.4.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl":
        "01d950ef496476a9223e4966376cb88098fcf5c55a12a21f722d7b5f84daae43",
}


def test_vendored_iterative_stratification_wheel_is_exact_release() -> None:
    wheel = Path("vendor") / WHEEL_NAME

    assert wheel.stat().st_size == 8_515
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == WHEEL_SHA256


def test_vendored_iterative_stratification_license_is_bsd_3_clause() -> None:
    license_text = Path("vendor/iterative-stratification-LICENSE.txt").read_text()

    assert "BSD 3-Clause License" in license_text
    assert "Redistribution and use in source and binary forms" in license_text
    assert "THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS" in license_text


def test_vendored_dinov2_processor_config_is_the_exact_mounted_artifact() -> None:
    """Spec section 6 standardizes with the attached model's own image_mean /
    image_std, and its required equivalence test cannot run locally without
    them (the Kaggle Model mount is not present off-Kaggle). Pin the exact
    bytes so a silent substitution -- remembered ImageNet constants above all
    -- cannot pass unnoticed.
    """
    config_path = Path("vendor") / PROCESSOR_NAME

    assert hashlib.sha256(config_path.read_bytes()).hexdigest() == PROCESSOR_SHA256

    config = json.loads(config_path.read_text())
    for key in ("image_mean", "image_std"):
        values = config[key]
        assert isinstance(values, list)
        assert len(values) == 3
        assert all(isinstance(v, (int, float)) and 0.0 < v < 1.0 for v in values)

    # Section 6 says to disable resize and rescale for the equivalence test.
    # The real config ALSO enables centre-cropping to 224, which would crop
    # the 336x336 letterboxed input and compare a different image, so the
    # test must disable that too (round 86).
    assert config["do_center_crop"] is True
    assert config["crop_size"] == {"height": 224, "width": 224}


def test_vendored_dinov2_license_records_the_pinned_artifacts_terms() -> None:
    """The pinned Kaggle Model version declares cc-by-nc-4.0, not the
    Apache-2.0 this project recorded in rounds 37-38. Pin the corrected
    record so it cannot silently revert.
    """
    license_text = Path("vendor/dinov2-small-LICENSE.txt").read_text()

    assert "cc-by-nc-4.0" in license_text
    assert "metaresearch/dinov2" in license_text
    assert PROCESSOR_SHA256 in license_text
    assert "No model weights are redistributed" in license_text


@pytest.mark.parametrize(("wheel_name", "expected_sha256"), sorted(CODEC_WHEELS.items()))
def test_vendored_codec_wheels_are_the_exact_pinned_builds(
    wheel_name: str, expected_sha256: str
) -> None:
    wheel = Path("vendor") / wheel_name

    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == expected_sha256


def test_vendored_codec_wheels_target_the_kaggle_interpreter() -> None:
    """A cp311 or macOS build would install cleanly here and fail on Kaggle."""
    compiled = [name for name in CODEC_WHEELS if "py3-none-any" not in name]

    assert compiled, "expected at least one compiled codec wheel"
    for name in compiled:
        assert "cp312" in name
        assert "manylinux" in name and "x86_64" in name


def test_codec_licence_note_records_the_gpl_component() -> None:
    """The GPL split is the whole reason this was a decision rather than a
    formality, so it must stay visible in the vendored record.
    """
    note = Path("vendor/pylibjpeg-LICENSE.txt").read_text()

    assert "GPL v3.0" in note
    assert "pylibjpeg_libjpeg-2.4.0" in note
    assert "--no-deps" in note
    for expected_sha256 in CODEC_WHEELS.values():
        assert expected_sha256 in note


def test_gpl_licence_text_travels_with_the_binary() -> None:
    """GPLv3 requires conveying a copy of the licence with the work.

    Extracted verbatim from the wheel's own dist-info rather than fetched,
    so it is provably the terms that shipped with this exact build.
    """
    text = Path("vendor/pylibjpeg-libjpeg-LICENSE.txt").read_text()

    assert "GNU GENERAL PUBLIC LICENSE" in text
    assert "Version 3, 29 June 2007" in text
    assert "pylibjpeg-libjpeg" in text
    # The wrapped library carries its own attribution and must not be lost.
    assert "libjpeg" in text
    assert len(text) > 30_000


def test_gpl_compliance_note_carries_a_written_offer_and_source_location() -> None:
    """This repository is public, so redistribution obligations are live.

    An earlier draft reasoned from private use and was wrong; these
    assertions exist so that reasoning cannot quietly return.
    """
    note = Path("vendor/pylibjpeg-LICENSE.txt").read_text()

    assert "written offer" in note.lower()
    assert "three years" in note.lower()
    assert "github.com/scaramallion/pylibjpeg-libjpeg" in note
    assert "mere aggregation" in note.lower()
    assert "this repository is public" in note.lower()


def test_root_licence_scopes_itself_to_first_party_code() -> None:
    """The MIT file must not read as covering the vendored artifacts."""
    licence = Path("LICENSE").read_text()

    assert "MIT License" in licence
    assert "Third-party components" in licence
    assert "GNU GPL v3.0" in licence
    assert "CC BY-NC 4.0" in licence


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
    assert (captured_stage / "vendor" / PROCESSOR_NAME).is_file()
    assert (captured_stage / "vendor" / "dinov2-small-LICENSE.txt").is_file()
    assert (captured_stage / "vendor" / "pylibjpeg-LICENSE.txt").is_file()
    assert (captured_stage / "vendor" / "pylibjpeg-libjpeg-LICENSE.txt").is_file()
    for wheel_name in CODEC_WHEELS:
        assert (captured_stage / "vendor" / wheel_name).is_file()
