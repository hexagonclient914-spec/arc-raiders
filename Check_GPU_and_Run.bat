@echo off
title AURA - Hardware Diagnostic und Live Console
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo =======================================================================
echo    AURA TACTICAL VISION // SYSTEM UND GPU DIAGNOSTICS
echo =======================================================================
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
    echo [FEHLER] Kein Python gefunden! Bitte installiere Python 3.11 von python.org
    pause
    exit /b 1
)

echo [1] Verwende Python: "%PY_CMD%"
"%PY_CMD%" -c "import sys; print('    Version: Python ' + sys.version.split()[0])"
echo.

echo [2] Pruefe NVIDIA CUDA und PyTorch Status...
"%PY_CMD%" -c "import torch; print('    PyTorch Version: ' + torch.__version__); print('    CUDA Status: ' + ('AKTIV (GPU: ' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'CPU (Kein CUDA)'))"

echo.
echo [3] Pruefe ONNX Runtime GPU Providers...
"%PY_CMD%" -c "import onnxruntime as ort; print('    Providers: ' + str(ort.get_available_providers()))"

echo.
echo =======================================================================
echo    Starte Vision Engine...
echo =======================================================================
echo.

"%PY_CMD%" yolo_main.py
pause
