@echo off
chcp 65001 >nul 2>&1
title Chinese Screen OCR - Launcher

cd /d "%~dp0"

echo Checking dependencies...
python -c "import PyQt5, paddle, paddleocr, mss, pypinyin, jieba, keyboard" >nul 2>&1
if %errorlevel% neq 0 (
    echo First time setup: Installing required libraries...
    echo This might take a few minutes.
    call install.bat
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Installation failed! Please check the errors above.
        pause
        exit /b 1
    )
)

echo Starting application...
call run.bat
