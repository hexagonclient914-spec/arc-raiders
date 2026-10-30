@echo off
title AURA - Packaging Client Cloud Payload
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY_CMD%"=="" where py >nul 2>nul && set "PY_CMD=py"
if "%PY_CMD%"=="" where python >nul 2>nul && set "PY_CMD=python"

%PY_CMD% build_payload.py
pause
