@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"

python -c "import PyQt5" >nul 2>&1
if %errorlevel% neq 0 (
    echo Libraries missing! Run install.bat first.
    pause
    exit /b 1
)

python main.py
if %errorlevel% neq 0 (
    echo.
    echo Application closed with an error.
    pause
)
