#!/bin/bash
pkill -f "uvicorn app.web:app" 2>/dev/null
cd /home/cs/SH/binder_llm
source .venv/bin/activate
uvicorn app.web:app --host 0.0.0.0 --port 65022 < /dev/null &
