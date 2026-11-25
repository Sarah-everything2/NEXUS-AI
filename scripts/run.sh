#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    echo "Run the platform installer first."
    exit 1
fi

exec "$ROOT/.venv/bin/python" -m core.cli "$@"
