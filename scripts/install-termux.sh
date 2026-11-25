#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v pkg >/dev/null 2>&1 || {
    echo "Run inside Android Termux"
    exit 1
}

pkg install -y python
python -m venv .venv
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -r requirements.txt
"$ROOT/.venv/bin/python" -m pip check

echo "Installed. Start manually with: ./scripts/run.sh"
