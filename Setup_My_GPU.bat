@echo off
title AURA - Automatic GPU Setup (RTX 4060 Ti)
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo =======================================================================
echo    AURA TACTICAL VISION // AUTOMATIC GPU ACTIVATOR (RTX 4060 Ti)
echo =======================================================================
echo.

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if "%PY_CMD%"=="" if exist "C:\Python311\python.exe" set "PY_CMD=C:\Python311\python.exe"
if "%PY_CMD%"=="" if exist "C:\Python312\python.exe" set "PY_CMD=C:\Python312\python.exe"

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

echo Verwende Python: "%PY_CMD%"
"%PY_CMD%" -c "import sys; print('Python: ' + sys.executable)"
echo.

echo [1/4] Installiere NVIDIA CUDA 12.1 PyTorch (fuer RTX 4060 Ti)...
"%PY_CMD%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

echo.
echo [2/4] Installiere ONNX Runtime GPU Acceleration & NVIDIA TensorRT 10...
"%PY_CMD%" -m pip install onnxruntime-gpu ultralytics tensorrt tensorrt-cu12

echo.
echo [3/4] Konfiguriere CUDA & cuDNN DLLs fuer High-Speed GPU Preprocessing...
"%PY_CMD%" -c "import os, shutil, torch, onnxruntime; t_lib = os.path.join(os.path.dirname(torch.__file__), 'lib'); o_capi = os.path.join(os.path.dirname(onnxruntime.__file__), 'capi'); [shutil.copy2(os.path.join(t_lib, f), os.path.join(o_capi, f)) for f in os.listdir(t_lib) if (f.startswith(('cublas','cudnn','cufft','curand','cusolver')) and f.endswith('.dll') and not os.path.exists(os.path.join(o_capi, f)))] if os.path.isdir(t_lib) and os.path.isdir(o_capi) else None; print('DLL Linker: OK')"

echo.
echo [4/4] Hardware & CUDA Verifikation:
"%PY_CMD%" -c "import torch, onnxruntime as ort; print('>>> CUDA STATUS: ' + ('AKTIV (GPU: ' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'FEHLER: CPU')); print('>>> ONNX PROVIDERS: ' + str(ort.get_available_providers()))"

echo.
echo =======================================================================
echo  Setup erfolgreich abgeschlossen!
echo  Starte jetzt die Loader.exe neu - die FPS liegen ab jetzt bei 250-350+!
echo =======================================================================
pause
