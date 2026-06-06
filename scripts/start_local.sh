#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .

mkdir -p runs

if [ "${ACADEMIC_AUDIT_SETUP_AI:-0}" = "1" ]; then
  scripts/setup_ai_local.sh "${ACADEMIC_AUDIT_MODEL:-llama3.1}"
fi

if [ -f ".streamlit.pid" ] && kill -0 "$(cat .streamlit.pid)" 2>/dev/null; then
  echo "Academic Integrity Audit ya esta arrancado en http://localhost:8501"
  exit 0
fi

nohup .venv/bin/streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --browser.gatherUsageStats false \
  > streamlit.log 2>&1 &

echo "$!" > .streamlit.pid
echo "Academic Integrity Audit arrancado: http://localhost:8501"
echo "Log: $(pwd)/streamlit.log"
