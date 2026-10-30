@echo off
title MAKCU // COM-Port Scanner und Hardware-Diagnose
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo =======================================================================
echo    MAKCU // COM-PORT SCANNER UND HARDWARE-DIAGNOSE
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

if not "%PY_CMD%"=="" (
    :: Ensure pyserial and makcu are ready
    %PY_CMD% -c "import serial, makcu" >nul 2>nul
    if %errorlevel% neq 0 (
        echo [INFO] Richte serielle Diagnose-Bibliotheken ein...
        %PY_CMD% -m pip install pyserial makcu >nul 2>nul
    )
    %PY_CMD% find_com_ports.py
    goto :done
)

echo [HINWEIS] Python nicht direkt verfuegbar. Fuehre direkten Windows Hardware-Scan aus...
echo.
powershell -NoProfile -Command "& { Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -eq 'Ports' -or $_.Name -match 'COM\d+' } | Select-Object Name, DeviceID, Status | Format-Table -AutoSize }"

:done
echo.
echo =======================================================================
echo  Scan abgeschlossen. Druecke eine beliebige Taste zum Beenden.
echo =======================================================================
pause