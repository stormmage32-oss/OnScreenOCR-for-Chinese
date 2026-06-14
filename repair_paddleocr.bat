@echo off
chcp 65001 >nul 2>&1
setlocal
title Repair PaddleOCR
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
    set "OCR_PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
    set "OCR_PYTHON=python"
)

echo Repairing PaddleOCR/PaddlePaddle version mismatch...
"%OCR_PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not available.
    pause
    exit /b 1
)
"%OCR_PYTHON%" -c "import setuptools, wheel" >nul 2>&1
if errorlevel 1 (
    echo Installing missing packaging tools...
    "%OCR_PYTHON%" -m pip install setuptools wheel
    if errorlevel 1 (
        echo [ERROR] Could not install Python packaging tools.
        pause
        exit /b 1
    )
)

"%OCR_PYTHON%" -m pip install "paddlepaddle==2.6.2" "paddleocr>=2.7,<3.0"
if errorlevel 1 (
    echo [ERROR] Could not install compatible Paddle packages.
    pause
    exit /b 1
)

"%OCR_PYTHON%" -c "import paddle; from paddleocr import PaddleOCR; print('[OK]', paddle.__version__)"
if errorlevel 1 (
    echo [ERROR] PaddleOCR still fails after repair.
    pause
    exit /b 1
)

echo.
echo Repair complete. Run START.bat or run.bat again.
pause
