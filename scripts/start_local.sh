#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if curl -fsS "http://127.0.0.1:8501" >/dev/null 2>&1; then
  echo "Academic Integrity Audit ya esta arrancado en http://localhost:8501"
  open "http://127.0.0.1:8501" 2>/dev/null || true
  exit 0
fi

if command -v osascript >/dev/null 2>&1; then
  osascript - "$PWD" <<'OSA'
on run argv
  set projectDir to item 1 of argv
  tell application "Terminal"
    do script "cd " & quoted form of projectDir & " && ./scripts/run_local.sh"
    activate
  end tell
end run
OSA

  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:8501" >/dev/null 2>&1; then
      open "http://127.0.0.1:8501" 2>/dev/null || true
      echo "Academic Integrity Audit arrancado: http://localhost:8501"
      exit 0
    fi
    sleep 1
  done

  echo "Se abrio una Terminal para arrancar la app."
  echo "Si el navegador no se abre solo, entra en http://127.0.0.1:8501"
  exit 0
fi

echo "Arrancando en primer plano. Deja esta terminal abierta."
exec ./scripts/run_local.sh
