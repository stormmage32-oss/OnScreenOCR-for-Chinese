@echo off
setlocal
chcp 65001 >nul 2>&1
title Build Chinese Screen OCR Installer
set "DOUBLE_CLICKED=1"

echo ========================================================
echo    CHINESE SCREEN OCR - BUNDLED INSTALLER BUILDER
echo ========================================================
echo.
echo This build bundles Python and the app dependencies with PyInstaller.
echo The user's Python installation is not used or changed.
echo.

echo [1/3] Creating isolated build environment...
if exist ".build-venv\Scripts\python.exe" (
    ".build-venv\Scripts\python.exe" --version >nul 2>&1
    if errorlevel 1 (
        echo Existing .build-venv is broken. Recreating it...
        rmdir /s /q ".build-venv"
    )
)

if not exist ".build-venv\Scripts\python.exe" (
    set "PYTHON_CMD=python"
    python --version >nul 2>&1
    if errorlevel 1 (
        set "PYTHON_CMD=py"
        py --version >nul 2>&1
        if errorlevel 1 (
            echo [ERROR] Python was not found on this build machine.
            echo Install Python 3.10 or 3.11, then run this script again.
            echo End users will not need Python installed.
            goto :error
        )
    )
)

if not exist ".build-venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .build-venv
    if errorlevel 1 goto :error
)

".build-venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error

".build-venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

echo.
echo [2/3] Building bundled application folder...
".build-venv\Scripts\pyinstaller.exe" --noconfirm --clean ChineseScreenOCR_full.spec
if errorlevel 1 goto :error

echo.
echo [3/3] Building Inno Setup installer...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo [ERROR] Inno Setup 6 was not found.
    echo Install it from https://jrsoftware.org/isinfo.php and run this script again.
    goto :error
)

"%ISCC%" installer\ChineseScreenOCR.iss
if errorlevel 1 goto :error

echo.
echo ========================================================
echo Installer created:
echo installer_output\ChineseScreenOCR-Setup.exe
echo ========================================================
echo.
if not "%CODEX_NO_PAUSE%"=="1" pause
exit /b 0

:error
echo.
echo [ERROR] Build failed.
echo.
echo The window will stay open so you can read the error above.
if not "%CODEX_NO_PAUSE%"=="1" pause
exit /b 1
