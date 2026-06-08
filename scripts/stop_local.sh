#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

stopped=0

pids="$(lsof -tiTCP:8601 -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$pids" ]; then
  kill $pids
  echo "Proceso detenido en puerto 8601."
  stopped=1
fi

if [ "$stopped" = "0" ]; then
  echo "No habia app local escuchando en 8601."
else
  echo "Academic Integrity Audit detenido."
fi
