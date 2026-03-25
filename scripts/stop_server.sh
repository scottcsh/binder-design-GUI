#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$PROJECT_DIR/.server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Server is not running."
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"

if [[ -z "${PID}" ]]; then
  rm -f "$PID_FILE"
  echo "Invalid PID file removed."
  exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  for _ in {1..20}; do
    if ! kill -0 "$PID" 2>/dev/null; then
      break
    fi
    sleep 0.5
  done

  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID"
  fi

  echo "Server stopped (PID: $PID)"
else
  echo "Process not running. Removing stale PID file."
fi

rm -f "$PID_FILE"
