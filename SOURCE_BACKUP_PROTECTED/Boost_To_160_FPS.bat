@echo off
title AURA - High-Speed TensorRT Engine Generator (160+ FPS)
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo =======================================================================
echo    AURA TACTICAL VISION // HIGH-SPEED TENSORRT ENGINE GENERATOR
echo =======================================================================
echo.
echo Dieses Tool optimiert die AI-Modelle speziell fuer deine RTX Grafikkarte!
echo Damit verdoppelt sich die Geschwindigkeit von 60 FPS auf 140 - 250+ FPS!
echo.

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if "%PY_CMD%"=="" if exist "C:\Python311\python.exe" set "PY_CMD=C:\Python311\python.exe"
if "%PY_CMD%"=="" if exist "C:\Python312\python.exe" set "PY_CMD=C:\Python312\python.exe"
if "%PY_CMD%"=="" if exist "C:\Program Files\Python311\python.exe" set "PY_CMD=C:\Program Files\Python311\python.exe"
if "%PY_CMD%"=="" if exist "C:\Program Files\Python312\python.exe" set "PY_CMD=C:\Program Files\Python312\python.exe"
if "%PY_CMD%"=="" (
    for /f "delims=" %%i in ('where py 2^>nul') do if "%PY_CMD%"=="" set "PY_CMD=%%i"
)
if "%PY_CMD%"=="" (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        echo %%i | findstr /i /v "WindowsApps" >nul && if "%PY_CMD%"=="" set "PY_CMD=%%i"
    )
)

if "%PY_CMD%"=="" (
    echo [FEHLER] Kein Python gefunden!
    pause
    exit /b 1
)

echo [1/2] Pruefe TensorRT Pakete...
"%PY_CMD%" -c "import tensorrt" >nul 2>nul
if %errorlevel% neq 0 (
    echo Installiere NVIDIA TensorRT 10...
    "%PY_CMD%" -m pip install tensorrt tensorrt-cu12
)

echo.
echo [2/2] Compiliere High-Speed Engine fuer deine Grafikkarte...
echo       Bitte warten, NVIDIA optimiert die Tensor Cores (dauert ca. 1 Minute)...
echo.

"%PY_CMD%" export_tensorrt.py valorant_30k_640.pt

echo.
echo =======================================================================
echo  Fertig! Deine Engine ist jetzt fuer maximale FPS optimiert!
echo  Starte jetzt die Loader.exe neu fuer 160 - 250+ FPS!
echo =======================================================================
pause
