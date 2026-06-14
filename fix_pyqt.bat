@echo off
chcp 65001 >nul 2>&1
title PyQt5 Fix

echo Fixing PyQt5 for Python 3.12...
echo.

python -m pip uninstall pyqt5 pyqt5-qt5 pyqt5-sip -y
python -m pip install pyqt5 pyqt5-qt5 pyqt5-sip --force-reinstall

echo.
echo Testing...
python -c "from PyQt5.QtWidgets import QApplication; from PyQt5.QtCore import Qt; print('[OK] PyQt5 fixed!')"

if %errorlevel% neq 0 (
    echo [ERROR] Still not working.
    pause
    exit /b 1
)

echo.
echo PyQt5 OK! Now start the application with run.bat.
pause
