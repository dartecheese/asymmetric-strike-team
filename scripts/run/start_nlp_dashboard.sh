#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"
echo "Starting NLP dashboard on http://127.0.0.1:5055"
if [ -x venv/bin/python ]; then
  exec venv/bin/python nlp_dashboard.py
else
  exec python3 nlp_dashboard.py
fi
