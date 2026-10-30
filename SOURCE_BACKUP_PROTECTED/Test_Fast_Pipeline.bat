@echo off
title YOLO11 Ultra-Fast Real-Time Vision Benchmark
cd /d "%~dp0"
echo =========================================================
echo    YOLO11 ULTRA-FAST VISION PIPELINE (RTX 4060 TENSORRT)
echo =========================================================
echo.
echo Starte entkoppelte DXcam / Zero-Copy Inferenz-Schleife...
echo.
py yolo_vision_fast.py
if errorlevel 1 (
    echo.
    echo Ein Fehler ist aufgetreten. Druecke eine Taste...
    pause
)
