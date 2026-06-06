#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

stopped=0

for port in 8501 8601; do
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    kill $pids
    echo "Proceso detenido en puerto $port."
    stopped=1
  fi
done

rm -f .streamlit.pid

if [ "$stopped" = "0" ]; then
  echo "No habia app local escuchando en 8501 ni 8601."
else
  echo "Academic Integrity Audit detenido."
fi
