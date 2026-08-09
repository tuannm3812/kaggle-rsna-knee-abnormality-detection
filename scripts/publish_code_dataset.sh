#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <create|version> [\"version message\"]" >&2
  exit 1
fi

ACTION="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGE_DIR}"' EXIT

cp -R "${REPO_ROOT}/src" "${STAGE_DIR}/src"
cp "${REPO_ROOT}/pyproject.toml" "${STAGE_DIR}/pyproject.toml"
cp "${REPO_ROOT}/README.md" "${STAGE_DIR}/README.md"
cp "${REPO_ROOT}/LICENSE" "${STAGE_DIR}/LICENSE"
cp "${REPO_ROOT}/dataset-metadata.json" "${STAGE_DIR}/dataset-metadata.json"

find "${STAGE_DIR}/src" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# -r zip is required: the Kaggle CLI's default --dir-mode is "skip", which
# silently omits directories (including src/) from the upload. Staging the
# whole src/ directory (rather than flattening to knee_mri/ directly) keeps
# the zip's single top-level entry as knee_mri/ either way Kaggle's server
# extracts it (wrapped in a folder named after the zip, or not) -- flattening
# would make shutil.make_archive's contents-only zipping upload knee_mri's
# individual files with no enclosing directory at all, an untested and
# strictly worse bet.
case "${ACTION}" in
  create)
    uv run --project "${REPO_ROOT}" kaggle datasets create -p "${STAGE_DIR}" -r zip
    ;;
  version)
    MESSAGE="${2:-Update src/knee_mri}"
    uv run --project "${REPO_ROOT}" kaggle datasets version -p "${STAGE_DIR}" -r zip -d -m "${MESSAGE}"
    ;;
  *)
    echo "Unknown action: ${ACTION} (expected create|version)" >&2
    exit 1
    ;;
esac
