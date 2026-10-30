"""
MAKCU & COM-Port Hardware Diagnostic & Auto-Configuration Utility
Scans all serial ports, inspects hardware IDs, checks device drivers, and verifies MAKCU connectivity.
"""

import sys
import os
import json
import time

# Ensure UTF-8 console output without crashes on German Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Enable Windows VT100 colors if possible
if os.name == "nt":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h_out = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(h_out, ctypes.byref(mode)):
            kernel32.SetConsoleMode(h_out, mode.value | 0x0004)
    except Exception:
        pass


def print_banner():
    print(f"{CYAN}{BOLD}" + "=" * 78 + f"{RESET}")
    print(f"{CYAN}{BOLD}   MAKCU // COM-PORT HARDWARE SCANNER & DIAGNOSE-TOOL{RESET}")
    print(f"{CYAN}{BOLD}   Automatische Erkennung fuer USB-Ports, Hardware-IDs und Geraetetreiber{RESET}")
    print(f"{CYAN}{BOLD}" + "=" * 78 + f"{RESET}\n")


def scan_com_ports():
    print(f"{YELLOW}[1/3] Scanne aktive Windows COM-Ports (serial.tools.list_ports)...{RESET}")
    
    ports_found = []
    try:
        import serial.tools.list_ports
        com_list = list(serial.tools.list_ports.comports())
    except ImportError:
        print(f"  {RED}[FEHLER] 'pyserial' ist nicht installiert.{RESET}")
        return []

    if not com_list:
        print(f"  {YELLOW}[HINWEIS] Keine aktiven COM-Ports von Windows registriert.{RESET}")
        return []

    print(f"  {GREEN}[OK] {len(com_list)} aktive(r) COM-Port(s) gefunden:{RESET}\n")
    for idx, p in enumerate(com_list, 1):
        hwid_str = p.hwid if p.hwid else "Unbekannt"
        desc_str = p.description if p.description else "Unbekannt"
        
        # Check if known MAKCU / CH340 / ESP32 HWID
        is_known_chip = False
        chip_label = ""
        hw_upper = hwid_str.upper()
        if "1A86:55D3" in hw_upper:
            is_known_chip = True
            chip_label = "CH9329 / MAKCU Original"
        elif "1A86:7523" in hw_upper or "1A86:5523" in hw_upper:
            is_known_chip = True
            chip_label = "WCH CH340 / CH341"
        elif "303A:1001" in hw_upper or "303A:0002" in hw_upper:
            is_known_chip = True
            chip_label = "Espressif ESP32-S3 USB"
        elif "10C4:EA60" in hw_upper:
            is_known_chip = True
            chip_label = "Silicon Labs CP210x"
        elif "MAKCU" in hw_upper or "MAKCU" in desc_str.upper():
            is_known_chip = True
            chip_label = "MAKCU Geraet"

        chip_tag = f" {GREEN}[Treffer: {chip_label}]{RESET}" if is_known_chip else ""

        print(f"  {BOLD}Port #{idx}:{RESET} {CYAN}{BOLD}{p.device}{RESET}{chip_tag}")
        print(f"    Beschreibung: {desc_str}")
        print(f"    Hardware-ID:  {hwid_str}")
        print()

        ports_found.append({
            "device": p.device,
            "description": desc_str,
            "hwid": hwid_str,
            "is_known_chip": is_known_chip,
            "chip_label": chip_label
        })

    return ports_found


def probe_makcu_connection(ports):
    print(f"{YELLOW}[2/3] Teste Verbindungs-Handshake & MAKCU-Status...{RESET}")
    if not ports:
        print(f"  {YELLOW}Uebersprungen (keine COM-Ports vorhanden).{RESET}\n")
        return None

    try:
        import makcu
    except ImportError:
        print(f"  {RED}[FEHLER] 'makcu' Python-Bibliothek ist nicht installiert.{RESET}\n")
        return None

    successful_port = None

    for item in ports:
        port_name = item["device"]
        print(f"  -> Pruefe {CYAN}{port_name}{RESET}...", end=" ", flush=True)

        try:
            # Attempt connection with port override
            ctrl = makcu.create_controller(fallback_com_port=port_name, override_port=True)
            if ctrl and ctrl.is_connected():
                info = ctrl.get_device_info()
                fw = ctrl.get_firmware_version()
                print(f"{GREEN}[VERBUNDEN!]{RESET}")
                print(f"     Firmware: {CYAN}{fw}{RESET} | Status: Bereit fuer Hardware-Befehle")
                successful_port = port_name
                ctrl.disconnect()
            else:
                print(f"{YELLOW}[Keine Antwort]{RESET} (Geraet antwortet nicht auf MAKCU-Protokoll)")
        except Exception as e:
            err_msg = str(e)
            if any(term in err_msg for term in ["Zugriff verweigert", "PermissionError", "Access is denied"]):
                print(f"{GREEN}[AKTIV]{RESET} (Port wird aktuell von einem laufenden Prozess verwendet, z.B. YOLO Vision)")
                successful_port = port_name
            else:
                print(f"{YELLOW}[Nicht kompatibel / Fehler]{RESET} ({err_msg})")

    print()
    return successful_port


def scan_driver_issues():
    print(f"{YELLOW}[3/3] Pruefe Windows Geraete-Manager auf Treiber-Probleme...{RESET}")
    import subprocess
    ps_cmd = (
        "Get-CimInstance Win32_PnPEntity | "
        "Where-Object { $_.ConfigManagerErrorCode -ne 0 -and "
        "($_.HardwareID -match '1A86' -or $_.HardwareID -match '303A' -or $_.HardwareID -match '10C4' -or $_.Name -match 'USB' -or $_.Name -match 'Serial') } | "
        "Select-Object Name, DeviceID, ConfigManagerErrorCode, Status"
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
        output = res.stdout.strip()
        if output:
            print(f"  {RED}[WARNUNG] Folgende USB-Geraete haben Treiber-Probleme (Fehlercode ungleich 0):{RESET}\n")
            print(output)
            print(f"\n  {YELLOW}-> Empfehlung: Lade den offiziellen 'CH341SER.EXE' Treiber herunter und installiere ihn.{RESET}\n")
        else:
            print(f"  {GREEN}[OK] Keine fehlerhaften USB-Serial-Geraete im Geraete-Manager gefunden.{RESET}\n")
    except Exception:
        print(f"  {YELLOW}Status konnte nicht via PowerShell ermittelt werden.{RESET}\n")


def update_config_port(port_name):
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolo_config.json")
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        data["makcu_port"] = port_name
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"  {GREEN}[OK] Port '{port_name}' wurde dauerhaft in yolo_config.json gespeichert!{RESET}")
    except Exception as e:
        print(f"  {RED}[FEHLER] Konfiguration konnte nicht gespeichert werden: {e}{RESET}")


def main():
    print_banner()
    ports = scan_com_ports()
    connected_port = probe_makcu_connection(ports)
    scan_driver_issues()

    print(f"{CYAN}{BOLD}" + "=" * 78 + f"{RESET}")
    if connected_port:
        print(f"{GREEN}{BOLD}   ERGEBNIS: MAKCU Hardware gefunden auf Port: {connected_port}{RESET}")
        print(f"{CYAN}{BOLD}" + "=" * 78 + f"{RESET}\n")
        
        try:
            choice = input(f"Moechtest du {BOLD}'{connected_port}'{RESET} als Standard-Port in der Konfiguration speichern? [J/N] (Standard: J): ").strip().upper()
            if choice in ["", "J", "Y", "JA", "YES"]:
                update_config_port(connected_port)
        except Exception:
            pass
    elif ports:
        print(f"{YELLOW}{BOLD}   ERGEBNIS: COM-Ports sind vorhanden, aber kein MAKCU hat geantwortet.{RESET}")
        print(f"{CYAN}{BOLD}" + "=" * 78 + f"{RESET}\n")
        print(f"   Checkliste:")
        print(f"   1. Kabel muss im 'PC / Host'-Port des MAKCU stecken (nicht im 'Maus'-Port).")
        print(f"   2. Ein echtes Datenkabel verwenden (viele Ladekabel uebertragen keine Daten).")
    else:
        print(f"{RED}{BOLD}   ERGEBNIS: Windows erkennt aktuell gar keinen COM-Port.{RESET}")
        print(f"{CYAN}{BOLD}" + "=" * 78 + f"{RESET}\n")
        print(f"   Checkliste:")
        print(f"   1. Ist der MAKCU per USB eingesteckt und leuchten die LEDs?")
        print(f"   2. Falls Windows den Dongle nicht erkennt, fehlt meist der CH340-Treiber.")
        print(f"   3. Stecke den Dongle in einen anderen USB-Anschluss direkt am Mainboard (Rueckseite).")

    print()


if __name__ == "__main__":
    main()
