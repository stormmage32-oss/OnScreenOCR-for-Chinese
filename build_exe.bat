@echo off
chcp 65001 >nul 2>&1
title Building Lightweight Launcher

echo ========================================================
echo    CHINESE SCREEN OCR - LIGHTWEIGHT EXE BUILDER
echo ========================================================
echo.

echo [1/2] Installing PyInstaller...
python -m pip install pyinstaller
echo.

echo [2/2] Building lightweight launcher...
echo This will be extremely fast and produce a very small file.
pyinstaller --noconfirm --onefile --windowed --name "ChineseScreenOCR" launcher.py

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Build failed. Please check the logs.
    pause
    exit /b 1
)

echo ========================================================
echo Build finished successfully!
echo.
copy dist\ChineseScreenOCR.exe .
echo.
echo The small "ChineseScreenOCR.exe" has been copied to your main folder.
echo You can now share this entire folder. When users click ChineseScreenOCR.exe,
echo it will download the heavy libraries directly onto their computers!
echo ========================================================
pause
