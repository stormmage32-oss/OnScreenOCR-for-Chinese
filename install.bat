@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
title OCR Installation
cd /d "%~dp0"

echo.
echo  ================================================
echo    CHINESE SCREEN OCR - INSTALLATION
echo  ================================================
echo.

if not defined OCR_PYTHON (
    if exist "%~dp0.venv\Scripts\python.exe" (
        "%~dp0.venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if (3,8) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>&1
        if errorlevel 1 (
            echo Existing .venv uses an unsupported Python version. Recreating it...
            rmdir /s /q "%~dp0.venv"
        ) else (
            set "OCR_PYTHON=%~dp0.venv\Scripts\python.exe"
        )
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
        echo Python 3.8-3.12 was not found.
        echo Installing Python 3.11 with Windows Package Manager...
        winget install --id Python.Python.3.11 -e --source winget --accept-package-agreements --accept-source-agreements
        if errorlevel 1 (
            echo [ERROR] Automatic Python installation failed.
            echo Install Python 3.11 manually and enable "Add python.exe to PATH".
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
    echo [ERROR] Python 3.8-3.12 was not found.
    echo Install Python 3.11 and enable "Add python.exe to PATH".
    pause
    exit /b 1
)

echo Using Python:
%OCR_PYTHON% --version
if errorlevel 1 (
    echo [ERROR] Python could not be started.
    pause
    exit /b 1
)
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Creating local virtual environment...
    %OCR_PYTHON% -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo [ERROR] Could not create .venv. Reinstall Python with the "venv" feature enabled.
        pause
        exit /b 1
    )
)

set "OCR_PYTHON=%~dp0.venv\Scripts\python.exe"

echo [1/4] Checking Python packaging tools...
"%OCR_PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not available in the virtual environment.
    pause
    exit /b 1
)
"%OCR_PYTHON%" -c "import setuptools, wheel" >nul 2>&1
if errorlevel 1 (
    echo Installing missing packaging tools...
    "%OCR_PYTHON%" -m pip install setuptools wheel
    if errorlevel 1 (
        echo [ERROR] Python packaging tools install failed!
        pause
        exit /b 1
    )
)
echo.

echo [2/4] Basic libraries...
"%OCR_PYTHON%" -m pip install "pyqt5>=5.15" "mss>=9.0" "pillow>=10.0" "numpy>=1.24,<2.0" "pypinyin>=0.49" "jieba>=0.42" "keyboard>=0.13.5"
if errorlevel 1 (
    echo [ERROR] Basic libraries failed to install!
    pause
    exit /b 1
)
echo.

echo [3/4] PaddlePaddle (Stable version: 2.6.2)...
"%OCR_PYTHON%" -m pip install "paddlepaddle==2.6.2"
if errorlevel 1 (
    echo [ERROR] PaddlePaddle failed to install!
    pause
    exit /b 1
)
echo.

echo [4/4] PaddleOCR...
"%OCR_PYTHON%" -m pip install "paddleocr>=2.7,<3.0"
if errorlevel 1 (
    echo [ERROR] PaddleOCR failed to install!
    pause
    exit /b 1
)
echo.

echo Testing OCR...
"%OCR_PYTHON%" -c "import paddle; print('[OK] PaddlePaddle is working')" 2>&1
if errorlevel 1 (
    echo [ERROR] PaddlePaddle test failed!
    pause
    exit /b 1
)
"%OCR_PYTHON%" -c "from paddleocr import PaddleOCR; print('[OK] PaddleOCR is working')" 2>&1
if errorlevel 1 (
    echo [ERROR] PaddleOCR test failed!
    pause
    exit /b 1
)
echo.

echo  ================================================
echo    INSTALLATION OK! To start: run.bat
echo    Models will be downloaded on first start (1-3 min)
echo  ================================================
echo.
pause
