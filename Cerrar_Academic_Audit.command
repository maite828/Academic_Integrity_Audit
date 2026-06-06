#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

scripts/stop_local.sh

echo ""
echo "Academic Integrity Audit apagado."
read -r -p "Pulsa Enter para cerrar esta ventana. "
