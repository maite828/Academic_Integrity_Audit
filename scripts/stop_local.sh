#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f ".streamlit.pid" ]; then
  echo "No hay PID local. Si Streamlit sigue abierto, cierralo desde la terminal donde lo arrancaste."
  exit 0
fi

pid="$(cat .streamlit.pid)"
if kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  echo "Academic Integrity Audit detenido."
else
  echo "El proceso ya no estaba activo."
fi

rm -f .streamlit.pid

