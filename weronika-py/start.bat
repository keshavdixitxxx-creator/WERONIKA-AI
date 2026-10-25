@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "SETUP_MARKER=%VENV_DIR%\.weronika_setup_complete"

if exist "%SETUP_MARKER%" if exist "%VENV_PY%" goto RUN_APP

echo.
echo === First-time Weronika setup ===
set "PYTHON_CMD=python"
python --version >nul 2>&1
if errorlevel 1 (
    py -3 --version >nul 2>&1
    if errorlevel 1 goto NO_PYTHON
    set "PYTHON_CMD=py -3"
)

%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto OLD_PYTHON

if not exist "%VENV_PY%" (
    echo Creating isolated Python environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 goto SETUP_FAILED
)

echo Installing Python requirements...
call "%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto SETUP_FAILED
call "%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto SETUP_FAILED

echo Installing the Playwright Chromium browser...
call "%VENV_PY%" -m playwright install chromium
if errorlevel 1 goto SETUP_FAILED

>"%SETUP_MARKER%" echo setup complete
if errorlevel 1 goto SETUP_FAILED

echo First-time setup complete.

:RUN_APP
echo.
echo Starting Weronika local messaging and opening its web page...
echo The page is available at http://127.0.0.1:8765/
echo Keep this window open while Weronika is running. Press Ctrl+C to stop.
echo.
call "%VENV_PY%" "%~dp0start.py" --open-browser
if errorlevel 1 goto APP_FAILED
goto END

:NO_PYTHON
echo ERROR: Python 3.10 or newer was not found.
echo Install Python from https://www.python.org/downloads/ and enable "Add Python to PATH", then run this file again.
goto PAUSE_END

:OLD_PYTHON
echo ERROR: Weronika needs Python 3.10 or newer. Install a current Python version and run this file again.
goto PAUSE_END

:SETUP_FAILED
echo.
echo ERROR: Setup did not finish. Check your internet connection and try start.bat again.
echo Setup will retry on the next run because the completion marker was not created.
goto PAUSE_END

:APP_FAILED
echo.
echo Weronika stopped with an error. Check the messages above, then run start.bat again.
goto PAUSE_END

:PAUSE_END
echo.
pause

:END
endlocal
