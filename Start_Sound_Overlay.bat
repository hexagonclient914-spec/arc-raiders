@echo off
title ARC Raiders Sound Overlay
cd /d "%~dp0"
echo ==========================================
echo     ARC RAIDERS - TACTICAL SOUND RADAR
echo ==========================================
echo.
echo Starting Audio Engine and HUD Overlay...
echo Hotkeys:
echo   [F9]  - Overlay Ein/Ausblenden
echo   [F10] - Einstellungen oeffnen/schliessen
echo.
py main.py
if errorlevel 1 (
    echo.
    echo Ein Fehler ist aufgetreten. Druecke eine Taste...
    pause
)
