@echo off
title Weronika - local agent (same-browser)
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://python.org and tick "Add to PATH".
  pause
  exit /b 1
)
echo Weronika - same-browser mode (no separate chrome test)
echo To enable full tab control, run Chrome with --remote-debugging-port=9222
start "" http://127.0.0.1:8765/
python start.py
if errorlevel 1 python weronika_agent.py
pause
