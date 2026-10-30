@echo off
title AURA - Hardware Diagnostic & Live Console
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo =======================================================================
echo    AURA TACTICAL VISION // SYSTEM & GPU DIAGNOSTICS
echo =======================================================================
echo.

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if "%PY_CMD%"=="" where py >nul 2>nul && set "PY_CMD=py"
if "%PY_CMD%"=="" where python >nul 2>nul && set "PY_CMD=python"

if "%PY_CMD%"=="" (
    echo [FEHLER] Kein Python gefunden! Bitte installiere Python 3.11 von python.org
    echo WICHTIG: Beim Installieren den Haken bei "Add python.exe to PATH" setzen!
    pause
    exit /b 1
)

echo [1] Verwende Python: %PY_CMD%
%PY_CMD% -c "import sys; print('    Version: Python ' + sys.version.split()[0])"
echo.

echo [2] Pruefe NVIDIA CUDA & TensorRT Status...
%PY_CMD% -c "import torch; print('    PyTorch Version: ' + torch.__version__); print('    CUDA Verfuegbar: ' + ('JA (GPU: ' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'NEIN (Laeuft auf CPU!)'))" 2>nul
if %errorlevel% neq 0 (
    echo    [WARNUNG] PyTorch ist noch nicht mit CUDA installiert!
    echo    Installiere jetzt automatisch PyTorch CUDA 12.1...
    echo.
    %PY_CMD% -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
    %PY_CMD% -m pip install onnxruntime-gpu tensorrt
)

echo.
echo [3] Pruefe ONNX Runtime GPU Provider...
%PY_CMD% -c "import onnxruntime as ort; print('    ONNX Providers: ' + str(ort.get_available_providers()))" 2>nul

echo.
echo =======================================================================
echo    WICHTIGER HINWEIS FUER DAS SPIEL:
echo    Stelle das Spiel in den Grafik-Optionen unbedingt auf:
echo    👉 'RAHMENLOSES FENSTER' (Borderless Windowed / Windowed Fullscreen)!
echo    Im exklusiven 'Vollbild' sperrt Windows die Bildschirmuebertragung
echo    und bremst auf 20 FPS herunter!
echo =======================================================================
echo.
echo Starte Vision Engine mit Live-Debug-Ausgabe...
echo.

%PY_CMD% yolo_main.py
pause
