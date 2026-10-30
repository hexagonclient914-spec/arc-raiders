@echo off
title Live FPS & Latency Monitor
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "PY_CMD="
where py >nul 2>nul
if %errorlevel% equ 0 set "PY_CMD=py"
if "%PY_CMD%"=="" where python >nul 2>nul && set "PY_CMD=python"
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY_CMD%"=="" if exist "C:\Program Files\Python311\python.exe" set "PY_CMD=C:\Program Files\Python311\python.exe"

if "%PY_CMD%"=="" (
    echo [FEHLER] Kein Python gefunden!
    pause
    exit /b 1
)

%PY_CMD% fps_checker.py
pause
