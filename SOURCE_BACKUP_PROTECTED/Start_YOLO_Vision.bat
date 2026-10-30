@echo off
title ARC Raiders // YOLO Tactical Vision HUD (Direct TensorRT 10)
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo =======================================================================
echo    ARC RAIDERS // YOLO TACTICAL VISION HUD (300+ FPS PRO)
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

if "%PY_CMD%"=="" (
    echo.
    echo =======================================================================
    echo  [FEHLER] Kein Python auf diesem PC gefunden!
    echo =======================================================================
    echo  Bitte fuehre zuerst einmalig "Start_Loader.bat" aus.
    echo.
    pause
    exit /b 1
)

:: Check if core packages are installed (first-time start check)
%PY_CMD% -c "import PyQt6, torch" >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [HINWEIS] Erster Start auf diesem PC erkannt!
    echo Fehlende Bibliotheken werden ueber Start_Loader.bat eingerichtet...
    echo.
    call Start_Loader.bat
    exit /b 0
)

:: Auto-check and auto-install makcu driver library if missing
%PY_CMD% -c "import makcu" >nul 2>nul
if %errorlevel% neq 0 (
    echo [SETUP] Installiere fehlende MAKCU-Bibliothek...
    %PY_CMD% -m pip install makcu
    echo [OK] MAKCU-Bibliothek bereitgestellt!
    echo.
)

echo Starting Screen Capture und GPU Detection Engine...
echo In-Game Hotkeys:
echo   [C]  - System und Aim EIN / AUS (mit Audio-Feedback)
echo   [F7] - HUD-Overlay Ein- / Ausblenden (Pure No-Overlay Modus)
echo   [F8] - Einstellungsmenue / Mini-Bar oeffnen
echo.

%PY_CMD% yolo_main.py

if %errorlevel% neq 0 (
    echo.
    echo =======================================================================
    echo  Das Programm wurde mit Fehlercode %errorlevel% beendet.
    echo  Wenn dies der erste Start ist, fuehre bitte "Start_Loader.bat" aus.
    echo =======================================================================
    pause
)