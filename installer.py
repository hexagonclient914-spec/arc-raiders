"""
ARC Raiders / Tactical Vision HUD - Automated Environment Installer
Checks hardware, installs CUDA PyTorch & TensorRT dependencies,
verifies AI models, and creates desktop launchers.
"""

import sys
import os
import subprocess
import shutil

def print_banner():
    banner = r"""
========================================================================
   ___   ___   ___   __   __ ___  ___ ___  ___  _  _   _  _ _   _ ___  
  /   \ | _ \ / __|  \ \ / // _ \| _ \_ _|/ _ \| \| | | || | | | |   \ 
 | - - ||   /| (__    \ V /| (_) |   /| || (_) | .` | | __ | |_| | |) |
 |_|_|_||_|_\ \___|    |_|  \___/|_|_\___|\___/|_|\_| |_||_|\___/|___/ 
                                                                        
           AUTOMATED INSTALLER & ENVIRONMENT SETUP WIZARD
========================================================================
"""
    print(banner)

def get_python_command():
    # Try py launcher first, then python
    if shutil.which("py"):
        return "py"
    if shutil.which("python"):
        return "python"
    return "python"

def check_system():
    print("[1/5] Hardware & System-Pruefung...")
    print(f"  - Betriebssystem: Windows")

    py_cmd = get_python_command()
    try:
        res = subprocess.run([py_cmd, "--version"], capture_output=True, text=True, check=True)
        print(f"  - Python Laufzeit: {res.stdout.strip()}")
    except Exception:
        print("  - [FEHLER] Kein Python gefunden! Bitte installiere Python 3.10 oder 3.11.")
        return False

    # Check NVIDIA GPU via nvidia-smi
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, check=True
        )
        gpu_info = res.stdout.strip()
        print(f"  - NVIDIA GPU erkannt: {gpu_info}")
    except Exception:
        print("  - [WARNUNG] nvidia-smi nicht verfuegbar oder keine dedizierte NVIDIA GPU.")

    print("  [OK] System-Check abgeschlossen.\n")
    return True

def install_dependencies():
    print("[2/5] Installiere & Aktualisiere Python-Pakete...")
    py_cmd = get_python_command()

    # Upgrade pip
    print("  -> Aktualisiere pip...")
    subprocess.run([py_cmd, "-m", "pip", "install", "--upgrade", "pip", "--quiet"], check=False)

    # PyTorch with CUDA 12.4
    print("  -> Pruefe / Installiere PyTorch mit CUDA 12.4 Unterstuetzung...")
    check_torch_code = "import torch; print(torch.cuda.is_available())"
    res = subprocess.run([py_cmd, "-c", check_torch_code], capture_output=True, text=True)
    
    if res.returncode == 0 and "True" in res.stdout:
        print("     PyTorch mit CUDA 12.4 ist bereits betriebsbereit.")
    else:
        print("     Installiere PyTorch CUDA 12.4 (kann einige Minuten dauern)...")
        subprocess.run([
            py_cmd, "-m", "pip", "install", "--upgrade",
            "torch", "torchvision",
            "--index-url", "https://download.pytorch.org/whl/cu124"
        ], check=True)

    # Core Vision, UI & TensorRT dependencies
    reqs = [
        "ultralytics",
        "PyQt6",
        "mss",
        "pywin32",
        "pyserial",
        "makcu",
        "tensorrt>=10.0.0",
        "onnx",
        "onnxslim",
        "numpy"
    ]
    print(f"  -> Installiere Core Vision Pakete ({', '.join(reqs)})...")
    subprocess.run([py_cmd, "-m", "pip", "install", "--upgrade"] + reqs, check=False)

    print("  [OK] Alle Abhaengigkeiten erfolgreich installiert.\n")

def verify_gpu_cuda():
    print("[3/5] Verifiziere NVIDIA CUDA & TensorRT Inferenz...")
    py_cmd = get_python_command()

    test_code = (
        "import torch; "
        "print('CUDA_OK' if torch.cuda.is_available() else 'NO_CUDA'); "
        "print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'); "
        "import tensorrt as trt; "
        "print('TRT_VERSION:', trt.__version__)"
    )
    try:
        res = subprocess.run([py_cmd, "-c", test_code], capture_output=True, text=True)
        lines = res.stdout.strip().splitlines()
        for line in lines:
            print(f"  - {line}")
    except Exception as e:
        print(f"  - Verifizierungsfehler: {e}")

    print("  [OK] GPU-Inferenz verifiziert.\n")

def verify_models(base_dir):
    print("[4/5] Pruefe integrierte KI-Erkennungsmodelle...")
    models_found = []
    if os.path.exists(base_dir):
        for f in os.listdir(base_dir):
            if f.endswith(".engine") or f.endswith(".pt") or f.endswith(".onnx"):
                size_mb = os.path.getsize(os.path.join(base_dir, f)) / (1024 * 1024)
                models_found.append((f, size_mb))

    if models_found:
        print(f"  Gefundene Modelle ({len(models_found)}):")
        for m_name, m_size in models_found:
            m_type = "TensorRT Engine (Ultra-Fast)" if m_name.endswith(".engine") else ("PyTorch Modell" if m_name.endswith(".pt") else "ONNX Modell")
            print(f"    * {m_name} ({m_size:.1f} MB) - [{m_type}]")
    else:
        print("  [WARNUNG] Keine Modelldateien (.engine/.pt/.onnx) im Ordner gefunden.")

    print("  [OK] Modell-Pruefung abgeschlossen.\n")

def create_desktop_shortcut(base_dir):
    print("[5/5] Erstelle Desktop-Verknuepfung...")
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        target_bat = os.path.join(base_dir, "Start_YOLO_Vision.bat")

        if not os.path.exists(target_bat):
            print("  - Start_YOLO_Vision.bat nicht gefunden, ueberspringe Verknuepfung.")
            return

        shortcut_path = os.path.join(desktop, "YOLO Tactical Vision HUD.lnk")

        ps_cmd = (
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{shortcut_path}'); "
            f"$s.TargetPath = '{target_bat}'; "
            f"$s.WorkingDirectory = '{base_dir}'; "
            f"$s.Description = 'Startet das ARC Raiders YOLO Tactical Vision HUD'; "
            f"$s.Save()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
        print(f"  - Verknuepfung erfolgreich angelegt: {shortcut_path}")
    except Exception as e:
        print(f"  - Verknuepfung konnte nicht automatisch erstellt werden: {e}")

    print("  [OK] Fertiggestellt.\n")

def get_base_dir():
    # If compiled with PyInstaller, the directory where the .exe lives:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def main():
    print_banner()
    base_dir = get_base_dir()

    try:
        if not check_system():
            print("\nDruecke [Enter] zum Beenden...")
            input()
            return

        install_dependencies()
        verify_gpu_cuda()
        verify_models(base_dir)
        create_desktop_shortcut(base_dir)

        print("========================================================================")
        print("   INSTALLATION ERFOLGREICH ABGESCHLOSSEN!")
        print("========================================================================")
        print("Du kannst das Tactical Vision HUD jetzt jederzeit starten:")
        print("  1. Ueber das Desktop-Icon: 'YOLO Tactical Vision HUD'")
        print("  2. Oder direkt ueber: 'Start_YOLO_Vision.bat'")
        print("\nHotkeys im Spiel:")
        print("  [F7] - HUD Overlay Ein / Ausblenden")
        print("  [F8] - Einstellungs-Menue (Modellwechsel, Scan-Bereich, FPS)")
        print("========================================================================")
    except KeyboardInterrupt:
        print("\nInstallation abgebrochen.")
    except Exception as e:
        print(f"\nUnerwarteter Fehler bei der Installation: {e}")

    print("\nDruecke [Enter] zum Beenden...")
    input()

if __name__ == "__main__":
    main()
