#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "Weronika AI - local agent (same-browser)"
echo "Checking Python..."
python3 --version
echo "Installing deps (quiet)..."
python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt || true
echo "Tip: For same-browser tab control, run Chrome with --remote-debugging-port=9222"
echo "Opening http://127.0.0.1:8765/ in 1.5s..."
(sleep 1.5 && python3 -m webbrowser http://127.0.0.1:8765/ 2>/dev/null || xdg-open http://127.0.0.1:8765/ 2>/dev/null || open http://127.0.0.1:8765/ 2>/dev/null || true) &
python3 weronika_agent.py
