@echo off
title YOLO Tactical Vision - Auto Setup und Loader
set PYTHONIOENCODING=utf-8
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo =======================================================================
echo    YOLO TACTICAL VISION HUD - AUTO SETUP UND LOADER
echo =======================================================================
echo.

set "PY_CMD="
where py >nul 2>nul
if %errorlevel% equ 0 set "PY_CMD=py"
if "%PY_CMD%"=="" where python >nul 2>nul && set "PY_CMD=python"
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if "%PY_CMD%"=="" if exist "C:\Program Files\Python311\python.exe" set "PY_CMD=C:\Program Files\Python311\python.exe"
if "%PY_CMD%"=="" if exist "C:\Program Files\Python312\python.exe" set "PY_CMD=C:\Program Files\Python312\python.exe"

if "%PY_CMD%"=="" (
    echo.
    echo =======================================================================
    echo  [FEHLER] Python wurde auf diesem Computer nicht gefunden!
    echo =======================================================================
    echo.
    echo  1. Gehe auf: https://www.python.org/downloads/
    echo  2. Lade Python 3.11 fuer Windows herunter.
    echo  3. WICHTIG: Setze beim Installieren ganz unten den Haken:
    echo     [X] Add python.exe to PATH
    echo.
    echo  Druecke eine Taste, um die Python-Seite im Browser zu oeffnen...
    pause >nul
    start https://www.python.org/downloads/
    goto end
)

echo [OK] Verwende Python: %PY_CMD%
echo.
%PY_CMD% loader.py

if %errorlevel% neq 0 (
    echo.
    echo =======================================================================
    echo  Der Loader wurde mit einem Fehler beendet (Fehlercode: %errorlevel%).
    echo =======================================================================
)

:end
echo.
echo Druecke eine Taste zum Schliessen dieses Fensters...
pause >nul
