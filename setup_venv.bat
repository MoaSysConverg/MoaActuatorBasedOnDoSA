@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo  MoA Actuator - Local Virtual Environment Setup
echo ===================================================
echo.

:: 1. Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10 or higher from python.org and add it to PATH.
    pause
    exit /b 1
)

:: Get Python version
for /f "tokens=2 delims= " %%I in ('python --version 2^>^&1') do set pyver=%%I
echo Found Python version: !pyver!

:: 2. Create local .venv
echo.
echo [1/3] Creating virtual environment (.venv) in this directory...
if exist .venv (
    echo .venv directory already exists. Skipping creation...
) else (
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b !errorlevel!
    )
)

:: 3. Upgrade pip
echo.
echo [2/3] Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip
if !errorlevel! neq 0 (
    echo [WARNING] Failed to upgrade pip. Continuing...
)

:: 4. Install package and dependencies
echo.
echo [3/3] Installing moa-actuator with all dependencies...
.venv\Scripts\python.exe -m pip install -e .[all]
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Installation failed. Please check the errors above.
    pause
    exit /b !errorlevel!
)

echo.
echo ===================================================
echo  Setup Completed Successfully!
echo ===================================================
echo.
echo  * You can now run the GUI using: run_gui.bat
echo  * To run Jupyter Notebook:
echo      1. Activate venv: .venv\Scripts\activate.bat
echo      2. Run: jupyter notebook
echo.
pause
