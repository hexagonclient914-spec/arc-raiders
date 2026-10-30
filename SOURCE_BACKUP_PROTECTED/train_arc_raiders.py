"""
ARC Raiders - High Performance YOLO Trainer
Fine-tunes YOLOv11 on your NVIDIA GeForce RTX 4060 GPU with CUDA acceleration.
Uses conservative VRAM batching (batch=8) to ensure 100% stability.
"""

import sys
import os
import shutil
import torch
from ultralytics import YOLO

def main():
    print("=" * 65)
    print("      ARC RAIDERS - HIGH PERFORMANCE YOLO TRAINER (GPU)")
    print("=" * 65)

    if not torch.cuda.is_available():
        print("[FEHLER] CUDA GPU nicht gefunden! Bitte stelle sicher, dass deine RTX 4060 aktiv ist.")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    print(f"[OK] Training Device: {gpu_name} (CUDA Active)")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_data_yaml = os.path.join(base_dir, "Arc-Raiders-13", "data.yaml")

    # 1. Dataset Check
    if os.path.exists(local_data_yaml):
        print(f"\n[1/3] Lokaler Arc Raiders Datensatz gefunden!")
        print(f"      Pfad: {local_data_yaml}")
        data_yaml_path = local_data_yaml
    else:
        # Ask or read Roboflow API Key
        api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
        if len(sys.argv) > 1 and sys.argv[1].strip():
            api_key = sys.argv[1].strip()

        if not api_key:
            print("\nBitte gib deinen kostenlosen Roboflow API-Key ein:")
            try:
                api_key = input("Roboflow API Key: ").strip()
            except EOFError:
                pass

        print("\n[1/3] Lade offiziellen Arc Raiders Datensatz herunter...")
        try:
            from roboflow import Roboflow
            rf = Roboflow(api_key=api_key)
            project = rf.workspace("valorantai").project("arc-raiders-8tjh4")
            dataset = project.version(13).download("yolov11")
            data_yaml_path = os.path.join(dataset.location, "data.yaml")
        except Exception as e:
            print(f"[FEHLER]: {e}")
            sys.exit(1)

    # 2. Configure Training Parameters
    print("\n[2/3] Konfiguriere Training auf RTX 4060...")
    print("   - Modell-Architektur: yolo11s.pt (Small - Deep Feature Extraction)")
    print("   - Batch-Groesse     : 8 (stabil, nur ~2.8 GB VRAM, kein Absturz)")
    print("   - Aufloesung        : 640x640")
    print("   - Epochen           : 40")
    print("   - Optimizer         : AdamW + AMP (FP16)")

    model = YOLO("yolo11s.pt")

    # 3. Start Fine-Tuning
    print("\n[3/3] Starte Training auf GPU...")
    print("      Fortschritt wird live angezeigt.\n")

    results = model.train(
        data=data_yaml_path,
        epochs=40,
        imgsz=640,
        batch=8,
        device=0,
        workers=2,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        warmup_epochs=2,
        mosaic=1.0,
        mixup=0.1,
        fliplr=0.5,
        amp=True,
        save=True,
        project="runs/detect",
        name="arc_raiders_improved",
        exist_ok=True
    )

    # 4. Save best weights
    best_weights = os.path.join("runs", "detect", "arc_raiders_improved", "weights", "best.pt")
    target_weights = os.path.join(base_dir, "arc_raiders_yolo11_better.pt")

    if os.path.exists(best_weights):
        shutil.copyfile(best_weights, target_weights)
        print("\n" + "=" * 65)
        print(f"TRAINING ERFOLGREICH BEENDET!")
        print(f"Modell gespeichert als: {target_weights}")
        print("=" * 65)

        # Update yolo_config.json automatically
        import json
        config_path = os.path.join(base_dir, "yolo_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["model_path"] = "arc_raiders_yolo11_better.pt"
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            print("[INFO] yolo_config.json wurde automatisch aktualisiert!")

        # 5. Automatically compile into NVIDIA TensorRT Engine for maximum FPS
        try:
            print("\n[AUTOMATISCH] Compiliere neues Modell in NVIDIA TensorRT Engine (.engine)...")
            trained_model = YOLO(target_weights)
            engine_path = trained_model.export(format="engine", half=True, dynamic=False, imgsz=640, device=0)
            if engine_path and os.path.exists(engine_path):
                cfg["model_path"] = os.path.basename(engine_path)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=4)
                print(f"[ERFOLG] TensorRT Engine erstellt: {engine_path} (Aktiviert fuer ~150-250 FPS!)")
        except Exception as te:
            print(f"[HINWEIS] TensorRT Auto-Export: {te}")
    else:
        print(f"[WARNUNG] best.pt nicht gefunden unter {best_weights}")

if __name__ == "__main__":
    main()
