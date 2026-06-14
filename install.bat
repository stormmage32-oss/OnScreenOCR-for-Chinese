@echo off
chcp 65001 >nul 2>&1
title OCR Installation

echo.
echo  ================================================
echo    CHINESE SCREEN OCR - INSTALLATION (ISOLATED)
echo  ================================================
echo.

if not exist "uv.exe" (
    echo [0/4] Downloading environment manager (uv)...
    powershell -Command "Invoke-WebRequest -Uri https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip -OutFile uv.zip; Expand-Archive uv.zip -DestinationPath . -Force; Move-Item -Path uv-x86_64-pc-windows-msvc\uv.exe -Destination . -Force; Remove-Item uv-x86_64-pc-windows-msvc -Recurse -Force; Remove-Item uv.zip -Force"
)

echo [1/4] Creating isolated Python 3.11 environment...
echo (Sisteminizdeki Python surumune dokunulmaz, gerekirse 3.11 sadece bu klasore indirilir)
uv venv --python 3.11 .venv
if %errorlevel% neq 0 (
    echo [ERROR] Virtual environment creation failed!
    pause
    exit /b 1
)
echo.

echo [2/4] Basic libraries...
uv pip install --python .venv "pyqt5>=5.15" "mss>=9.0" "pillow>=10.0" "numpy>=1.24,<2.0" "pypinyin>=0.49" "jieba>=0.42" "keyboard>=0.13.5"
if %errorlevel% neq 0 (
    echo [ERROR] Basic libraries failed to install!
    pause
    exit /b 1
)
echo.

echo [3/4] PaddlePaddle (Stable version: 2.6.2)...
uv pip install --python .venv "paddlepaddle==2.6.2"
if %errorlevel% neq 0 (
    echo [ERROR] PaddlePaddle failed to install!
    pause
    exit /b 1
)
echo.

echo [4/4] PaddleOCR...
uv pip install --python .venv "paddleocr>=2.7"
if %errorlevel% neq 0 (
    echo [ERROR] PaddleOCR failed to install!
    pause
    exit /b 1
)
echo.

echo Testing OCR...
.venv\Scripts\python.exe -c "import paddle; print('[OK] PaddlePaddle is working')" 2>&1
.venv\Scripts\python.exe -c "from paddleocr import PaddleOCR; print('[OK] PaddleOCR is working')" 2>&1
echo.

echo  ================================================
echo    INSTALLATION OK! To start: run.bat
echo    Models will be downloaded on first start (1-3 min)
echo  ================================================
echo.
pause
