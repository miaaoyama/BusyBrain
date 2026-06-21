#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -x .venv/bin/python ]]; then
  echo "Busy Brain virtual environment not found. Run the setup steps in README.md first."
  exit 1
fi

for port in 8000 8001 8002 8003 8004 8080; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop the existing Busy Brain terminals, then run this again."
    exit 1
  fi
done

LOG_DIR="$ROOT_DIR/.busy-brain-logs"
mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR"/*.log

pids=()

start_service() {
  local name="$1"
  shift
  "$@" >"$LOG_DIR/$name.log" 2>&1 &
  pids+=("$!")
  echo "  ✓ $name"
}

cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Stopping Busy Brain…"
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}

trap cleanup INT TERM EXIT

echo "Starting Busy Brain services…"
start_service api .venv/bin/uvicorn api:app --reload --host 127.0.0.1 --port 8000
start_service website .venv/bin/python -m http.server 8080 --bind 127.0.0.1
start_service orchestrator .venv/bin/python agent.py
start_service study-agent .venv/bin/python study_agent.py
start_service calendar-agent .venv/bin/python calendar_agent.py
start_service workload-agent .venv/bin/python wellness_agent.py

sleep 2
for pid in "${pids[@]}"; do
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "A service failed to start. Check $LOG_DIR for details."
    exit 1
  fi
done

echo
echo "Busy Brain is ready: http://localhost:8080"
echo "Logs: $LOG_DIR"
echo "Press Ctrl+C once to stop everything."
echo

wait
