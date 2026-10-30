@echo off
title AURA Elite HUD
cd /d "%~dp0"
py aura_gui.py
if %errorlevel% neq 0 python aura_gui.py
pause
