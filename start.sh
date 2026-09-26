#!/usr/bin/env bash
# start.sh — launch the backend (FastAPI) and frontend (Vite) together
# Usage: ./start.sh
# Stop both with Ctrl+C

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV="$BACKEND_DIR/.venv"

# ── Colour helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[start]${NC} $*"; }
warn()  { echo -e "${YELLOW}[start]${NC} $*"; }
error() { echo -e "${RED}[start]${NC} $*" >&2; }

# ── Pre-flight checks ───────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
  error "Python venv not found at $VENV"
  error "Run: python3 -m venv backend/.venv && backend/.venv/bin/pip install -e 'backend[dev]'"
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  warn "node_modules not found — running npm install..."
  npm install --prefix "$FRONTEND_DIR" --silent
fi

# ── Cleanup on exit ─────────────────────────────────────────────────────────
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  info "Shutting down..."
  [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  info "Done."
}
trap cleanup EXIT INT TERM

# ── Start backend ────────────────────────────────────────────────────────────
info "Starting backend  → http://localhost:8000  (docs: http://localhost:8000/docs)"
PYTHONPATH="$BACKEND_DIR" \
  "$VENV/bin/uvicorn" app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir "$BACKEND_DIR/app" \
  --log-level info &
BACKEND_PID=$!

# ── Start frontend ───────────────────────────────────────────────────────────
info "Starting frontend → http://localhost:5173"
npm run dev --prefix "$FRONTEND_DIR" &
FRONTEND_PID=$!

# ── Wait ─────────────────────────────────────────────────────────────────────
info "Both services running. Press Ctrl+C to stop."
wait
