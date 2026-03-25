#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$PROJECT_DIR/.server.pid"
LOG_FILE="$PROJECT_DIR/gui.log"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Server status: stopped"
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"

if [[ -n "${PID}" ]] && kill -0 "$PID" 2>/dev/null; then
  LOCAL_IP="127.0.0.1"
  NETWORK_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -z "${NETWORK_IP}" ]]; then
    NETWORK_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -n1)"
  fi

  echo "Server status: running"
  echo "PID: $PID"
  echo "Local access  : http://${LOCAL_IP}:65022"
  if [[ -n "${NETWORK_IP}" ]]; then
    echo "Network access: http://${NETWORK_IP}:65022"
  else
    echo "Network access: unavailable"
  fi
  echo "Log: $LOG_FILE"
else
  echo "Server status: stopped (stale PID file)"
  rm -f "$PID_FILE"
fi
