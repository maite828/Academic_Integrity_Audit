#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Academic Integrity Audit"
echo "========================"
echo ""
echo "Preparando la aplicacion local..."
echo "La primera vez puede tardar porque instala dependencias y comprueba Ollama."
echo ""

scripts/start_local.sh

echo ""
echo "Abriendo navegador en http://localhost:8501 ..."
open "http://localhost:8501"

echo ""
echo "Listo. La interfaz esta abierta en el navegador."
echo "Para apagarla despues, haz doble clic en Cerrar_Academic_Audit.command."
echo ""
read -r -p "Pulsa Enter para cerrar esta ventana. La app seguira abierta en segundo plano. "
