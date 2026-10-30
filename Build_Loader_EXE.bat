@echo off
title Build Standalone Commercial Loader EXE
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY_CMD%"=="" where py >nul 2>nul && set "PY_CMD=py"
if "%PY_CMD%"=="" where python >nul 2>nul && set "PY_CMD=python"

echo =======================================================================
echo    BUILDING LEAN COMMERCIAL CLIENT LOADER.EXE (FAST BUILD)
echo =======================================================================
echo.

%PY_CMD% -m PyInstaller --noconsole --onefile --name "Loader" --clean ^
    --exclude-module torch ^
    --exclude-module torchvision ^
    --exclude-module tensorrt ^
    --exclude-module ultralytics ^
    --exclude-module onnxruntime ^
    --exclude-module cv2 ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    commercial_loader.py

if exist "dist\Loader.exe" (
    copy /y "dist\Loader.exe" "Loader.exe" >nul
    echo.
    echo =======================================================================
    echo  [SUCCESS] Standalone Loader.exe compiled successfully!
    echo =======================================================================
) else (
    echo [ERROR] Build failed. Check console output above.
)

pause
