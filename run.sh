#!/usr/bin/env bash
# Starts the API and the web app together. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend packages (first run only)..."
  (cd frontend && npm install)
fi

cleanup() { echo; echo "Stopping..."; kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "API   -> http://127.0.0.1:8000/docs"
echo "App   -> http://localhost:5173"
echo

(cd backend && python3 -m uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev) &
wait
