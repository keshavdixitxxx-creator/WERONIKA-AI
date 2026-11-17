@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo Run start.bat once first so Weronika's local Python environment is created.
    echo Then run setup-calls.bat again.
    pause
    exit /b 1
)

echo.
echo === Optional call audio setup ===
echo This installs the speech engine Weronika needs to HEAR a caller and her voice to ANSWER:
echo   sounddevice     - hears through the microphone, a Bluetooth pairing, or line-in
echo   faster-whisper  - accurate transcription (best on Hinglish and Indian English)
echo   vosk            - a light fallback engine, plus a small offline model
echo   pyttsx3         - Weronika's spoken voice
echo It is a sizeable download, and the first call may take a moment while the model loads.
echo.
echo Privacy: call audio is processed by this local worker only. It is never uploaded, and it
echo is never written to disk - one utterance lives in memory just long enough to become words.
echo.
echo Without this, Weronika still answers calls in typed mode and says so out loud.
echo.
set /p "ANSWER=Continue with setup? Type YES to continue: "
if /i not "%ANSWER%"=="YES" (
    echo Setup cancelled. Weronika stays in typed mode for calls.
    pause
    exit /b 0
)

"%VENV_PY%" "%~dp0setup_calls.py" %*
if errorlevel 1 goto SETUP_FAILED

echo.
echo Call audio setup finished.
echo Restart Weronika with start.bat, then say "handle my calls" in the orb.
echo.
echo For a phone (SIM) call you still need:
echo   1. USB debugging switched on, and the phone connected with a cable.
echo   2. Android platform-tools installed, or WERONIKA_ADB pointing at adb.exe.
echo   3. The phone on speaker, or paired to this computer as a hands-free headset.
echo For a WhatsApp call: open WhatsApp in Weronika's browser and sign in.
pause
exit /b 0

:SETUP_FAILED
echo.
echo Call audio setup failed. Check the error above.
echo If a package failed to compile, install Visual Studio Build Tools with the C++ workload
echo and rerun this file, or try a lighter install:
echo     setup-calls.bat --engines vosk
echo Weronika keeps working in typed mode either way.
pause
exit /b 1
