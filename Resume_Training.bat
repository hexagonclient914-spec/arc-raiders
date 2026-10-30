@echo off
title ARC Raiders - YOLOv11 Training Resume
cd /d "%~dp0"
echo =======================================================
echo     ARC RAIDERS - RESUME TRAINING (EPOCH 21 -> 40)
echo =======================================================
echo.
py resume_training.py
echo.
pause
