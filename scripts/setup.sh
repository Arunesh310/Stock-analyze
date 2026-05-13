#!/usr/bin/env bash
# BharatQuant — one-shot Linux/Mac setup
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> [1/3] Backend"
pushd backend > /dev/null
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
deactivate
popd > /dev/null

echo "==> [2/3] Frontend"
pushd frontend > /dev/null
npm install --legacy-peer-deps
[ -f .env.local ] || cp .env.local.example .env.local
popd > /dev/null

echo "==> [3/3] Ollama models"
if command -v ollama >/dev/null 2>&1; then
  ollama pull llama3 || true
  ollama pull nomic-embed-text || true
else
  echo "  Ollama not installed — get it from https://ollama.com/download"
fi

cat <<EOF

[ok] Setup complete.

Start the backend:
  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload

Start the frontend in another terminal:
  cd frontend && npm run dev
EOF
