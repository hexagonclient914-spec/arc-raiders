"""
ARC Raiders - Resume YOLOv11 Training from Checkpoint
Resumes training seamlessly from last.pt (epoch 21 to 40).
"""

import os
import sys
import shutil
import torch
from ultralytics import YOLO

def main():
    print("=" * 65)
    print("      ARC RAIDERS - RESUME TRAINING (EPOCH 21 -> 40)")
    print("=" * 65)

    if not torch.cuda.is_available():
        print("[FEHLER] CUDA GPU nicht gefunden!")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    print(f"[OK] Training Device: {gpu_name} (CUDA Active)")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    last_weights = os.path.join(base_dir, "runs", "detect", "arc_raiders_improved", "weights", "last.pt")

    if not os.path.exists(last_weights):
        print(f"[FEHLER] Checkpoint nicht gefunden: {last_weights}")
        sys.exit(1)

    print(f"[OK] Lade letzten Checkpoint: {last_weights}")
    print("[OK] Setze Training nahtlos ab Epoche 21 fort...\n")

    try:
        model = YOLO(last_weights)
        model.train(resume=True)
    except Exception as e:
        print(f"\n[FEHLER beim Training]: {e}")
        sys.exit(1)

    print("\n" + "=" * 65)
    print("TRAINING VOLLSTAENDIG BEENDET (40/40 EPOCHEN)!")
    print("=" * 65)

    best_weights = os.path.join(base_dir, "runs", "detect", "arc_raiders_improved", "weights", "best.pt")
    target = os.path.join(base_dir, "arc_raiders_yolo11_better.pt")
    if os.path.exists(best_weights):
        shutil.copyfile(best_weights, target)
        print(f"[INFO] Neues finales Modell gespeichert als: {target}")

        # Update yolo_config.json
        import json
        config_path = os.path.join(base_dir, "yolo_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                cfg["model_path"] = "arc_raiders_yolo11_better.pt"
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=4)
                print("[INFO] yolo_config.json wurde automatisch aktualisiert!")
            except Exception:
                pass

if __name__ == "__main__":
    main()
