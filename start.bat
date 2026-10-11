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

if exist "..\public\weronika.html" copy /y "..\public\weronika.html" "weronika.html" >nul
if exist "..\public\weronika-commands.js" copy /y "..\public\weronika-commands.js" "weronika-commands.js" >nul
if exist "..\public\technical-viewer.js" copy /y "..\public\technical-viewer.js" "technical-viewer.js" >nul
if exist "..\public\technical-models.js" copy /y "..\public\technical-models.js" "technical-models.js" >nul

start "" http://127.0.0.1:8765/
python weronika_agent.py
pause
