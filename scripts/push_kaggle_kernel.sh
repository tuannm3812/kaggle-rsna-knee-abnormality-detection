#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <kernel-name>" >&2
  echo "  e.g. $0 eda" >&2
  exit 1
fi

KERNEL_NAME="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KERNEL_DIR="${REPO_ROOT}/notebooks/kernels/${KERNEL_NAME}"

if [[ ! -f "${KERNEL_DIR}/kernel-metadata.json" ]]; then
  echo "No kernel-metadata.json at ${KERNEL_DIR} — create it first." >&2
  exit 1
fi

NOTEBOOK_FILE=$(python3 -c "
import json
with open('${KERNEL_DIR}/kernel-metadata.json') as f:
    print(json.load(f)['code_file'])
")

SOURCE_NOTEBOOK="${REPO_ROOT}/notebooks/${NOTEBOOK_FILE}"
if [[ ! -f "${SOURCE_NOTEBOOK}" ]]; then
  echo "Source notebook not found: ${SOURCE_NOTEBOOK}" >&2
  exit 1
fi

cp "${SOURCE_NOTEBOOK}" "${KERNEL_DIR}/${NOTEBOOK_FILE}"
echo "Copied ${SOURCE_NOTEBOOK} -> ${KERNEL_DIR}/${NOTEBOOK_FILE}"

cd "${KERNEL_DIR}"
uv run --project "${REPO_ROOT}" kaggle kernels push -p .
echo "Pushed kernel ${KERNEL_NAME}."
