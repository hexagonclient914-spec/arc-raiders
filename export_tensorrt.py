"""
ARC Raiders - NVIDIA TensorRT Model Compiler
Converts PyTorch (.pt) models into ultra-fast NVIDIA TensorRT (.engine) format
specifically optimized for the Tensor Cores on NVIDIA RTX GPUs.
"""

import sys
import os
import time
import torch
from ultralytics import YOLO

def export_model_to_tensorrt(model_path="arc_raiders_yolo11n.pt", imgsz=640, half=True):
    print("=" * 65)
    print("      ARC RAIDERS - NVIDIA TENSORRT COMPILER (RTX 4060)")
    print("=" * 65)

    if not torch.cuda.is_available():
        print("[FEHLER] Keine NVIDIA CUDA GPU gefunden!")
        return None

    gpu_name = torch.cuda.get_device_name(0)
    print(f"[OK] Ziel-GPU: {gpu_name}")

    if not os.path.exists(model_path):
        print(f"[FEHLER] Modelldatei nicht gefunden: {model_path}")
        return None

    print(f"\n[1/2] Lade PyTorch Modell: {model_path}...")
    model = YOLO(model_path)

    print(f"[2/2] Compiliere zu NVIDIA TensorRT Engine (FP16, imgsz={imgsz})...")
    print("      (NVIDIA optimiert Layer, Speicher-Layout und Tensor Cores)")
    print("      Bitte warten, dauert ca. 1-2 Minuten...\n")

    t0 = time.time()
    try:
        exported_path = model.export(
            format="engine",
            half=half,
            dynamic=False,
            imgsz=imgsz,
            device=0,
            verbose=True
        )
        t1 = time.time()
        print("\n" + "=" * 65)
        print(f"ERFOLG! TensorRT Engine compiliert in {t1 - t0:.1f} Sekunden!")
        print(f"Engine-Datei: {exported_path}")
        print("Erwartete Inferenz-Zeit: ~3 - 5 ms (150 - 250+ FPS)!")
        print("=" * 65)
        return exported_path
    except Exception as e:
        print(f"\n[FEHLER beim TensorRT Export]: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    elif os.path.exists("valorant_30k_640.pt"):
        target = "valorant_30k_640.pt"
    elif os.path.exists("arc_raiders_yolo11n.pt"):
        target = "arc_raiders_yolo11n.pt"
    else:
        target = "GGMCS2.pt"
    export_model_to_tensorrt(target)
