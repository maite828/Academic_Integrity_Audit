#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .

mkdir -p runs

echo "Abriendo Academic Integrity Audit en http://localhost:8501"
echo "Para apagarlo, pulsa Ctrl+C en esta terminal."

.venv/bin/streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --browser.gatherUsageStats false

