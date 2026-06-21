#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

if ! command -v python >/dev/null 2>&1; then
  echo "Python command 'python' was not found. Install Python 3.10+ and run: python -m pip install -r requirements-demo.txt" >&2
  exit 1
fi

cd "$repo_root"
if ! python -c "import streamlit" >/dev/null 2>&1; then
  echo "Streamlit is not installed. Run: python -m pip install -r requirements-demo.txt" >&2
  exit 1
fi

python -m streamlit run demo/app.py

