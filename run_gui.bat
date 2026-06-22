@echo off
setlocal
pushd %~dp0

:: Check if local .venv exists
if not exist .venv (
    echo [ERROR] Virtual environment (.venv) not found.
    echo Please run setup_venv.bat first to set up the environment.
    echo.
    pause
    exit /b 1
)

echo Starting MoA Actuator GUI...
.venv\Scripts\python.exe -m moa_actuator gui

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] GUI execution failed.
    pause
)

popd
endlocal
