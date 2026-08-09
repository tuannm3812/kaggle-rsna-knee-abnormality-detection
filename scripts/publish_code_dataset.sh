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

cp -R "${REPO_ROOT}/src/knee_mri" "${STAGE_DIR}/knee_mri"
cp "${REPO_ROOT}/pyproject.toml" "${STAGE_DIR}/pyproject.toml"
cp "${REPO_ROOT}/README.md" "${STAGE_DIR}/README.md"
cp "${REPO_ROOT}/LICENSE" "${STAGE_DIR}/LICENSE"
cp "${REPO_ROOT}/dataset-metadata.json" "${STAGE_DIR}/dataset-metadata.json"

find "${STAGE_DIR}/knee_mri" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# -r zip is required: the Kaggle CLI's default --dir-mode is "skip", which
# silently omits directories (including knee_mri/) from the upload.
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
