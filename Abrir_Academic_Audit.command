#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Academic Integrity Audit"
echo "========================"
echo ""
echo "Preparando la aplicacion local..."
echo "La primera vez puede tardar porque instala dependencias y comprueba Ollama."
echo ""

(
  sleep 8
  open "http://127.0.0.1:8501"
) &

echo "Cuando aparezca la URL, deja esta ventana abierta."
echo "Para apagar la app, vuelve a esta ventana y pulsa Ctrl+C."
echo ""

scripts/run_local.sh
