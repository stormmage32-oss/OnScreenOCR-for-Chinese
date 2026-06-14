@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
title Chinese Screen OCR - Launcher

cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if (3,8) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo Existing .venv uses an unsupported Python version. Recreating it...
        rmdir /s /q "%~dp0.venv"
    ) else (
        set "OCR_PYTHON=%~dp0.venv\Scripts\python.exe"
    )
)

if not defined OCR_PYTHON (
    where py >nul 2>&1
    if not errorlevel 1 (
        for %%V in (3.12 3.11 3.10 3.9 3.8) do (
            if not defined OCR_PYTHON (
                py -%%V -c "import sys" >nul 2>&1
                if not errorlevel 1 set "OCR_PYTHON=py -%%V"
            )
        )
    )
)

if not defined OCR_PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if (3,8) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>&1
        if not errorlevel 1 set "OCR_PYTHON=python"
    )
)

if not defined OCR_PYTHON (
    where winget >nul 2>&1
    if not errorlevel 1 (
        echo.
        echo Python 3.8-3.12 was not found.
        echo Installing Python 3.11 with Windows Package Manager...
        winget install --id Python.Python.3.11 -e --source winget --accept-package-agreements --accept-source-agreements
        if errorlevel 1 (
            echo.
            echo [ERROR] Automatic Python installation failed.
            echo Install Python 3.11 manually from https://www.python.org/downloads/release/python-3119/
            echo Make sure "Add python.exe to PATH" is enabled, then run START.bat again.
            echo.
            pause
            exit /b 1
        )

        for %%V in (3.11 3.12 3.10 3.9 3.8) do (
            if not defined OCR_PYTHON (
                py -%%V -c "import sys" >nul 2>&1
                if not errorlevel 1 set "OCR_PYTHON=py -%%V"
            )
        )
    )
)

if not defined OCR_PYTHON (
    echo.
    echo [ERROR] Python 3.8-3.12 was not found.
    echo Install Python 3.11 from https://www.python.org/downloads/release/python-3119/
    echo Make sure "Add python.exe to PATH" is enabled, then run START.bat again.
    echo.
    pause
    exit /b 1
)

echo Using %OCR_PYTHON%
echo Checking local environment...
%OCR_PYTHON% -c "import PyQt5, paddle, paddleocr, mss, pypinyin, jieba, keyboard" >nul 2>&1
if errorlevel 1 (
    echo First time setup: installing required libraries into .venv...
    echo This may take several minutes.
    call "%~dp0install.bat"
    if errorlevel 1 (
        echo.
        echo [ERROR] Installation failed. See the messages above.
        pause
        exit /b 1
    )
)

echo Starting application...
call "%~dp0run.bat"
