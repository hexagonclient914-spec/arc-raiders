"""
Ultra-Compact Live FPS & Latency Diagnostic HUD
Shows Real-Time Capture FPS, TensorRT Inference FPS, and End-to-End Latency.
"""

import sys
import os
import time
import ctypes
import numpy as np
import mss
import torch
from ultralytics import YOLO

# High precision timer
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Prefer TensorRT engine for 140+ FPS
models = [
    "arc_raiders_yolo11_better.engine",
    "valorant_30k_640.engine",
    "yolo11s.pt",
    "yolo11n.pt"
]

selected_model = None
for m in models:
    p = os.path.join(BASE_DIR, m)
    if os.path.exists(p):
        selected_model = p
        break

if not selected_model:
    print("[FEHLER] Kein Modell gefunden!")
    sys.exit(1)

model_name = os.path.basename(selected_model)
is_trt = selected_model.endswith(".engine")
backend_str = "TensorRT FP16 (Ultra-Fast)" if is_trt else "PyTorch CUDA"

print("=" * 65)
print("       REAL-TIME FPS & LATENCY DIAGNOSTIC MONITOR")
print("=" * 65)
print(f"Modell : {model_name}")
print(f"Backend: {backend_str}")
print(f"GPU    : {torch.cuda.get_device_name(0)}")
print("=" * 65)

# Load Model
if is_trt:
    model = YOLO(selected_model, task="detect")
else:
    model = YOLO(selected_model)
    model.to("cuda:0")

# Setup Capture (Center Crop 640x640)
user32 = ctypes.windll.user32
sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
rw, rh = 640, 640
left = (sw - rw) // 2
top = (sh - rh) // 2
reg = {"left": left, "top": top, "width": rw, "height": rh}

sct = mss.mss()

# Warmup GPU
print("Optimiere GPU-Pipeline & führe Warmup durch...")
dummy = np.zeros((640, 640, 3), dtype=np.uint8)
for _ in range(15):
    model.predict(dummy, verbose=False, device="cuda:0")
torch.cuda.synchronize()

print("\n[LIVE MONITOR] (Beenden mit Strg+C)\n")
print(f"{'Frame':>6} | {'FPS':>8} | {'Capture (ms)':>13} | {'Inferenz (ms)':>14} | {'Gesamt (ms)':>12}")
print("-" * 65)

frame_id = 0
fps_timer = time.perf_counter()
frames_in_sec = 0
current_fps = 0.0

try:
    while True:
        t0 = time.perf_counter()

        # 1. Zero-Copy Capture
        grabbed = sct.grab(reg)
        bgr = np.frombuffer(grabbed.raw, dtype=np.uint8).reshape((grabbed.height, grabbed.width, 4))[:, :, :3]
        t1 = time.perf_counter()

        # 2. Inference
        with torch.inference_mode():
            res = model.predict(bgr, verbose=False, device="cuda:0", conf=0.35, iou=0.45)
        t2 = time.perf_counter()

        t_cap = (t1 - t0) * 1000.0
        t_inf = (t2 - t1) * 1000.0
        t_total = (t2 - t0) * 1000.0

        frame_id += 1
        frames_in_sec += 1

        now = time.perf_counter()
        if now - fps_timer >= 0.5:
            current_fps = frames_in_sec / (now - fps_timer)
            frames_in_sec = 0
            fps_timer = now

            # Print diagnostic row
            print(f"{frame_id:6d} | {current_fps:7.1f} | {t_cap:11.2f} ms | {t_inf:12.2f} ms | {t_total:10.2f} ms", flush=True)

except KeyboardInterrupt:
    pass
finally:
    sct.close()
    try:
        ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass
    print("\nMonitor gestoppt.")
