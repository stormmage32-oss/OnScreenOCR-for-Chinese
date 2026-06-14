@echo off
chcp 65001 >nul 2>&1
setlocal
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
    set "OCR_PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
    set "OCR_PYTHON=python"
)

"%OCR_PYTHON%" -c "import PyQt5" >nul 2>&1
if errorlevel 1 (
    echo Libraries missing! Run START.bat first.
    pause
    exit /b 1
)

"%OCR_PYTHON%" main.py
if errorlevel 1 (
    echo.
    echo Application closed with an error.
    pause
)
