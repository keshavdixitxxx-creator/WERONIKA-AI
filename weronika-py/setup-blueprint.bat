@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo Run start.bat once first so Weronika's local Python environment is created.
    echo Then run setup-blueprint.bat again.
    pause
    exit /b 1
)

echo.
echo === Optional local photo-to-3D setup ===
echo This installs CPU-only PyTorch, the TripoSR model code, and build dependencies.
echo It is a large download. The pretrained model weights are downloaded on first use.
echo CPU generation may take several minutes per image and requires a C++ build toolchain.
echo Photos are processed by the local worker and are not uploaded to Weronika's cloud brain.
echo.
set /p "ANSWER=Continue with setup? Type YES to continue: "
if /i not "%ANSWER%"=="YES" (
    echo Setup cancelled.
    pause
    exit /b 0
)

"%VENV_PY%" "%~dp0setup_blueprint.py"
if errorlevel 1 goto SETUP_FAILED

echo.
echo Local Blueprint model setup finished successfully.
echo Restart Weronika with start.bat, then choose GENERATE 3D MODEL in Blueprint.
pause
exit /b 0

:SETUP_FAILED
echo.
echo Blueprint setup failed. Check the error above.
echo If torchmcubes failed to compile, install Visual Studio Build Tools with the C++ workload, then rerun this file.
pause
exit /b 1
