#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-llama3.1}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
OLLAMA_APP="/Applications/Ollama.app"
OLLAMA_APP_BIN="$OLLAMA_APP/Contents/Resources/ollama"

if [ -x "$OLLAMA_APP_BIN" ]; then
  OLLAMA_BIN="$OLLAMA_APP_BIN"
else
  OLLAMA_BIN="$(command -v ollama || true)"
fi

if [ -z "${OLLAMA_BIN:-}" ]; then
  if command -v brew >/dev/null 2>&1; then
    echo "Ollama no esta instalado. Instalando Ollama.app con Homebrew Cask..."
    brew install --cask ollama
    OLLAMA_BIN="$OLLAMA_APP_BIN"
  else
    echo "No se encontro Ollama ni Homebrew."
    echo "Instala Ollama desde https://ollama.com o instala Homebrew y reintenta."
    exit 1
  fi
fi

if ! curl -sS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  if [ -d "$OLLAMA_APP" ]; then
    echo "Arrancando Ollama.app..."
    open -a Ollama
  elif command -v brew >/dev/null 2>&1; then
    echo "Arrancando Ollama como servicio Homebrew..."
    brew services start ollama >/dev/null || true
  else
    echo "Arrancando Ollama en segundo plano..."
    nohup "$OLLAMA_BIN" serve > ollama_app.log 2>&1 &
    echo "$!" > .ollama_app.pid
  fi
fi

for _ in $(seq 1 30); do
  if curl -sS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -sS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  echo "Ollama no responde en $OLLAMA_URL."
  echo "Prueba manualmente: ollama serve"
  exit 1
fi

MODEL_ALIAS="$MODEL"
if [[ "$MODEL" != *":"* ]]; then
  MODEL_ALIAS="$MODEL:latest"
fi

if ! "$OLLAMA_BIN" list | awk -v model="$MODEL" -v alias="$MODEL_ALIAS" 'NR > 1 && ($1 == model || $1 == alias) { found=1 } END { exit found ? 0 : 1 }'; then
  echo "Descargando modelo local: $MODEL"
  "$OLLAMA_BIN" pull "$MODEL"
fi

echo "IA local lista."
echo "Ollama: $OLLAMA_URL"
echo "Modelo: $MODEL"
