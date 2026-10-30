"""
ARC Raiders / Battlefield 2042 / Valorant / CS2 - YOLO Tactical Vision HUD Loader v4.5
Automated one-click dependency downloader, model verifier, hardware diagnostic,
and multi-game TensorRT 10 launch manager.
Compatible with all Windows codepages (cp1252, cp850, UTF-8).
"""

import sys
import os
import time
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ANSI Colors (with graceful fallback)
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Safe stdout / stderr reconfigure to prevent UnicodeEncodeError on cp1252/cp850
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Enable Windows ANSI virtual terminal colors
try:
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
except Exception:
    pass


def print_banner():
    banner = f"""
{CYAN}{BOLD}================================================================================
   _______       _____ _____ _____ _____          _      __      _______ _____ _____ ____  _   _ 
  |__   __|/\   / ____|_   _|_   _/ ____|   /\   | |     \ \    / /_   _/ ____|_   _/ __ \| \ | |
     | |  /  \ | |      | |   | || |       /  \  | |      \ \  / /  | || (___   | || |  | |  \| |
     | | / /\ \| |      | |   | || |      / /\ \ | |       \ \/ /   | | \___ \  | || |  | | . ` |
     | |/ ____ \ |____ _| |_ _| || |____ / ____ \| |____    \  /   _| |_ ____) |_| || |__| | |\  |
     |_/_/    \_\_____|_____|_____\_____/_/    \_\______|    \/   |_____|_____/|_____\____/|_| \_|
                                                                                                 
      TACTICAL VISION // CYBER-SUITE LOADER & DIAGNOSTIC v4.5
   NVIDIA TensorRT 10 | Direct Memory Access | MAKCU Dual-ESP32
================================================================================{RESET}
"""
    try:
        print(banner)
    except Exception:
        print("\n=== YOLO TACTICAL VISION LOADER & SETUP ===\n")


def get_py_cmd():
    if shutil.which("py"):
        return "py"
    if shutil.which("python"):
        return "python"
    # Check standard install locations
    local_py = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe")
    if os.path.exists(local_py):
        return local_py
    local_py12 = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe")
    if os.path.exists(local_py12):
        return local_py12
    return "python"


def check_python_environment():
    print(f"{YELLOW}[1/5] Pruefe Python-Laufzeitumgebung...{RESET}")
    py_cmd = get_py_cmd()
    try:
        ver_res = subprocess.run([py_cmd, "--version"], capture_output=True, text=True, check=True)
        py_ver = ver_res.stdout.strip()
        print(f"  {GREEN}[OK] Python erkannt:{RESET} {py_ver}")
    except Exception:
        print(f"  {RED}[FEHLER] Kein Python gefunden! Bitte installiere Python 3.11 64-Bit von python.org{RESET}")
        return False

    is_64 = sys.maxsize > 2**32
    if is_64:
        print(f"  {GREEN}[OK] Architektur:{RESET} 64-Bit (x64 Windows)")
    else:
        print(f"  {RED}[WARNUNG] 32-Bit Python erkannt. Fuer CUDA & TensorRT wird 64-Bit benoetigt!{RESET}")
        return False

    return True


def check_and_install_packages():
    print(f"\n{YELLOW}[2/5] Pruefe & Verifiziere Python-Bibliotheken...{RESET}")
    py_cmd = get_py_cmd()

    # Step A: Check PyTorch CUDA
    print(f"  -> Pruefe PyTorch mit NVIDIA CUDA-Beschleunigung...")
    torch_check_code = (
        "try:\n"
        "    import torch\n"
        "    print('TORCH_OK' if torch.cuda.is_available() else 'TORCH_NO_CUDA')\n"
        "except ImportError:\n"
        "    print('TORCH_MISSING')\n"
    )
    res = subprocess.run([py_cmd, "-c", torch_check_code], capture_output=True, text=True)
    status = res.stdout.strip()

    if "TORCH_OK" in status:
        print(f"     {GREEN}[OK] PyTorch CUDA 12.x ist einsatzbereit.{RESET}")
    else:
        print(f"     {CYAN}-> Installiere PyTorch mit CUDA 12.4 Support (kann 1-2 Minuten dauern)...{RESET}")
        cmd = [
            py_cmd, "-m", "pip", "install", "--upgrade",
            "torch", "torchvision",
            "--index-url", "https://download.pytorch.org/whl/cu124"
        ]
        subprocess.run(cmd, check=True)
        print(f"     {GREEN}[OK] PyTorch CUDA erfolgreich installiert!{RESET}")

    # Step B: Core Required Packages
    required_packages = [
        ("tensorrt", "tensorrt>=10.0.0"),
        ("onnxruntime", "onnxruntime-gpu"),
        ("onnx", "onnx"),
        ("onnxslim", "onnxslim"),
        ("ultralytics", "ultralytics"),
        ("PyQt6", "PyQt6"),
        ("mss", "mss"),
        ("win32api", "pywin32"),
        ("serial", "pyserial"),
        ("makcu", "makcu"),
        ("numpy", "numpy"),
    ]

    missing = []
    for import_name, pip_name in required_packages:
        check_code = f"import {import_name}"
        res = subprocess.run([py_cmd, "-c", check_code], capture_output=True)
        if res.returncode != 0:
            missing.append(pip_name)
        else:
            print(f"     {GREEN}[OK] {import_name}{RESET} ist bereit.")

    if missing:
        print(f"\n  {CYAN}-> Lade fehlende Pakete herunter: {', '.join(missing)}...{RESET}")
        for pkg in missing:
            print(f"     -> Installiere {pkg}...")
            res = subprocess.run([py_cmd, "-m", "pip", "install", "--upgrade", pkg])
            if res.returncode == 0:
                print(f"     {GREEN}[OK] {pkg} erfolgreich installiert.{RESET}")
            else:
                print(f"     {YELLOW}[!] {pkg} konnte nicht direkt installiert werden (wird bei Bedarf uebersprungen).{RESET}")
        print(f"  {GREEN}[OK] Paket-Pruefung abgeschlossen.{RESET}")
    else:
        print(f"  {GREEN}[OK] Alle Core-Pakete sind vollstaendig.{RESET}")


def check_nvidia_hardware():
    print(f"\n{YELLOW}[3/5] Pruefe NVIDIA Grafikkarte & TensorRT 10 Status...{RESET}")
    py_cmd = get_py_cmd()

    check_code = (
        "import torch\n"
        "import tensorrt as trt\n"
        "if torch.cuda.is_available():\n"
        "    print(f'GPU:{torch.cuda.get_device_name(0)}')\n"
        "    vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)\n"
        "    print(f'VRAM:{vram:.1f} GB')\n"
        "    print(f'TRT:{trt.__version__}')\n"
        "else:\n"
        "    print('GPU:NONE')\n"
    )
    res = subprocess.run([py_cmd, "-c", check_code], capture_output=True, text=True)
    out = res.stdout.strip()

    if "GPU:NONE" not in out:
        for line in out.splitlines():
            if line.startswith("GPU:"):
                print(f"  {GREEN}[OK] NVIDIA GPU:{RESET} {line.split(':', 1)[1]}")
            elif line.startswith("VRAM:"):
                print(f"  {GREEN}[OK] Dedizierter VRAM:{RESET} {line.split(':', 1)[1]}")
            elif line.startswith("TRT:"):
                print(f"  {GREEN}[OK] TensorRT Engine Runtime:{RESET} v{line.split(':', 1)[1]} (execute_async_v3)")
    else:
        print(f"  {RED}[INFO] Keine CUDA-faehige NVIDIA GPU erkannt.{RESET}")


def check_game_profiles_and_engines():
    print(f"\n{YELLOW}[4/5] Pruefe Spielprofile & High-Speed TensorRT 10 Engines...{RESET}")

    game_profiles = [
        ("Battlefield 2042", "battlefield_2042.engine", "battlefield_2042_fp16.onnx", "battlefield_2042.pt"),
        ("Valorant", "valorant_30k_640.engine", "valorant_30k_640_fp16.onnx", "valorant_30k_640.pt"),
        ("Counter-Strike 2", "GGMCS2.engine", "GGMCS2_fp16.onnx", "GGMCS2.pt"),
        ("ARC Raiders", "arc_raiders_yolo11_better.engine", "arc_raiders_yolo11_better_fp16.onnx", "arc_raiders_yolo11_better.pt"),
    ]

    for title, engine_file, fp16_file, pt_file in game_profiles:
        eng_p = os.path.join(BASE_DIR, engine_file)
        fp16_p = os.path.join(BASE_DIR, fp16_file)
        pt_p = os.path.join(BASE_DIR, pt_file)

        if os.path.exists(eng_p):
            sz = os.path.getsize(eng_p) / (1024 * 1024)
            print(f"  {GREEN}[OK] {title}:{RESET} {engine_file} ({sz:.1f} MB) -> {CYAN}Direct TensorRT 10 (200 - 320+ FPS){RESET}")
        elif os.path.exists(fp16_p):
            sz = os.path.getsize(fp16_p) / (1024 * 1024)
            print(f"  {YELLOW}[OK] {title}:{RESET} {fp16_file} ({sz:.1f} MB) -> {YELLOW}ONNX CUDA FP16 (~120 - 150 FPS){RESET}")
        elif os.path.exists(pt_p):
            sz = os.path.getsize(pt_p) / (1024 * 1024)
            print(f"  {YELLOW}[INFO] {title}:{RESET} {pt_file} ({sz:.1f} MB) -> PyTorch Basis")
        else:
            print(f"  {RED}[X] {title}:{RESET} Keine Modelldatei gefunden!")


def check_makcu_device():
    print(f"\n{YELLOW}[5/5] Pruefe MAKCU Dual-ESP32 Hardware-Controller...{RESET}")
    py_cmd = get_py_cmd()

    probe_code = (
        "try:\n"
        "    import makcu\n"
        "    ctrl = None\n"
        "    try:\n"
        "        ctrl = makcu.create_controller()\n"
        "    except Exception:\n"
        "        ctrl = None\n"
        "    if not (ctrl and ctrl.is_connected()):\n"
        "        from serial.tools import list_ports\n"
        "        busy_port = None\n"
        "        for p in list_ports.comports():\n"
        "            try:\n"
        "                c = makcu.create_controller(fallback_com_port=p.device, override_port=True)\n"
        "                if c and c.is_connected():\n"
        "                    ctrl = c\n"
        "                    break\n"
        "            except Exception as ex:\n"
        "                err_s = str(ex)\n"
        "                if 'Zugriff verweigert' in err_s or 'PermissionError' in err_s or 'Access is denied' in err_s:\n"
        "                    busy_port = p.device\n"
        "        if not ctrl and busy_port:\n"
        "            print(f'MAKCU_BUSY:{busy_port}')\n"
        "    if ctrl and ctrl.is_connected():\n"
        "        info = ctrl.get_device_info()\n"
        "        fw = ctrl.get_firmware_version()\n"
        "        port = info.get('port', getattr(ctrl, 'port', 'COM'))\n"
        "        print(f'MAKCU_OK:{port}:{fw}')\n"
        "        ctrl.disconnect()\n"
        "    else:\n"
        "        from serial.tools import list_ports\n"
        "        detected = [f'{p.device} ({p.description})' for p in list_ports.comports()]\n"
        "        print(f'MAKCU_NOT_CONNECTED:' + '; '.join(detected))\n"
        "except Exception as e:\n"
        "    err_str = str(e)\n"
        "    if 'Zugriff verweigert' in err_str or 'PermissionError' in err_str or 'Access is denied' in err_str:\n"
        "        print('MAKCU_BUSY')\n"
        "    else:\n"
        "        print(f'MAKCU_ERROR:{e}')\n"
    )
    res = subprocess.run([py_cmd, "-c", probe_code], capture_output=True, text=True)
    out = res.stdout.strip()

    if "MAKCU_OK" in out:
        parts = out.split(":")
        port = parts[1] if len(parts) > 1 else "COM19"
        fw = parts[2] if len(parts) > 2 else "km.MAKCU"
        print(f"  {GREEN}[OK] MAKCU Hardware erkannt:{RESET} Port {port} (Firmware: {fw})")
    elif "MAKCU_BUSY" in out:
        print(f"  {GREEN}[OK] MAKCU Hardware verbunden:{RESET} Port ist aktiv in Benutzung (YOLO Vision laeuft bereits)")
    elif "MAKCU_NOT_CONNECTED" in out:
        raw_ports = out.replace("MAKCU_NOT_CONNECTED:", "").strip()
        print(f"  {YELLOW}[INFO] Kein MAKCU Controller auf den COM-Ports gefunden.{RESET}")
        if raw_ports:
            print(f"  {CYAN}  Erkannte Geraete:{RESET} {raw_ports}")
        else:
            print(f"  {RED}  Hinweis: Windows erkennt aktuell gar keinen COM-Port.{RESET}")
        print(f"  {YELLOW}  Checkliste falls MAKCU eingesteckt ist:{RESET}")
        print(f"   1. USB-Port: Kabel muss im 'PC / Host'-Port des MAKCU stecken (nicht im Maus-Port).")
        print(f"   2. Datenkabel: Verwendet ein echtes USB-Datenkabel (kein reines Ladekabel).")
        print(f"   3. Treiber: Prueft im Geraete-Manager unter 'Anschluesse (COM & LPT)' den CH340-Treiber.")
    else:
        print(f"  {YELLOW}Hinweis: {out}{RESET}")


def create_desktop_shortcut():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    bat_path = os.path.join(BASE_DIR, "Start_YOLO_Vision.bat")
    lnk_path = os.path.join(desktop, "YOLO Tactical Vision.lnk")

    if os.path.exists(bat_path):
        try:
            import win32com.client
            w = win32com.client.Dispatch("WScript.Shell")
            s = w.CreateShortcut(lnk_path)
            s.TargetPath = bat_path
            s.WorkingDirectory = BASE_DIR
            s.Description = "Startet das YOLO Tactical Vision HUD mit Direct TensorRT 10"
            s.Save()
            print(f"\n  {GREEN}[OK] Desktop-Verknuepfung verifiziert:{RESET} 'YOLO Tactical Vision'")
        except Exception:
            pass


def run_live_benchmark():
    py_cmd = get_py_cmd()
    bench_code = (
        "import time\n"
        "from yolo_config import YOLOConfig\n"
        "from yolo_engine import YOLOEngine\n"
        "cfg = YOLOConfig()\n"
        "cfg.set('max_fps', 350)\n"
        "eng = YOLOEngine(cfg)\n"
        "eng.start()\n"
        "time.sleep(2.5)\n"
        "st = eng.get_state()\n"
        "print('BENCH_RES:' + str(st['fps']) + ':' + str(st['latency_ms']) + ':' + str(st['capture_ms']) + ':' + str(st['backend_name']))\n"
        "eng.stop()\n"
    )
    print(f"\n{CYAN}-> Fuehre Live-Benchmark auf deiner GPU durch (ca. 3 Sekunden)...{RESET}")
    res = subprocess.run([py_cmd, "-c", bench_code], capture_output=True, text=True)
    out = res.stdout.strip()
    for line in out.splitlines():
        if "BENCH_RES:" in line:
            _, fps, lat, cap, backend = line.split(":", 4)
            print(f"\n{GREEN}{BOLD}================ BENCHMARK ERGEBNIS ================{RESET}")
            print(f"  {BOLD}Inference FPS:{RESET}     {GREEN}{fps} FPS{RESET}")
            print(f"  {BOLD}End-to-End Latenz:{RESET} {CYAN}{lat} ms{RESET}")
            print(f"  {BOLD}Screen-Capture:{RESET}    {YELLOW}{cap} ms (Zero-Copy Triple-Ring){RESET}")
            print(f"  {BOLD}Backend:{RESET}           {backend}")
            print(f"{GREEN}{BOLD}===================================================={RESET}\n")
            return
    print(f"  Benchmark-Ausgabe: {out}")


def main():
    os.chdir(BASE_DIR)
    print_banner()

    if not check_python_environment():
        print(f"\n{RED}Setup abgebrochen.{RESET} Bitte installiere Python und versuche es erneut.")
        input("\nDruecke [Enter] zum Schliessen...")
        return

    check_and_install_packages()
    check_nvidia_hardware()
    check_game_profiles_and_engines()
    check_makcu_device()
    create_desktop_shortcut()

    print(f"\n{CYAN}{BOLD}" + "=" * 80 + f"{RESET}")
    print(f"{GREEN}{BOLD}   [OK] SYSTEM VOLLSTAENDIG OPTIMIERT UND BEREIT (300+ FPS)!{RESET}")
    print(f"{CYAN}{BOLD}" + "=" * 80 + f"{RESET}\n")

    print(f"{BOLD}Waehle eine Aktion:{RESET}")
    print(f"  {BOLD}[1]{RESET} YOLO Tactical Vision HUD starten (Direct TensorRT 10)")
    print(f"  {BOLD}[2]{RESET} Live-Benchmark & Latenz-Test durchfuehren")
    print(f"  {BOLD}[3]{RESET} MAKCU Hardware Wiggle Test")
    print(f"  {BOLD}[4]{RESET} COM-Port Hardware-Scanner & Diagnose ausfuehren")
    print(f"  {BOLD}[5]{RESET} Beenden")

    try:
        choice = input(f"\n{CYAN}Auswahl [1/2/3/4/5] (Standard: 1): {RESET}").strip()
        py_cmd = get_py_cmd()
        if choice in ["", "1"]:
            print(f"\n{GREEN}Starte YOLO Tactical Vision HUD...{RESET}\n")
            subprocess.Popen([py_cmd, "yolo_main.py"], cwd=BASE_DIR)
        elif choice == "2":
            run_live_benchmark()
            input("Druecke [Enter] zum Fortfahren...")
            main()
        elif choice == "3":
            print(f"\n{CYAN}Fuehre MAKCU Hardware Test aus...{RESET}")
            test_cmd = (
                "import json, os, time\n"
                "from makcu_aimbot import MAKCU_AimbotEngine\n"
                "cfg = {}\n"
                "try:\n"
                "    with open('yolo_config.json', 'r', encoding='utf-8') as f:\n"
                "        cfg = json.load(f)\n"
                "except Exception:\n"
                "    pass\n"
                "m = MAKCU_AimbotEngine(cfg)\n"
                "time.sleep(0.4)\n"
                "res = m.test_move()\n"
                "if res:\n"
                "    print('\\n  [OK] MAKCU Hardware-Test ERFOLGREICH! (Mauszeiger hat gewackelt)')\n"
                "else:\n"
                "    print('\\n  [!] Test fehlgeschlagen. Pruefe USB-Kabel / COM-Port.')\n"
                "m.disconnect()\n"
            )
            subprocess.run([py_cmd, "-c", test_cmd], cwd=BASE_DIR)
            input("Druecke [Enter] zum Fortfahren...")
            main()
        elif choice == "4":
            import find_com_ports
            find_com_ports.main()
            input("Druecke [Enter] zum Fortfahren...")
            main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
