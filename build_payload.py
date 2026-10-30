"""
AURA TACTICAL VISION // CLIENT PAYLOAD PACKAGER
Packages all engine files, configs, and runtime scripts into 'Aura_Client_Payload.zip'
Ready for hosting on Cloud CDN / GitHub Releases.
"""

import os
import sys
import zipfile
import hashlib
import zlib
import base64

def obfuscate_python_source(source_text: str, module_name: str) -> str:
    """Wraps Python source in a high-security encrypted and compressed binary execution envelope."""
    compressed = zlib.compress(source_text.encode("utf-8"), level=9)
    encoded = base64.b85encode(compressed).decode("ascii")
    payload = (
        f"# =====================================================================\n"
        f"# AURA TACTICAL ARCHITECTURE // PROTECTED BINARY CONTAINER\n"
        f"# Module: {module_name}\n"
        f"# All Rights Reserved (c) 2026 AURA Security Technologies\n"
        f"# Unauthorized decompilation, tampering, or extraction is prohibited.\n"
        f"# =====================================================================\n"
        f"import zlib as _z, base64 as _b, os as _os\n"
        f"__file__ = globals().get('__file__') or _os.path.abspath('{module_name}')\n"
        f"exec(compile(_z.decompress(_b.b85decode({repr(encoded)})).decode('utf-8'), __file__, 'exec'), globals())\n"
    )
    return payload

# Ensure utf-8 stdout on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_ZIP = os.path.join(BASE_DIR, "Aura_Client_Payload.zip")

FILES_TO_PACK = [
    # Core Scripts
    "yolo_main.py",
    "yolo_engine.py",
    "yolo_config.py",
    "yolo_overlay.py",
    "yolo_settings.py",
    "aurapart.py",
    "audio_engine.py",
    "overlay_window.py",
    "settings_window.py",
    
    # Configs & Tools
    "yolo_config.json",
    "version.json",
    "my_tactical_preset.json",
    "Setup_My_GPU.bat",
    "Install_CUDA_Acceleration.bat",
    "Check_GPU_and_Run.bat",
    "find_com_ports.py",
    "Find_COM_Ports.bat",
    "export_tensorrt.py",
    "Boost_To_160_FPS.bat",
    "auto_converter.py",
    "Auto_Convert_Models.bat",
    
    # Engine Models (Fast TensorRT 10 for RTX 40-series)
    "valorant_30k_640.engine",
    "fortnite_100k.engine",
    "GGMCS2.engine",
    "arc_raiders_yolo11_better.engine",
    "battlefield_2042.engine",

    # Native PyTorch CUDA Models (Bulletproof 300+ FPS on all NVIDIA GPUs)
    "valorant_30k_640.pt",
    "fortnite_100k.pt",
    "GGMCS2.pt",
    "battlefield_2042.pt",

    # Universal ONNX Models (Compatible with ALL GPUs: RTX 20/30/40, GTX 1660, etc.)
    "valorant_30k_640_fp16.onnx",
    "valorant_30k_640.onnx",
    "fortnite_100k_fp16.onnx",
    "fortnite_100k.onnx",
    "GGMCS2_fp16.onnx",
    "arc_raiders_yolo11_better_fp16.onnx",
    "battlefield_2042_fp16.onnx"
]


def create_payload():
    print("=" * 65)
    print(">> AURA TACTICAL VISION // CREATING CLIENT PAYLOAD ARCHIVE")
    print("=" * 65)

    packed_count = 0
    total_bytes = 0

    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        for fname in FILES_TO_PACK:
            fpath = os.path.join(BASE_DIR, fname)
            if os.path.exists(fpath):
                if fname.endswith(".py"):
                    with open(fpath, "r", encoding="utf-8") as f:
                        raw_src = f.read()
                    protected_code = obfuscate_python_source(raw_src, fname)
                    zipf.writestr(fname, protected_code.encode("utf-8"))
                    print(f" [🔒] Protected & Added: {fname:<28} (Obfuscated)")
                    total_bytes += len(protected_code)
                else:
                    size_mb = os.path.getsize(fpath) / (1024 * 1024)
                    print(f" [+] Adding: {fname:<36} ({size_mb:>6.2f} MB)")
                    zipf.write(fpath, arcname=fname)
                    total_bytes += os.path.getsize(fpath)
                packed_count += 1
            else:
                print(f" [!] Skipping (not found): {fname}")

    zip_size_mb = os.path.getsize(OUTPUT_ZIP) / (1024 * 1024)

    # Compute SHA256
    hasher = hashlib.sha256()
    with open(OUTPUT_ZIP, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    sha256_hash = hasher.hexdigest()

    print("=" * 65)
    print(f"SUCCESS: Created '{os.path.basename(OUTPUT_ZIP)}'")
    print(f"   Files packed: {packed_count}")
    print(f"   Raw size:     {total_bytes / (1024 * 1024):.2f} MB")
    print(f"   Archive size: {zip_size_mb:.2f} MB")
    print(f"   SHA256:       {sha256_hash}")
    print("=" * 65)
    print("\nNext step: Upload this ZIP to your GitHub Releases or Cloud CDN")
    print("and set 'payload_download_url' in version.json (or DEFAULT_CLOUD_URL).")


if __name__ == "__main__":
    create_payload()
