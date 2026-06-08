#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .

mkdir -p runs_form

if [ "${ACADEMIC_AUDIT_SETUP_AI:-0}" = "1" ]; then
  scripts/setup_ai_local.sh "${ACADEMIC_AUDIT_MODEL:-llama3.1}"
fi

(
  sleep 3
  open "http://127.0.0.1:8601"
) &

echo "Abriendo formulario simple en http://127.0.0.1:8601"
echo "Deja esta terminal abierta. Para apagar, pulsa Ctrl+C."

exec .venv/bin/python -m uvicorn academic_audit.simple_web:app \
  --host 127.0.0.1 \
  --port 8601
