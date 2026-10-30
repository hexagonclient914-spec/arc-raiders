@echo off
title YOLO Tactical Vision - C# .NET 8 DirectML
cd /d "%~dp0"

if exist "csharp_bin\YoloTacticalVisionCS.exe" (
    start "" "csharp_bin\YoloTacticalVisionCS.exe"
    exit
)
if exist "YoloTacticalVisionCS.exe" (
    start "" "YoloTacticalVisionCS.exe"
    exit
)

echo Starte C# Build...
dotnet run --project YoloTacticalVisionCS -c Release
