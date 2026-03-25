#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$PROJECT_DIR/app"
WEB_PY="$APP_DIR/web.py"
PID_FILE="$PROJECT_DIR/.server.pid"
LOG_FILE="$PROJECT_DIR/gui.log"
VENV_ACTIVATE="$PROJECT_DIR/.venv/bin/activate"

if [[ ! -f "$WEB_PY" ]]; then
  echo "web.py not found: $WEB_PY"
  exit 1
fi

if [[ ! -f "$VENV_ACTIVATE" ]]; then
  echo ".venv not found: $VENV_ACTIVATE"
  exit 1
fi

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Server is already running (PID: $OLD_PID)"
    echo "Local access  : http://127.0.0.1:65022"
    exit 0
  else
    rm -f "$PID_FILE"
  fi
fi

cd "$PROJECT_DIR"
source "$VENV_ACTIVATE"

nohup python -m uvicorn app.web:app --host 0.0.0.0 --port 65022 > "$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

sleep 1

if kill -0 "$PID" 2>/dev/null; then
  LOCAL_IP="127.0.0.1"
  NETWORK_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -z "${NETWORK_IP}" ]]; then
    NETWORK_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -n1)"
  fi
  echo "================================================================"
  echo "Local access  : http://${LOCAL_IP}:65022"
  if [[ -n "${NETWORK_IP}" ]]; then
    echo "Network access: http://${NETWORK_IP}:65022"
  else
    echo "Network access: unavailable"
  fi
  echo "================================================================"
  echo "PID: $PID"
  echo "Log: $LOG_FILE"
else
  echo "Failed to start server."
  echo "Check log: $LOG_FILE"
  exit 1
fi
