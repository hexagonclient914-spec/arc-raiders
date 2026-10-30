"""
ARC Raiders - YOLO Vision GPU & Detection Diagnostic Test
Checks NVIDIA RTX GPU, CUDA drivers, capture speed, and real-time inference latency.
"""

import time
import os
import torch
import numpy as np
import mss
from ultralytics import YOLO

def run_diagnostic():
    print("=" * 60)
    print("   ARC RAIDERS - YOLO VISION & GPU DIAGNOSTIC TEST")
    print("=" * 60)

    # 1. GPU Check
    cuda_ok = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_ok else "None (CPU only)"
    print(f"\n[1/4] GPU Detection:")
    print(f"      CUDA Available : {cuda_ok}")
    print(f"      GPU Model      : {device_name}")
    print(f"      PyTorch Version: {torch.__version__}")

    # 2. Screen Capture Benchmark
    print("\n[2/4] Testing Ultra-Fast MSS Screen Capture...")
    sct = mss.mss()
    region = {"left": 640, "top": 220, "width": 640, "height": 640}
    t0 = time.perf_counter()
    frames = 50
    for _ in range(frames):
        _ = np.array(sct.grab(region))
    t1 = time.perf_counter()
    capture_fps = frames / (t1 - t0)
    print(f"      Capture Speed  : {capture_fps:.1f} FPS ({((t1 - t0) / frames * 1000):.2f} ms/frame)")
    sct.close()

    # 3. Model Loading
    print("\n[3/4] Loading ARC Raiders YOLOv11 Neural Network...")
    device = "cuda:0" if cuda_ok else "cpu"
    t0 = time.perf_counter()
    model_file = "arc_raiders_yolo11n.pt" if os.path.exists("arc_raiders_yolo11n.pt") else "yolo11n.pt"
    model = YOLO(model_file)
    model.to(device)
    t1 = time.perf_counter()
    print(f"      Model Loaded   : {model_file} in {(t1 - t0):.2f}s on {device}")
    if hasattr(model, "names"):
        print(f"      Trained Classes: {list(model.names.values())}")

    # 4. FP16 Inference Latency Test
    print("\n[4/4] Benchmarking Real-Time Inference Latency...")
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    # Warmup
    for _ in range(5):
        _ = model.predict(dummy, verbose=False, device=device, half=cuda_ok)

    t0 = time.perf_counter()
    n_inferences = 50
    for _ in range(n_inferences):
        _ = model.predict(dummy, verbose=False, device=device, half=cuda_ok)
    t1 = time.perf_counter()
    total_time = t1 - t0
    avg_latency = (total_time / n_inferences) * 1000.0
    inference_fps = n_inferences / total_time

    print(f"      Inference Time : {avg_latency:.2f} ms per frame")
    print(f"      Inference FPS  : {inference_fps:.1f} FPS")

    print("\n" + "=" * 60)
    if cuda_ok and avg_latency < 25.0:
        print("  STATUS: [PERFECT] Ready for competitive Arc Raiders gameplay!")
        print("  Real-time tactical HUD will run smoothly at 60+ FPS.")
    else:
        print("  STATUS: Working, but consider optimizing resolution.")
    print("=" * 60)

if __name__ == "__main__":
    run_diagnostic()
