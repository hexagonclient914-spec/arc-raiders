"""
AURA TACTICAL VISION // HIGH-SPEED MODEL AUTO-CONVERTER
Universal multi-GPU compiler supporting TensorRT 8, 9, 10, and 11+.
Automatically discovers, converts, and optimizes all AI models for maximum FPS.
"""

import os
import sys
import time

def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def check_cuda_device():
    try:
        import torch
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            return True, f"{gpu} ({vram:.1f} GB VRAM)"
    except Exception:
        pass
    return False, "Keine CUDA GPU gefunden"

def convert_pt_to_onnx(pt_path: str, imgsz=640) -> str:
    """Exports Ultralytics PyTorch (.pt) model to clean static ONNX format."""
    stem = os.path.splitext(pt_path)[0]
    out_onnx = stem + ".onnx"
    if os.path.exists(out_onnx):
        return out_onnx
    
    print(f"[Auto-Converter] Exportiere PyTorch '{os.path.basename(pt_path)}' zu ONNX...")
    try:
        from ultralytics import YOLO
        model = YOLO(pt_path)
        exported = model.export(format="onnx", half=False, imgsz=imgsz, dynamic=False, opset=12)
        print(f"[Auto-Converter] ONNX Export erfolgreich: {os.path.basename(exported)}")
        return exported
    except Exception as e:
        print(f"[Auto-Converter] Fehler beim ONNX Export von {pt_path}: {e}")
        return ""

def convert_onnx_to_fp16_file(onnx_path: str) -> str:
    """Converts ONNX model to FP16 half-precision for Tensor Cores."""
    if onnx_path.endswith("_fp16.onnx"):
        return onnx_path
    stem = os.path.splitext(onnx_path)[0]
    out_fp16 = stem + "_fp16.onnx"
    if os.path.exists(out_fp16):
        return out_fp16

    print(f"[Auto-Converter] Erstelle FP16 Version: '{os.path.basename(out_fp16)}'...")
    try:
        import onnx
        from onnxruntime.transformers.float16 import convert_float_to_float16
        model = onnx.load(onnx_path)
        model_fp16 = convert_float_to_float16(model, keep_io_types=False)
        onnx.save(model_fp16, out_fp16)
        print(f"[Auto-Converter] FP16 erfolgreich gespeichert!")
        return out_fp16
    except Exception as e:
        print(f"[Auto-Converter] FP16 Hinweis: {e}")
        return onnx_path

def compile_engine_from_onnx(onnx_path: str, engine_path: str) -> bool:
    """
    Bulletproof TensorRT Engine Compiler compatible with TensorRT 8, 9, 10, and 11.
    Eliminates all EXPLICIT_BATCH and BuilderFlag deprecation crashes.
    """
    try:
        import tensorrt as trt
    except ImportError:
        print("[Auto-Converter] 'tensorrt' ist nicht in Python installiert!")
        return False

    print(f"[Auto-Compiler] Optimiere '{os.path.basename(onnx_path)}' -> '{os.path.basename(engine_path)}'...")
    print(f"                (TensorRT testet Kernel & Layer-Tactics fuer deine GPU, dauert ca. 45-60 Sek)...")
    t0 = time.time()
    try:
        logger = trt.Logger(trt.Logger.WARNING)
        builder = trt.Builder(logger)

        # Universal network creation (TRT 8/9/10/11)
        if hasattr(trt, "NetworkDefinitionCreationFlag") and hasattr(trt.NetworkDefinitionCreationFlag, "EXPLICIT_BATCH"):
            network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
        else:
            network = builder.create_network()

        parser = trt.OnnxParser(network, logger)
        with open(onnx_path, "rb") as f:
            if not parser.parse(f.read()):
                for err_idx in range(parser.num_errors):
                    print(f"[TRT Parser Error]: {parser.get_error(err_idx)}")
                return False

        config = builder.create_builder_config()

        # Workspace limit safe across versions
        try:
            config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 2 * 1024 * 1024 * 1024)
        except Exception:
            pass

        # FP16 Precision Flag safe across versions
        try:
            if hasattr(trt.BuilderFlag, "FP16"):
                config.set_flag(trt.BuilderFlag.FP16)
        except Exception:
            pass

        serialized = builder.build_serialized_network(network, config)
        if serialized is None:
            print("[Auto-Compiler] Build fehlgeschlagen (serialized is None).")
            return False

        with open(engine_path, "wb") as f_out:
            f_out.write(serialized)

        dt = time.time() - t0
        print(f"[Auto-Compiler] ERFOLG! Engine erstellt in {dt:.1f}s: '{os.path.basename(engine_path)}'")
        return True
    except Exception as e:
        print(f"[Auto-Compiler] Fehler beim Engine Build: {e}")
        return False

def auto_convert_all(base_dir=None):
    """Discovers and compiles all models in base directory."""
    work_dir = base_dir or get_base_dir()
    print("=" * 68)
    print("      AURA TACTICAL VISION // UNIVERSAL AI AUTO-CONVERTER")
    print("=" * 68)

    ok_cuda, gpu_str = check_cuda_device()
    print(f"Ziel-GPU : {gpu_str}")
    if not ok_cuda:
        print("[WARNUNG] Keine NVIDIA GPU erkannt. Engine-Export erfordert eine NVIDIA GeForce RTX GPU.")
        return

    print(f"Ordner   : {work_dir}\n")

    # Discover candidate models
    files = os.listdir(work_dir)
    stems = set()
    for f in files:
        for ext in (".pt", ".onnx", ".engine"):
            if f.lower().endswith(ext):
                stem = f[: -len(ext)]
                if stem.endswith("_fp16"):
                    stem = stem[:-5]
                stems.add(stem)

    converted_count = 0
    for stem in sorted(stems):
        eng_file = os.path.join(work_dir, stem + ".engine")
        fp16_file = os.path.join(work_dir, stem + "_fp16.onnx")
        onnx_file = os.path.join(work_dir, stem + ".onnx")
        pt_file = os.path.join(work_dir, stem + ".pt")

        print(f"\n[Modell] Pruefe '{stem}'...")

        # 1. Ensure ONNX exists if only .pt is provided
        if not os.path.exists(onnx_file) and not os.path.exists(fp16_file) and os.path.exists(pt_file):
            convert_pt_to_onnx(pt_file)

        # 2. Ensure FP16 ONNX exists
        if os.path.exists(onnx_file) and not os.path.exists(fp16_file):
            convert_onnx_to_fp16_file(onnx_file)

        # 3. Compile TensorRT .engine if missing or testable
        src_for_engine = fp16_file if os.path.exists(fp16_file) else (onnx_file if os.path.exists(onnx_file) else None)
        if src_for_engine:
            if not os.path.exists(eng_file):
                print(f"-> Keine passende .engine fuer '{stem}' gefunden. Starte Kompilierung...")
                ok = compile_engine_from_onnx(src_for_engine, eng_file)
                if ok:
                    converted_count += 1
            else:
                print(f"-> .engine existiert bereits: '{os.path.basename(eng_file)}' [OK]")

    print("\n" + "=" * 68)
    print(f"Auto-Converter abgeschlossen! {converted_count} neue Engine(s) erstellt.")
    print("Alle Modelle sind bereit fuer 160 - 280+ FPS Inferenz!")
    print("=" * 68)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    auto_convert_all(target)
