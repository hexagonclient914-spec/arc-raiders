"""
ARC Raiders YOLO Tactical Vision HUD - Main Application Entrypoint
Ultra-low latency AI vision HUD with click-through overlay and dynamic controls.
Uses Native Win32 GetAsyncKeyState Hardware Polling so hotkeys (like 'C', 'F7', 'F8', Mouse4/5)
work 100% reliably inside fullscreen games without Administrator hook blocks.
"""

import sys
import os
import socket
import subprocess
import ctypes
import threading
import time
import winsound
import traceback


def global_exception_handler(exc_type, exc_value, exc_traceback):
    try:
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- UNCAUGHT EXCEPTION AT {time.ctime()} ---\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    except Exception:
        pass
    traceback.print_exception(exc_type, exc_value, exc_traceback)


sys.excepthook = global_exception_handler
if hasattr(threading, "excepthook"):
    threading.excepthook = lambda args: global_exception_handler(args.exc_type, args.exc_value, args.exc_traceback)

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QLineEdit
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QIcon, QGuiApplication, QColor, QPixmap, QPainter

from yolo_config import YOLOConfig
from yolo_engine import YOLOEngine
from yolo_overlay import YOLOOverlayWindow
from aura_gui import AuraEliteHUDWindow

_instance_lock = None

# =====================================================================
# NATIVE WIN32 VIRTUAL-KEY (VK) TABLE FOR HARDWARE POLLING
# =====================================================================
VK_CODE_MAP = {
    # Mouse buttons
    "lmb": 0x01,
    "rmb": 0x02,
    "mmb": 0x04,
    "mouse3": 0x04,
    "xbutton1": 0x05,
    "mouse4": 0x05,
    "xbutton2": 0x06,
    "mouse5": 0x06,

    # Modifiers & special keys
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "lshift": 0xA0,
    "rshift": 0xA1,
    "ctrl": 0x11,
    "lctrl": 0xA2,
    "rctrl": 0xA3,
    "alt": 0x12,
    "lalt": 0xA4,
    "ralt": 0xA5,
    "pause": 0x13,
    "capslock": 0x14,
    "caps lock": 0x14,
    "caps": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "page up": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "page down": 0x22,
    "pgdn": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "ins": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,

    # Function keys F1 - F12
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,

    # Numpad
    "num0": 0x60,
    "num1": 0x61,
    "num2": 0x62,
    "num3": 0x63,
    "num4": 0x64,
    "num5": 0x65,
    "num6": 0x66,
    "num7": 0x67,
    "num8": 0x68,
    "num9": 0x69,
}

# Populate letters a-z (0x41 - 0x5A) and digits 0-9 (0x30 - 0x39)
for _ch_code in range(ord('a'), ord('z') + 1):
    VK_CODE_MAP[chr(_ch_code)] = 0x41 + (_ch_code - ord('a'))
for _dg_code in range(ord('0'), ord('9') + 1):
    VK_CODE_MAP[chr(_dg_code)] = 0x30 + (_dg_code - ord('0'))


def resolve_vk_code(key_name: str) -> int:
    """Resolve a human-readable key string (e.g. 'c', 'f7', 'xbutton1') to Win32 VK code."""
    if not key_name:
        return 0
    k = str(key_name).strip().lower()
    if k in VK_CODE_MAP:
        return VK_CODE_MAP[k]
    if len(k) == 1:
        return ord(k.upper())
    return 0


def play_feedback_beep(enabled_state: bool, config: YOLOConfig):
    """Play a crisp non-blocking acoustic tone so user hears toggle state even in No-Overlay mode."""
    if not bool(config.get("hotkey_sound", True)):
        return

    def _beep_worker():
        try:
            if enabled_state:
                winsound.Beep(880, 55)
                winsound.Beep(1180, 65)
            else:
                winsound.Beep(520, 85)
        except Exception:
            pass

    threading.Thread(target=_beep_worker, daemon=True).start()


def enforce_single_instance():
    """Ensure only one instance of YOLO Vision runs at a time."""
    global _instance_lock
    port = 49235
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', port))
        _instance_lock = s
        return True
    except Exception:
        # Kill previous background instance
        subprocess.run(
            ["powershell", "-Command", f"Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%yolo_main.py%'\" | Where-Object {{ $_.ProcessId -ne {os.getpid()} }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"],
            capture_output=True
        )
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', port))
            _instance_lock = s
            return True
        except Exception:
            return False


class HotkeyBridge(QObject):
    sig_toggle_engine = pyqtSignal()
    sig_toggle_overlay = pyqtSignal()
    sig_toggle_settings = pyqtSignal()


def create_tray_icon_pixmap():
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # Tactical cyan ring with red crosshair dot
    painter.setPen(QColor(0, 255, 204))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(3, 3, 26, 26)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 51, 85))
    painter.drawEllipse(11, 11, 10, 10)
    painter.end()
    return pixmap


def main():
    # Attach main GUI thread to interactive user desktop
    try:
        user32 = ctypes.windll.user32
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception:
        pass

    enforce_single_instance()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = YOLOConfig()
    engine = YOLOEngine(config)
    engine.start()

    # Screen setup
    screen = QGuiApplication.primaryScreen()
    screen_rect = screen.geometry()

    overlay = YOLOOverlayWindow(engine, config)
    overlay.setGeometry(screen_rect)
    if not bool(config.get("headless_mode", False)):
        overlay.show()
        overlay.raise_()

    settings = AuraEliteHUDWindow(engine, config, overlay)
    # Position settings window nicely centered on screen
    settings.move(
        screen_rect.x() + (screen_rect.width() - settings.width()) // 2,
        screen_rect.y() + (screen_rect.height() - settings.height()) // 2
    )
    settings.show()
    settings.raise_()
    settings.activateWindow()

    # Thread-safe Hotkey signals
    bridge = HotkeyBridge()

    def do_toggle_engine():
        new_state = not bool(config.get("enabled", True))
        config.set("enabled", new_state)
        config.set("makcu_enabled", new_state)
        play_feedback_beep(new_state, config)
        if hasattr(settings, "_sync_engine_power_ui"):
            settings._sync_engine_power_ui()
        k_eng = str(config.get("hotkey_toggle_engine", "c")).upper()
        if getattr(settings, "status_bar_lbl", None) is not None:
            if new_state:
                settings.status_bar_lbl.setText(f"🟢 System & Aim AKTIVIERT via Keybind [{k_eng}]")
            else:
                settings.status_bar_lbl.setText(f"🔴 System & Aim PAUSIERT via Keybind [{k_eng}]")
        if overlay.isVisible():
            overlay.update()

    def do_toggle_overlay():
        if overlay.isVisible():
            config.set("headless_mode", True)
            overlay.hide()
            play_feedback_beep(False, config)
        else:
            config.set("headless_mode", False)
            overlay.show()
            play_feedback_beep(True, config)
        if hasattr(settings, "_sync_headless_ui"):
            settings._sync_headless_ui()

    def do_toggle_settings():
        if settings.isVisible():
            settings.hide()
        else:
            settings.show()
            settings.raise_()
            settings.activateWindow()

    bridge.sig_toggle_engine.connect(do_toggle_engine)
    bridge.sig_toggle_overlay.connect(do_toggle_overlay)
    bridge.sig_toggle_settings.connect(do_toggle_settings)

    # =====================================================================
    # NATIVE WIN32 HARDWARE KEY POLLER (Works in all fullscreen games!)
    # =====================================================================
    user32_api = ctypes.windll.user32
    key_prev_down = {"engine": False, "overlay": False, "settings": False}

    def poll_win32_hotkeys():
        # Pause global hotkey triggers while user is recording a new keybind in GUI
        if getattr(settings, "_is_recording_keybind", False):
            return

        # Prevent single-letter hotkeys (like 'C') from firing while typing in the search bar
        focus_w = QApplication.focusWidget()
        is_typing_text = isinstance(focus_w, QLineEdit) and settings.isActiveWindow()

        hk_map = [
            ("engine", config.get("hotkey_toggle_engine", "c"), bridge.sig_toggle_engine),
            ("overlay", config.get("hotkey_toggle_overlay", "f7"), bridge.sig_toggle_overlay),
            ("settings", config.get("hotkey_toggle_settings", "f8"), bridge.sig_toggle_settings),
        ]

        for slot_name, key_str, sig in hk_map:
            vk = resolve_vk_code(key_str)
            if vk == 0:
                key_prev_down[slot_name] = False
                continue

            # Skip alphanumeric keys if typing in search box
            if is_typing_text and (0x30 <= vk <= 0x5A):
                key_prev_down[slot_name] = False
                continue

            is_down = (user32_api.GetAsyncKeyState(vk) & 0x8000) != 0
            if is_down and not key_prev_down[slot_name]:
                sig.emit()
            key_prev_down[slot_name] = is_down

    hotkey_timer = QTimer(app)
    hotkey_timer.timeout.connect(poll_win32_hotkeys)
    hotkey_timer.start(18)  # ~55 Hz hardware key state polling with zero CPU overhead

    def refresh_hotkeys():
        # Reset edge states after rebinding
        for k in key_prev_down:
            key_prev_down[k] = True

    settings.rebind_hotkeys_callback = refresh_hotkeys

    # System Tray
    tray_icon = QSystemTrayIcon(QIcon(create_tray_icon_pixmap()), app)
    tray_menu = QMenu()

    action_toggle_engine = tray_menu.addAction("System An/Aus (C)")
    action_toggle_engine.triggered.connect(do_toggle_engine)

    action_toggle_overlay = tray_menu.addAction("Toggle Overlay (F7)")
    action_toggle_overlay.triggered.connect(do_toggle_overlay)

    action_toggle_settings = tray_menu.addAction("Settings Window (F8)")
    action_toggle_settings.triggered.connect(do_toggle_settings)

    tray_menu.addSeparator()

    def cleanup_and_exit():
        hotkey_timer.stop()
        engine.stop()
        app.quit()

    action_quit = tray_menu.addAction("Exit YOLO Vision")
    action_quit.triggered.connect(cleanup_and_exit)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.setToolTip("ARC Raiders - YOLO Tactical Vision HUD")
    tray_icon.show()

    ret = app.exec()
    engine.stop()
    sys.exit(ret)


if __name__ == "__main__":
    main()
