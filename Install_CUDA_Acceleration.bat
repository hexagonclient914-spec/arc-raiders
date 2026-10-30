@echo off
title AURA - Install NVIDIA GPU Acceleration (250+ FPS)
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo =======================================================================
echo    AURA TACTICAL VISION // GPU ACCELERATION SETUP (RTX 4060 Ti)
echo =======================================================================
echo.

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if "%PY_CMD%"=="" where py >nul 2>nul && set "PY_CMD=py"
if "%PY_CMD%"=="" where python >nul 2>nul && set "PY_CMD=python"

if "%PY_CMD%"=="" (
    echo [FEHLER] Kein Python gefunden!
    pause
    exit /b 1
)

echo [1/3] Entferne alte CPU-Bibliotheken (damit keine Konflikte entstehen)...
%PY_CMD% -m pip uninstall -y torch torchvision onnxruntime onnxruntime-gpu

echo.
echo [2/3] Installiere PyTorch fuer NVIDIA RTX (CUDA 12.1)...
%PY_CMD% -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

echo.
echo [3/3] Installiere ONNX Runtime GPU fuer Tensor Cores...
%PY_CMD% -m pip install onnxruntime-gpu

echo.
echo =======================================================================
echo [TEST] Pruefe ob RTX 4060 Ti jetzt erkannt wird:
%PY_CMD% -c "import torch; print('CUDA Status: ' + ('AKTIV (GPU: ' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'FEHLER: Noch immer CPU'))"
echo =======================================================================
echo.
pause
