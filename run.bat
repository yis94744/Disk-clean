@echo off
chcp 65001 >nul
title Disk Cleaner Pro

echo ================================
echo   Disk Cleaner Pro v1.0.0
echo ================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.9+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check/Create venv
if not exist "venv\" (
    echo [*] Creating virtual environment...
    python -m venv venv
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install/Update dependencies
echo [*] Checking dependencies...
pip install -q --upgrade pip
pip install -q PySide6 psutil

:: Launch
echo [*] Launching Disk Cleaner Pro...
echo.
python main.py

:: Keep window open if crash
if errorlevel 1 (
    echo.
    echo [ERROR] Application crashed. Check the error above.
    pause
)
