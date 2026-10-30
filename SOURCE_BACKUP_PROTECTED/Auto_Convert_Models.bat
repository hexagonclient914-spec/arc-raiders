@echo off
title AURA - Automatic Multi-Model TensorRT Compiler (200+ FPS)
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo =======================================================================
echo    AURA TACTICAL VISION // UNIVERSAL AI MODEL AUTO-CONVERTER
echo =======================================================================
echo.
echo Dieses Tool konvertiert alle KI-Modelle (.pt und .onnx) vollautomatisch
echo in extrem schnelle NVIDIA TensorRT .engine Dateien fuer deine GPU!
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
    echo [FEHLER] Kein Python gefunden! Bitte Python 3.11 oder 3.12 installieren.
    pause
    exit /b 1
)

echo [1/2] Pruefe NVIDIA TensorRT Pakete...
"%PY_CMD%" -c "import tensorrt" >nul 2>nul
if %errorlevel% neq 0 (
    echo Installiere NVIDIA TensorRT...
    "%PY_CMD%" -m pip install tensorrt tensorrt-cu12
)

echo.
echo [2/2] Starte automatischen Modell-Compiler...
echo.

"%PY_CMD%" auto_converter.py

echo.
echo =======================================================================
echo    FERTIG! Alle Modelle wurden fuer deine Grafikkarte optimiert.
echo =======================================================================
echo.
pause
