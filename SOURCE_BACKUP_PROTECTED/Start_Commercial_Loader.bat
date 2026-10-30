@echo off
title AURA Tactical Vision // Commercial Client Loader
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY_CMD%"=="" where py >nul 2>nul && set "PY_CMD=py"
if "%PY_CMD%"=="" where python >nul 2>nul && set "PY_CMD=python"

if "%PY_CMD%"=="" (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

start "" %PY_CMD% commercial_loader.py
exit /b 0
