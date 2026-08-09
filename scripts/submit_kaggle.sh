#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <kernel-user/kernel-slug> <kernel-version> \"<submission message>\"" >&2
  exit 1
fi

KERNEL="$1"
VERSION="$2"
MESSAGE="$3"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

uv run --project "${REPO_ROOT}" python3 - "$KERNEL" "$VERSION" "$MESSAGE" <<'PYEOF'
import sys

import kaggle

kernel, version, message = sys.argv[1], int(sys.argv[2]), sys.argv[3]

api = kaggle.KaggleApi()
api.authenticate()
api.competition_submit_code(
    file_name="submission.csv",
    message=message,
    competition="rsna-knee-abnormality-detection",
    kernel=kernel,
    kernel_version=version,
)
print(f"Submitted {kernel} v{version}: {message}")
PYEOF
