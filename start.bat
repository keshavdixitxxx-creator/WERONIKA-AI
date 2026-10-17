@echo off
title Weronika - local agent
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://python.org and tick "Add to PATH".
  pause
  exit /b 1
)

echo Installing what Weronika needs (first run only)...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Python packages could not be installed. Check the console and try again.
  pause
  exit /b 1
)
python -m playwright install chromium
if errorlevel 1 (
  echo Chromium could not be installed. Browser app automation will stay unavailable until this succeeds.
  pause
  exit /b 1
)
echo Private email, DM, and calendar summaries require Ollama running locally (default model: llama3.2).

rem The local agent serves the UI and its static modules directly from public\.
start "" http://127.0.0.1:8765/
python weronika_agent.py
pause
