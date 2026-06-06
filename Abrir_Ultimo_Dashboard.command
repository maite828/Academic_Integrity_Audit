#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

DASHBOARD="$(find . -maxdepth 3 -name dashboard.html -type f -print0 | xargs -0 ls -t 2>/dev/null | head -n 1 || true)"

if [ -z "$DASHBOARD" ]; then
  echo "No se encontro ningun dashboard.html generado."
  echo "Primero abre Abrir_Academic_Audit.command y ejecuta una auditoria."
  echo ""
  read -r -p "Pulsa Enter para cerrar esta ventana. "
  exit 1
fi

echo "Abriendo dashboard:"
echo "$DASHBOARD"
open "$DASHBOARD"
