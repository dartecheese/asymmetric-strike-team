#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "Starting NLP dashboard on http://127.0.0.1:5055"
python3 nlp_dashboard.py
