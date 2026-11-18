@echo off
rem Double-click to start Chinese Screen OCR.
rem The first start opens a setup window that installs everything into this folder.
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0app\launcher.ps1"
