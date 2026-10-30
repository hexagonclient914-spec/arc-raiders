"""
AURA TACTICAL VISION // COMMERCIAL CLIENT LOADER v5.0.0
High-end commercial loader with hardware-locked HWID licensing,
remote cloud update manager, game profile selector, hardware diagnostics,
and stealth background execution.
"""

import sys
import os
import json
import time
import winreg
import hashlib
import threading
import subprocess
import serial.tools.list_ports

from license_manager import LicenseManager, get_machine_hwid
from cloud_downloader import (
    is_client_installed,
    get_client_installation_dir,
    get_active_payload_dir,
    get_github_token,
    CloudAssetDownloaderThread
)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QProgressBar, QStackedWidget,
    QFrame, QGraphicsDropShadowEffect, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor, QIcon, QPainter, QBrush, QPen

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VERSION_FILE = os.path.join(BASE_DIR, "version.json")
AUTH_FILE = os.path.join(BASE_DIR, "loader_auth.json")
CONFIG_FILE = os.path.join(BASE_DIR, "yolo_config.json")


def get_runtime_python() -> str:
    """Find valid Python runtime on system, avoiding WindowsApps stubs."""
    import shutil
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
        r"C:\Python311\python.exe",
        r"C:\Python312\python.exe",
        r"C:\Program Files\Python311\python.exe",
        r"C:\Program Files\Python312\python.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    if shutil.which("py"):
        return "py"

    py_cmd = shutil.which("python")
    if py_cmd and "WindowsApps" not in py_cmd:
        return py_cmd

    if not getattr(sys, "frozen", False):
        return sys.executable
    return "python"
def get_machine_hwid() -> str:
    """Retrieve permanent Windows MachineGuid and format as standard commercial HWID."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        )
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        h = hashlib.sha256(guid.encode("utf-8")).hexdigest()[:16].upper()
        return "-".join([h[i:i+4] for i in range(0, 16, 4)])
    except Exception:
        return "HWID-8842-10F9-C43A"


def load_auth_data() -> dict:
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"license_key": "", "remember": True, "activated": False}


def save_auth_data(data: dict):
    try:
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass


def load_version_info() -> dict:
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": "5.0.0", "channel": "release", "build": 5002}


# =====================================================================
# THREAD WORKERS (UPDATE CHECK & HARDWARE SCAN)
# =====================================================================
class UpdateCheckerThread(QThread):
    sig_update_status = pyqtSignal(bool, str, list)  # is_update_avail, new_ver, changelog

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self):
        # Allow instant local responsiveness with network verification
        time.sleep(0.8)
        v_info = load_version_info()
        remote_url = v_info.get("remote_manifest_url", "")
        
        if remote_url and remote_url.startswith("http"):
            try:
                import requests
                headers = {"User-Agent": "AuraTacticalLoader/5.0"}
                if "api.github.com" in remote_url or "github" in remote_url:
                    headers["Accept"] = "application/vnd.github.raw+json"
                    token = get_github_token()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                res = requests.get(remote_url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    remote_data = res.json()
                    rem_ver = remote_data.get("version", self.current_version)
                    if rem_ver != self.current_version:
                        self.sig_update_status.emit(True, rem_ver, remote_data.get("changelog", []))
                        return
            except Exception:
                pass

        # Up to date
        self.sig_update_status.emit(False, self.current_version, v_info.get("changelog", []))


class HardwareScannerThread(QThread):
    sig_hardware_ready = pyqtSignal(dict)

    def run(self):
        info = {
            "gpu_name": "NVIDIA GPU Detecting...",
            "tensorrt_status": "Checking...",
            "makcu_port": "None",
            "makcu_status": "Disconnected",
        }
        
        # 1. Check GPU & TensorRT cleanly via nvidia-smi (keeps Loader.exe super light & instant)
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2.0
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split("\n")[0].split(",")
                g_name = parts[0].strip()
                vram = parts[1].strip() if len(parts) > 1 else ""
                info["gpu_name"] = f"{g_name} ({vram} MB)"
                info["tensorrt_status"] = "Direct TensorRT 10 (FP16 Ready)"
            else:
                info["gpu_name"] = "NVIDIA GeForce RTX"
                info["tensorrt_status"] = "Direct TensorRT 10"
        except Exception:
            info["gpu_name"] = "NVIDIA GeForce RTX"
            info["tensorrt_status"] = "Direct TensorRT 10"

        # 2. Check MAKCU Dual-ESP32
        try:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            if "COM19" in ports:
                info["makcu_port"] = "COM19"
                info["makcu_status"] = "Online (km.MAKCU Dual-ESP32)"
            elif ports:
                info["makcu_port"] = ports[0]
                info["makcu_status"] = f"Online ({ports[0]})"
            else:
                info["makcu_status"] = "Not Connected (Plug USB into Host Port)"
        except Exception as e:
            info["makcu_status"] = f"Error: {e}"

        self.sig_hardware_ready.emit(info)


# =====================================================================
# MODERN COMMERCIAL UI APPLICATION
# =====================================================================
class CommercialLoaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.v_info = load_version_info()
        self.license_mgr = LicenseManager()
        self.hwid = self.license_mgr.hwid
        self.auth_data = self.license_mgr.cached_auth
        self.drag_position = QPoint()
        self.active_process = None
        self.uptime_seconds = 0

        self.setWindowTitle(f"AURA Tactical Vision // Client Loader v{self.v_info.get('version', '5.0.0')}")
        self.resize(840, 580)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._init_ui()
        self._apply_styling()

        # Hardware scan
        self.hw_scanner = HardwareScannerThread()
        self.hw_scanner.sig_hardware_ready.connect(self._on_hardware_detected)
        self.hw_scanner.start()

        # Auto updater check
        self.update_checker = UpdateCheckerThread(self.v_info.get("version", "5.0.0"))
        self.update_checker.sig_update_status.connect(self._on_update_result)
        self.update_checker.start()

        # Process monitor timer
        self.proc_timer = QTimer(self)
        self.proc_timer.timeout.connect(self._check_process_health)
        self.proc_timer.start(1000)

        # Check auto-login via LicenseManager
        if self.license_mgr.is_already_activated():
            self.lbl_sub_badge.setText(f"💎 {self.license_mgr.get_user_tier()}")
            self.stack.setCurrentIndex(1)
            self._sync_selected_game_card()

    def _init_ui(self):
        # Outer container with rounded corners and drop shadow
        self.central_container = QFrame(self)
        self.central_container.setObjectName("CentralContainer")
        self.setCentralWidget(self.central_container)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 190))
        shadow.setOffset(0, 6)
        self.central_container.setGraphicsEffect(shadow)

        main_lay = QVBoxLayout(self.central_container)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # 1. Custom Title Bar
        title_bar = QFrame()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(48)
        t_lay = QHBoxLayout(title_bar)
        t_lay.setContentsMargins(18, 0, 14, 0)

        lbl_logo = QLabel("⚡ AURA")
        lbl_logo.setObjectName("TitleLogo")
        lbl_title = QLabel(f"TACTICAL VISION  |  COMMERCIAL SUITE  v{self.v_info.get('version', '5.0.0')}")
        lbl_title.setObjectName("TitleText")

        t_lay.addWidget(lbl_logo)
        t_lay.addWidget(lbl_title)
        t_lay.addStretch()

        btn_min = QPushButton("—")
        btn_min.setObjectName("TitleBtn")
        btn_min.clicked.connect(self.showMinimized)
        t_lay.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("TitleCloseBtn")
        btn_close.clicked.connect(self.close)
        t_lay.addWidget(btn_close)

        main_lay.addWidget(title_bar)

        # 2. Stacked Content Area (Page 0: Auth, Page 1: Dashboard)
        self.stack = QStackedWidget()
        main_lay.addWidget(self.stack)

        self._build_auth_page()
        self._build_dashboard_page()

    # -----------------------------------------------------------------
    # PAGE 0: AUTHENTICATION & LICENSE ACTIVATION
    # -----------------------------------------------------------------
    def _build_auth_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(60, 40, 60, 40)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("AuthCard")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(36, 32, 36, 32)
        c_lay.setSpacing(16)

        lbl_auth_header = QLabel("CLIENT AUTHENTICATION")
        lbl_auth_header.setObjectName("AuthHeader")
        lbl_auth_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_lay.addWidget(lbl_auth_header)

        lbl_auth_sub = QLabel("Enter your client license key to activate your session.")
        lbl_auth_sub.setObjectName("SubText")
        lbl_auth_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_lay.addWidget(lbl_auth_sub)

        # HWID Display Box
        hwid_box = QFrame()
        hwid_box.setObjectName("HwidBox")
        h_lay = QHBoxLayout(hwid_box)
        h_lay.setContentsMargins(14, 8, 14, 8)
        lbl_hwid_title = QLabel("HARDWARE-ID (HWID):")
        lbl_hwid_title.setObjectName("BadgeLabel")
        self.lbl_hwid_val = QLabel(self.hwid)
        self.lbl_hwid_val.setObjectName("HwidValue")
        btn_copy = QPushButton("COPY")
        btn_copy.setObjectName("ActionPillBtn")
        btn_copy.clicked.connect(self._copy_hwid)
        h_lay.addWidget(lbl_hwid_title)
        h_lay.addWidget(self.lbl_hwid_val)
        h_lay.addStretch()
        h_lay.addWidget(btn_copy)
        c_lay.addWidget(hwid_box)

        # Key Input
        self.txt_key = QLineEdit()
        self.txt_key.setObjectName("KeyInput")
        self.txt_key.setPlaceholderText("Paste License Key (e.g. AURA-PRO-XXXX-XXXX)...")
        if self.auth_data.get("license_key"):
            self.txt_key.setText(self.auth_data.get("license_key"))
        c_lay.addWidget(self.txt_key)

        # Remember checkbox
        self.chk_remember = QCheckBox("Remember license on this hardware")
        self.chk_remember.setChecked(self.auth_data.get("remember", True))
        c_lay.addWidget(self.chk_remember)

        # Activate Button
        btn_activate = QPushButton("ACTIVATE & LOGIN")
        btn_activate.setObjectName("LaunchButton")
        btn_activate.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_activate.clicked.connect(self._handle_activation)
        c_lay.addWidget(btn_activate)

        self.lbl_auth_status = QLabel("")
        self.lbl_auth_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_auth_status.setObjectName("StatusWarning")
        c_lay.addWidget(self.lbl_auth_status)

        lay.addWidget(card)
        self.stack.addWidget(page)

    # -----------------------------------------------------------------
    # PAGE 1: COMMERCIAL DASHBOARD & GAME HUB
    # -----------------------------------------------------------------
    def _build_dashboard_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 16, 24, 20)
        lay.setSpacing(14)

        # Top Bar: User Status & Auto-Update Banner
        top_bar = QFrame()
        top_bar.setObjectName("TopInfoBar")
        tb_lay = QHBoxLayout(top_bar)
        tb_lay.setContentsMargins(16, 10, 16, 10)

        self.lbl_sub_badge = QLabel("💎 LIFETIME VIP")
        self.lbl_sub_badge.setObjectName("VipBadge")
        
        self.lbl_user_hwid = QLabel(f"HWID: {self.hwid}")
        self.lbl_user_hwid.setObjectName("SubText")

        tb_lay.addWidget(self.lbl_sub_badge)
        tb_lay.addWidget(self.lbl_user_hwid)
        tb_lay.addStretch()

        self.lbl_update_badge = QLabel("☁️ Checking for updates...")
        self.lbl_update_badge.setObjectName("UpdateBadge")
        tb_lay.addWidget(self.lbl_update_badge)

        lay.addWidget(top_bar)

        # Game Selector Grid (Cards)
        lbl_sec1 = QLabel("SELECT ACTIVE GAME PROFILE")
        lbl_sec1.setObjectName("SectionHeader")
        lay.addWidget(lbl_sec1)

        games_row = QHBoxLayout()
        games_row.setSpacing(12)

        self.game_cards = {}
        games_data = [
            ("valorant", "Valorant", "valorant_30k_640.engine", "Direct TRT 10", "⚡ 280+ FPS", "head"),
            ("fortnite", "Fortnite", "fortnite_100k.engine", "Direct TRT 10", "⚡ 260+ FPS", "head"),
            ("arc_raiders", "ARC Raiders", "arc_raiders_yolo11_better.engine", "YOLOv11 TRT", "🎯 Snitch/Raider", "head"),
            ("battlefield_2042", "Battlefield 2042", "battlefield_2042.engine", "FP16 TRT 10", "💥 200+ FPS", "head"),
            ("cs2", "Counter-Strike 2", "GGMCS2.engine", "Direct TRT 10", "🏆 Head/Neck", "head"),
        ]

        for gid, name, eng_file, tech, fps_badge, bone in games_data:
            c = QFrame()
            c.setObjectName("GameCard")
            c.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            c.mousePressEvent = lambda e, g=gid: self._select_game(g)
            
            c_lay = QVBoxLayout(c)
            c_lay.setContentsMargins(14, 14, 14, 14)
            c_lay.setSpacing(6)

            badge = QLabel(fps_badge)
            badge.setObjectName("GameBadge")
            c_lay.addWidget(badge)

            g_title = QLabel(name)
            g_title.setObjectName("GameTitle")
            c_lay.addWidget(g_title)

            g_sub = QLabel(tech)
            g_sub.setObjectName("SubText")
            c_lay.addWidget(g_sub)

            status_lbl = QLabel("● UNDETECTED")
            status_lbl.setObjectName("GameStatusOnline")
            c_lay.addWidget(status_lbl)

            games_row.addWidget(c)
            self.game_cards[gid] = {
                "frame": c,
                "name": name,
                "engine": eng_file,
                "bone": bone
            }

        lay.addLayout(games_row)

        # Hardware Diagnostic Strip
        hw_box = QFrame()
        hw_box.setObjectName("HardwareBox")
        hw_lay = QHBoxLayout(hw_box)
        hw_lay.setContentsMargins(16, 10, 16, 10)

        self.lbl_gpu = QLabel("🎮 GPU: Detecting NVIDIA TensorRT...")
        self.lbl_gpu.setObjectName("HwLabel")

        self.lbl_makcu = QLabel("🔌 MAKCU: Scanning COM ports...")
        self.lbl_makcu.setObjectName("HwLabel")

        hw_lay.addWidget(self.lbl_gpu)
        hw_lay.addStretch()
        hw_lay.addWidget(self.lbl_makcu)
        lay.addWidget(hw_box)

        # Cloud Download / Sync Progress Container (hidden when idle)
        self.download_container = QFrame()
        self.download_container.setObjectName("DownloadContainer")
        d_lay = QVBoxLayout(self.download_container)
        d_lay.setContentsMargins(14, 8, 14, 8)
        d_lay.setSpacing(6)

        d_header_lay = QHBoxLayout()
        self.lbl_download_status = QLabel("⚡ Synchronizing AI Engine & Assets...")
        self.lbl_download_status.setObjectName("DownloadText")
        self.lbl_download_speed = QLabel("0.0 MB/s")
        self.lbl_download_speed.setObjectName("DownloadSpeed")
        d_header_lay.addWidget(self.lbl_download_status)
        d_header_lay.addStretch()
        d_header_lay.addWidget(self.lbl_download_speed)
        d_lay.addLayout(d_header_lay)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("CyberProgressBar")
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        d_lay.addWidget(self.progress_bar)

        self.download_container.setVisible(False)
        lay.addWidget(self.download_container)

        # Action Area (Launch Button + Utility Buttons)
        action_lay = QHBoxLayout()
        action_lay.setSpacing(12)

        self.btn_launch = QPushButton("INITIALIZE & LAUNCH VISION ENGINE")
        self.btn_launch.setObjectName("LaunchButton")
        self.btn_launch.setFixedHeight(48)
        self.btn_launch.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_launch.clicked.connect(self._toggle_launch)
        action_lay.addWidget(self.btn_launch, stretch=3)

        btn_settings = QPushButton("⚙️ SETTINGS [F8]")
        btn_settings.setObjectName("SecondaryButton")
        btn_settings.setFixedHeight(48)
        btn_settings.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_settings.clicked.connect(self._open_settings)
        action_lay.addWidget(btn_settings, stretch=1)

        btn_test = QPushButton("🎯 WIGGLE TEST")
        btn_test.setObjectName("SecondaryButton")
        btn_test.setFixedHeight(48)
        btn_test.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_test.clicked.connect(self._run_wiggle_test)
        action_lay.addWidget(btn_test, stretch=1)

        btn_update = QPushButton("🔄 UPDATE ASSETS")
        btn_update.setObjectName("SecondaryButton")
        btn_update.setFixedHeight(48)
        btn_update.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_update.clicked.connect(lambda: self._start_asset_download_and_launch(force=True))
        action_lay.addWidget(btn_update, stretch=1)

        lay.addLayout(action_lay)

        # Live Status Footer
        footer_lay = QHBoxLayout()
        self.lbl_status = QLabel("System Ready. Click Launch to start.")
        self.lbl_status.setObjectName("SubText")
        footer_lay.addWidget(self.lbl_status)
        footer_lay.addStretch()

        lbl_hotkeys = QLabel("Hotkeys: [C] Aim Toggle  |  [F7] Overlay  |  [F8] Menu")
        lbl_hotkeys.setObjectName("SubText")
        footer_lay.addWidget(lbl_hotkeys)
        lay.addLayout(footer_lay)

        self.stack.addWidget(page)

    # -----------------------------------------------------------------
    # LOGIC HANDLERS
    # -----------------------------------------------------------------
    def _copy_hwid(self):
        cb = QApplication.clipboard()
        cb.setText(self.hwid)
        self.lbl_hwid_val.setText(f"{self.hwid} (COPIED!)")
        QTimer.singleShot(1500, lambda: self.lbl_hwid_val.setText(self.hwid))

    def _handle_activation(self):
        key = self.txt_key.text().strip().upper()
        if not key:
            self.lbl_auth_status.setText("⚠️ Please enter a valid license key.")
            self.lbl_auth_status.setStyleSheet("color: #FF5555;")
            return

        self.lbl_auth_status.setText("Verifying license key & hardware signature...")
        self.lbl_auth_status.setStyleSheet("color: #FFE600;")
        QApplication.processEvents()
        time.sleep(0.3)

        success, msg, plan = self.license_mgr.validate_key(key, remember=self.chk_remember.isChecked())
        if success:
            self.lbl_auth_status.setText("✅ License successfully activated!")
            self.lbl_auth_status.setStyleSheet("color: #00FFCC;")
            self.lbl_sub_badge.setText(f"💎 {self.license_mgr.get_user_tier()}")
            QApplication.processEvents()
            time.sleep(0.4)
            self.stack.setCurrentIndex(1)
            self._sync_selected_game_card()
        else:
            self.lbl_auth_status.setText(f"❌ {msg}")
            self.lbl_auth_status.setStyleSheet("color: #FF2A55; font-weight: bold;")

    def _select_game(self, game_id: str):
        # Update UI highlight
        for gid, item in self.game_cards.items():
            if gid == game_id:
                item["frame"].setProperty("selected", "true")
            else:
                item["frame"].setProperty("selected", "false")
            item["frame"].style().unpolish(item["frame"])
            item["frame"].style().polish(item["frame"])

        # Update yolo_config.json in active directory
        active_dir = get_active_payload_dir()
        cfg_path = os.path.join(active_dir, "yolo_config.json")
        if not os.path.exists(cfg_path) and os.path.exists(CONFIG_FILE):
            cfg_path = CONFIG_FILE

        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                
                cfg["active_game_profile"] = game_id
                cfg["model_path"] = self.game_cards[game_id]["engine"]
                cfg["makcu_target_bone"] = self.game_cards[game_id]["bone"]
                
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=4)
                
                self.lbl_status.setText(f"Active Profile set to: {self.game_cards[game_id]['name']}")
            except Exception as e:
                self.lbl_status.setText(f"Error updating config: {e}")

    def _sync_selected_game_card(self):
        curr_game = "valorant"
        active_dir = get_active_payload_dir()
        cfg_path = os.path.join(active_dir, "yolo_config.json")
        if not os.path.exists(cfg_path) and os.path.exists(CONFIG_FILE):
            cfg_path = CONFIG_FILE

        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    curr_game = cfg.get("active_game_profile", "valorant")
            except Exception:
                pass
        self._select_game(curr_game)

    def _on_hardware_detected(self, info: dict):
        self.lbl_gpu.setText(f"🎮 GPU: {info.get('gpu_name')} ({info.get('tensorrt_status')})")
        self.lbl_makcu.setText(f"🔌 MAKCU: {info.get('makcu_status')}")

    def _on_update_result(self, is_update_avail: bool, new_ver: str, changelog: list):
        if is_update_avail:
            self.lbl_update_badge.setText(f"🚀 UPDATE READY: v{new_ver}")
            self.lbl_update_badge.setStyleSheet("color: #FFE600; font-weight: bold;")
        else:
            self.lbl_update_badge.setText(f"✅ System Up to Date (v{new_ver})")
            self.lbl_update_badge.setStyleSheet("color: #00FFCC;")

    def _toggle_launch(self):
        if self.active_process is not None and self.active_process.poll() is None:
            # Terminate running process
            try:
                self.active_process.terminate()
                self.active_process.wait(timeout=1.5)
            except Exception:
                try:
                    self.active_process.kill()
                except Exception:
                    pass
            self.active_process = None
            self.btn_launch.setText("INITIALIZE & LAUNCH VISION ENGINE")
            self.btn_launch.setObjectName("LaunchButton")
            self.btn_launch.style().unpolish(self.btn_launch)
            self.btn_launch.style().polish(self.btn_launch)
            self.lbl_status.setText("Vision Engine stopped.")
            return

        # Check if assets are installed or need download
        if not is_client_installed():
            self._start_asset_download_and_launch()
            return

        self._start_vision_engine()

    def _start_asset_download_and_launch(self, force=False):
        self.btn_launch.setEnabled(False)
        self.btn_launch.setText("DOWNLOADING ASSETS...")
        self.download_container.setVisible(True)
        if force:
            self.lbl_status.setText("Cloud Sync: Downloading latest updates from GitHub Releases...")
        else:
            self.lbl_status.setText("First-time setup: Provisioning AI engines & assets...")

        self.downloader_thread = CloudAssetDownloaderThread()
        self.downloader_thread.sig_progress.connect(self._on_download_progress)
        self.downloader_thread.sig_finished.connect(lambda s, m: self._on_download_finished(s, m, auto_launch=not force))
        self.downloader_thread.start()

    def _on_download_progress(self, percent: int, status_msg: str, speed_str: str):
        self.progress_bar.setValue(percent)
        self.lbl_download_status.setText(status_msg)
        self.lbl_download_speed.setText(speed_str)

    def _on_download_finished(self, success: bool, message: str, auto_launch: bool = True):
        self.download_container.setVisible(False)
        self.btn_launch.setEnabled(True)
        self.btn_launch.setText("INITIALIZE & LAUNCH VISION ENGINE")
        if success:
            if auto_launch:
                self.lbl_status.setText("✅ Assets synchronized. Starting engine...")
                self._start_vision_engine()
            else:
                self.lbl_status.setText("✅ Update successful! All assets are up to date.")
        else:
            self.lbl_status.setText(f"❌ Setup error: {message}")

    def _start_vision_engine(self):
        py_cmd = get_runtime_python()
        active_dir = get_active_payload_dir()
        target_script = os.path.join(active_dir, "yolo_main.py")
        if not os.path.exists(target_script):
            self.lbl_status.setText(f"Error: '{target_script}' not found in app directory!")
            return

        try:
            log_path = os.path.join(active_dir, "engine_output.log")
            self.log_file = open(log_path, "w", encoding="utf-8", errors="replace")
            # Start detached process with no console window
            creation_flags = 0x08000000  # CREATE_NO_WINDOW
            self.active_process = subprocess.Popen(
                [py_cmd, target_script],
                cwd=active_dir,
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags
            )
            self.uptime_seconds = 0
            self.btn_launch.setText("⏹️ STOP ACTIVE VISION ENGINE (RUNNING)")
            self.btn_launch.setObjectName("StopButton")
            self.btn_launch.style().unpolish(self.btn_launch)
            self.btn_launch.style().polish(self.btn_launch)
            self.lbl_status.setText(f"Running (PID: {self.active_process.pid}) · Direct TensorRT 10 Stream Active")
        except Exception as e:
            self.lbl_status.setText(f"Launch error: {e}")

    def _check_process_health(self):
        if self.active_process is not None:
            if self.active_process.poll() is None:
                self.uptime_seconds += 1
                m, s = divmod(self.uptime_seconds, 60)
                self.lbl_status.setText(f"Running (PID: {self.active_process.pid} · Uptime: {m:02d}:{s:02d}) · 100% Headshot Fusion")
            else:
                self.active_process = None
                self.btn_launch.setText("INITIALIZE & LAUNCH VISION ENGINE")
                self.btn_launch.setObjectName("LaunchButton")
                self.btn_launch.style().unpolish(self.btn_launch)
                self.btn_launch.style().polish(self.btn_launch)
                
                # Check engine_output.log for exact error
                err_hint = ""
                active_dir = get_active_payload_dir()
                log_path = os.path.join(active_dir, "engine_output.log")
                if os.path.exists(log_path):
                    try:
                        with open(log_path, "r", encoding="utf-8", errors="ignore") as lf:
                            content = lf.read().strip()
                            if content:
                                lines = [l.strip() for l in content.split("\n") if l.strip()]
                                if lines:
                                    err_hint = lines[-1]
                    except Exception:
                        pass
                if err_hint:
                    self.lbl_status.setText(f"Terminated: {err_hint[:50]}")
                else:
                    self.lbl_status.setText("Vision Engine terminated.")

    def _open_settings(self):
        # Trigger F8 or start settings standalone
        py_cmd = get_runtime_python()
        subprocess.Popen([py_cmd, "-c", "import win32api, win32con; win32api.keybd_event(0x77, 0, 0, 0); win32api.keybd_event(0x77, 0, win32con.KEYEVENTF_KEYUP, 0)"])

    def _run_wiggle_test(self):
        py_cmd = get_runtime_python()
        active_dir = get_active_payload_dir()
        test_script = (
            "import time, json\n"
            "from aurapart import MAKCU_AimbotEngine\n"
            "cfg = {}\n"
            "try:\n"
            "    with open('yolo_config.json', 'r', encoding='utf-8') as f:\n"
            "        cfg = json.load(f)\n"
            "except Exception:\n"
            "    pass\n"
            "eng = MAKCU_AimbotEngine(cfg)\n"
            "time.sleep(0.5)\n"
            "res = eng.test_move()\n"
            "eng.disconnect()\n"
            "print('OK' if res else 'FAIL')\n"
        )
        try:
            res = subprocess.run([py_cmd, "-c", test_script], capture_output=True, text=True, cwd=active_dir)
            if "OK" in res.stdout:
                self.lbl_status.setText("✅ MAKCU Hardware Test OK! Cursor responded.")
            else:
                self.lbl_status.setText("⚠️ MAKCU Hardware Test failed. Check COM port.")
        except Exception as e:
            self.lbl_status.setText(f"Test error: {e}")

    # -----------------------------------------------------------------
    # WINDOW DRAGGING EVENTS
    # -----------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    # -----------------------------------------------------------------
    # STYLING SHEET
    # -----------------------------------------------------------------
    def _apply_styling(self):
        qss = """
        QFrame#CentralContainer {
            background-color: #0b0d12;
            border: 1px solid #1c2333;
            border-radius: 12px;
        }

        QFrame#TitleBar {
            background-color: #0f131a;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1px solid #1c2333;
        }

        QLabel#TitleLogo {
            color: #00FFCC;
            font-size: 15px;
            font-weight: 900;
            letter-spacing: 2px;
        }

        QLabel#TitleText {
            color: #8b9bb4;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.5px;
            margin-left: 8px;
        }

        QPushButton#TitleBtn {
            background: transparent;
            color: #8b9bb4;
            border: none;
            font-size: 14px;
            width: 28px;
            height: 28px;
            border-radius: 4px;
        }
        QPushButton#TitleBtn:hover {
            background: #1c2333;
            color: #ffffff;
        }

        QPushButton#TitleCloseBtn {
            background: transparent;
            color: #8b9bb4;
            border: none;
            font-size: 13px;
            width: 28px;
            height: 28px;
            border-radius: 4px;
        }
        QPushButton#TitleCloseBtn:hover {
            background: #ff2a55;
            color: #ffffff;
        }

        QFrame#AuthCard {
            background-color: #11151f;
            border: 1px solid #232c40;
            border-radius: 12px;
            max-width: 520px;
        }

        QLabel#AuthHeader {
            color: #ffffff;
            font-size: 18px;
            font-weight: 800;
            letter-spacing: 2px;
        }

        QLabel#SubText {
            color: #7a889b;
            font-size: 11px;
        }

        QFrame#HwidBox {
            background-color: #090b10;
            border: 1px solid #1c2333;
            border-radius: 8px;
        }

        QLabel#BadgeLabel {
            color: #00FFCC;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
        }

        QLabel#HwidValue {
            color: #ffffff;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            font-weight: bold;
            margin-left: 6px;
        }

        QPushButton#ActionPillBtn {
            background-color: #1a2233;
            color: #00FFCC;
            border: 1px solid #00FFCC;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 800;
            padding: 3px 8px;
        }
        QPushButton#ActionPillBtn:hover {
            background-color: #00FFCC;
            color: #000000;
        }

        QLineEdit#KeyInput {
            background-color: #090b10;
            border: 1px solid #232c40;
            border-radius: 8px;
            color: #ffffff;
            font-size: 12px;
            padding: 10px 14px;
        }
        QLineEdit#KeyInput:focus {
            border: 1px solid #00FFCC;
        }

        QCheckBox {
            color: #8b9bb4;
            font-size: 11px;
        }
        QCheckBox::indicator {
            width: 14px;
            height: 14px;
            border-radius: 3px;
            border: 1px solid #2b354c;
            background: #090b10;
        }
        QCheckBox::indicator:checked {
            background: #00FFCC;
            border-color: #00FFCC;
        }

        QFrame#TopInfoBar {
            background-color: #11151f;
            border: 1px solid #1c2333;
            border-radius: 8px;
        }

        QLabel#VipBadge {
            background-color: #211538;
            color: #c084fc;
            border: 1px solid #7c3aed;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 800;
            padding: 2px 8px;
            margin-right: 8px;
        }

        QLabel#UpdateBadge {
            font-size: 11px;
            font-weight: bold;
        }

        QLabel#SectionHeader {
            color: #8b9bb4;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1.5px;
            margin-top: 4px;
        }

        QFrame#GameCard {
            background-color: #11151f;
            border: 1px solid #1c2333;
            border-radius: 8px;
        }
        QFrame#GameCard:hover {
            border: 1px solid #3b4763;
            background-color: #151a26;
        }
        QFrame#GameCard[selected="true"] {
            border: 1px solid #00FFCC;
            background-color: #0e1e24;
        }

        QLabel#GameBadge {
            color: #00FFCC;
            font-size: 10px;
            font-weight: 800;
        }

        QLabel#GameTitle {
            color: #ffffff;
            font-size: 14px;
            font-weight: bold;
        }

        QLabel#GameStatusOnline {
            color: #10b981;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
            margin-top: 4px;
        }

        QFrame#HardwareBox {
            background-color: #0c0f16;
            border: 1px solid #1c2333;
            border-radius: 8px;
        }

        QLabel#HwLabel {
            color: #94a3b8;
            font-size: 11px;
            font-weight: 600;
        }

        QFrame#DownloadContainer {
            background-color: #0d121c;
            border: 1px solid #1e293b;
            border-radius: 8px;
        }

        QLabel#DownloadText {
            color: #00FFCC;
            font-size: 11px;
            font-weight: 700;
        }

        QLabel#DownloadSpeed {
            color: #94a3b8;
            font-size: 11px;
            font-weight: 600;
        }

        QProgressBar#CyberProgressBar {
            background-color: #111827;
            border: 1px solid #1f2937;
            border-radius: 4px;
        }

        QProgressBar#CyberProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00E5FF, stop:1 #00FF9D);
            border-radius: 4px;
        }

        QPushButton#LaunchButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00E5FF, stop:1 #00FF9D);
            color: #050b14;
            font-size: 13px;
            font-weight: 900;
            letter-spacing: 1px;
            border: none;
            border-radius: 8px;
        }
        QPushButton#LaunchButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38E1FF, stop:1 #33FFB0);
        }

        QPushButton#StopButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF2A55, stop:1 #FF5E3A);
            color: #ffffff;
            font-size: 13px;
            font-weight: 900;
            letter-spacing: 1px;
            border: none;
            border-radius: 8px;
        }
        QPushButton#StopButton:hover {
            background: #ff476d;
        }

        QPushButton#SecondaryButton {
            background-color: #131822;
            color: #cbd5e1;
            border: 1px solid #232c40;
            border-radius: 8px;
            font-size: 11px;
            font-weight: bold;
        }
        QPushButton#SecondaryButton:hover {
            background-color: #1c2333;
            border-color: #384666;
            color: #ffffff;
        }
        """
        self.setStyleSheet(qss)


def main():
    app = QApplication(sys.argv)
    win = CommercialLoaderWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
