"""
ARC Raiders Sound Overlay - Main Application (v3.0)
Single-instance enforced transparent tactical HUD with multi-threat persistence.
"""

import sys
import os
import socket
import subprocess
import keyboard

_instance_lock = None

def enforce_single_instance():
    global _instance_lock
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 49234))
        _instance_lock = s
        return True
    except Exception:
        # Stop existing background instance and re-bind
        subprocess.run(
            ["powershell", "-Command", f"Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%main.py%'\" | Where-Object {{ $_.ProcessId -ne {os.getpid()} }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"],
            capture_output=True
        )
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', 49234))
            _instance_lock = s
            return True
        except Exception:
            return False
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QGuiApplication, QColor, QPixmap, QPainter

from config import Config
from audio_engine import AudioEngine
from overlay_window import SoundOverlayWindow
from settings_window import SettingsWindow

class HotkeyBridge(QObject):
    sig_toggle_overlay = pyqtSignal()
    sig_toggle_settings = pyqtSignal()

def create_tray_icon_pixmap():
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QColor(255, 140, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.setBrush(QColor(0, 229, 255))
    painter.drawEllipse(10, 10, 12, 12)
    painter.end()
    return pixmap

def main():
    enforce_single_instance()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = Config()
    audio = AudioEngine()

    # Pass config settings
    audio.gain = config.get("gain", 3.0)
    audio.noise_threshold = config.get("noise_threshold", 0.002)
    audio.hold_duration = config.get("hold_duration", 0.95)
    audio.stereo_boost = config.get("stereo_boost", 1.4)
    audio.start(device_index=config.get("device_index", None))

    screen = QGuiApplication.primaryScreen()
    screen_rect = screen.geometry()

    overlay = SoundOverlayWindow(audio, config)
    overlay.setGeometry(screen_rect)
    overlay.show()

    settings = SettingsWindow(audio, config, overlay)
    settings.show()

    bridge = HotkeyBridge()

    def do_toggle_overlay():
        if overlay.isVisible():
            overlay.hide()
        else:
            overlay.show()

    def do_toggle_settings():
        if settings.isVisible():
            settings.hide()
        else:
            settings.show()
            settings.activateWindow()

    bridge.sig_toggle_overlay.connect(do_toggle_overlay)
    bridge.sig_toggle_settings.connect(do_toggle_settings)

    hk_toggle = config.get("hotkey_toggle", "f9")
    hk_settings = config.get("hotkey_settings", "f10")

    try:
        keyboard.add_hotkey(hk_toggle, lambda: bridge.sig_toggle_overlay.emit())
        keyboard.add_hotkey(hk_settings, lambda: bridge.sig_toggle_settings.emit())
    except Exception as e:
        print(f"Failed to register global hotkeys: {e}")

    tray_icon = QSystemTrayIcon(QIcon(create_tray_icon_pixmap()), app)
    tray_menu = QMenu()

    action_settings = tray_menu.addAction("Einstellungen öffnen [F10]")
    action_settings.triggered.connect(do_toggle_settings)

    action_toggle_overlay = tray_menu.addAction("Overlay An/Aus [F9]")
    action_toggle_overlay.triggered.connect(do_toggle_overlay)

    tray_menu.addSeparator()
    action_quit = tray_menu.addAction("Beenden")
    action_quit.triggered.connect(app.quit)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.setToolTip("ARC Raiders Tactical Sound Radar v3.0")
    tray_icon.show()

    print("ARC Raiders Tactical Sound Radar v3.0 running!")
    print(f"Hotkeys: [{hk_toggle.upper()}] Toggle Overlay | [{hk_settings.upper()}] Settings")

    exit_code = app.exec()

    try:
        keyboard.unhook_all_hotkeys()
    except Exception:
        pass
    audio.stop()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
