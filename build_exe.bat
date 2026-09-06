@echo off
chcp 65001 >nul
title Build Disk Cleaner Pro (exe)

:: PyInstaller single-file build
:: Requirements: pip install pyinstaller (plus runtime deps in requirements.txt)
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name DiskCleaner ^
  --icon app.ico ^
  --add-data "bg.jpg;." ^
  --add-data "app.ico;." ^
  --add-data "core\safety_rules.json;core" ^
  main.py

if errorlevel 1 (
    echo [ERROR] Build failed.
    exit /b 1
)

echo.
echo [OK] Build finished: dist\DiskCleaner.exe
