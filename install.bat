@echo off
chcp 65001 >nul 2>&1
title OCR Installation

echo.
echo  ================================================
echo    CHINESE SCREEN OCR - INSTALLATION
echo  ================================================
echo.

python --version
echo.

echo [1/4] updating pip...
python -m pip install --upgrade pip
echo.

echo [2/4] Basic libraries...
python -m pip install "pyqt5>=5.15" "mss>=9.0" "pillow>=10.0" "numpy>=1.24" "pypinyin>=0.49" "jieba>=0.42" "keyboard>=0.13.5"
if %errorlevel% neq 0 (
    echo [ERROR] Basic libraries failed to install!
    pause
    exit /b 1
)
echo.

echo [3/4] PaddlePaddle (Stable version: 2.6.2)...
python -m pip install "paddlepaddle==2.6.2"
if %errorlevel% neq 0 (
    echo [ERROR] PaddlePaddle failed to install!
    pause
    exit /b 1
)
echo.

echo [4/4] PaddleOCR...
python -m pip install "paddleocr>=2.7"
if %errorlevel% neq 0 (
    echo [ERROR] PaddleOCR failed to install!
    pause
    exit /b 1
)
echo.

echo Testing OCR...
python -c "import paddle; print('[OK] PaddlePaddle is working')" 2>&1
python -c "from paddleocr import PaddleOCR; print('[OK] PaddleOCR is working')" 2>&1
echo.

echo  ================================================
echo    INSTALLATION OK! To start: run.bat
echo    Models will be downloaded on first start (1-3 min)
echo  ================================================
echo.
pause
