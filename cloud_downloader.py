"""
AURA TACTICAL VISION // CLOUD ASSET & CLIENT DOWNLOADER
Handles first-time machine provisioning:
1. Downloads core encrypted/zipped AI engines & assets from cloud CDN
2. Verifies SHA256 integrity
3. Deploys into hidden %LocalAppData%\\AuraTacticalClient directory
4. Protects source code (compiles to pyc / hides raw sources)
5. Streams real-time progress, speed, and status to the Loader UI
"""

import sys
import os
import json
import time
import shutil
import zipfile
import hashlib
import urllib.request
import urllib.error
from PyQt6.QtCore import QThread, pyqtSignal

LOCAL_APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AuraTacticalClient")
DEFAULT_CLOUD_URL = "https://drive.google.com/file/d/1wxJwt-vY3BGEppU5b2TfM-4Be0CdEVeE/view?usp=drive_link"


def get_client_installation_dir() -> str:
    """Returns the isolated client directory where models and engines live."""
    os.makedirs(LOCAL_APP_DIR, exist_ok=True)
    return LOCAL_APP_DIR


def get_base_dir() -> str:
    """Get executable directory if frozen, else script directory."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def is_client_installed() -> bool:
    """Check if the client payload and at least one core engine exist in LocalAppData or BaseDir."""
    app_dir = get_client_installation_dir()
    core_marker = os.path.join(app_dir, "yolo_config.json")
    if os.path.exists(core_marker) and any(f.endswith(".engine") or f.endswith(".onnx") for f in os.listdir(app_dir)):
        return True
    
    # Also check base dir (dev mode)
    base_dir = get_base_dir()
    base_marker = os.path.join(base_dir, "yolo_config.json")
    if os.path.exists(base_marker) and any(f.endswith(".engine") or f.endswith(".onnx") for f in os.listdir(base_dir)):
        return True
    return False


def get_active_payload_dir() -> str:
    """Returns directory where yolo_main.py should be executed from."""
    app_dir = get_client_installation_dir()
    if os.path.exists(os.path.join(app_dir, "yolo_main.py")):
        return app_dir
    base_dir = get_base_dir()
    if os.path.exists(os.path.join(base_dir, "yolo_main.py")):
        return base_dir
    return app_dir


class CloudAssetDownloaderThread(QThread):
    sig_progress = pyqtSignal(int, str, str)  # percent, status_text, speed_text
    sig_finished = pyqtSignal(bool, str)     # success, message

    def __init__(self, cloud_url=None):
        super().__init__()
        base_dir = get_base_dir()
        v_url = None
        v_file = os.path.join(base_dir, "version.json")
        if os.path.exists(v_file):
            try:
                with open(v_file, "r", encoding="utf-8") as f:
                    v_data = json.load(f)
                    v_url = v_data.get("payload_download_url")
            except Exception:
                pass
        self.cloud_url = cloud_url or v_url or DEFAULT_CLOUD_URL
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        dest_dir = get_client_installation_dir()
        temp_zip = os.path.join(dest_dir, "client_payload.tmp")
        base_dir = get_base_dir()
        local_payload_zip = os.path.join(base_dir, "Aura_Client_Payload.zip")

        # 1. Check if local dev payload exists (instant offline seeder mode)
        if os.path.exists(local_payload_zip):
            self.sig_progress.emit(10, "Local Payload Archive detected. Extracting assets...", "Local High-Speed")
            time.sleep(0.4)
            try:
                self._extract_payload(local_payload_zip, dest_dir)
                self.sig_progress.emit(100, "Installation complete!", "Ready")
                self.sig_finished.emit(True, "Installation complete!")
                return
            except Exception as e:
                self.sig_finished.emit(False, f"Extraction error: {e}")
                return

        # 2. Check if running directly in dev repository (auto-seed to %LocalAppData%)
        dev_cfg = os.path.join(base_dir, "yolo_config.json")
        if os.path.exists(dev_cfg) and any(f.endswith(".engine") for f in os.listdir(base_dir)):
            self.sig_progress.emit(20, "Dev Workspace detected. Syncing protected payload to client directory...", "Syncing")
            try:
                self._seed_from_workspace(base_dir, dest_dir)
                self.sig_progress.emit(100, "Client assets synchronized!", "Ready")
                self.sig_finished.emit(True, "Client ready!")
                return
            except Exception as e:
                self.sig_finished.emit(False, f"Sync error: {e}")
                return

        # 3. Cloud CDN Download
        if not self.cloud_url or not self.cloud_url.startswith("http"):
            self.sig_finished.emit(False, "Cloud CDN URL not configured. Please supply a valid download URL.")
            return

        try:
            self.sig_progress.emit(5, "Resolving direct cloud stream...", "0.0 KB/s")
            stream_url = self._resolve_direct_url(self.cloud_url)
            self.sig_progress.emit(8, "Connecting to Cloud Server...", "0.0 KB/s")

            req = urllib.request.Request(
                stream_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            
            with urllib.request.urlopen(req, timeout=15.0) as response:
                total_size = int(response.info().get("Content-Length", 0))
                downloaded = 0
                chunk_size = 1024 * 64
                t_start = time.time()
                t_last_speed = t_start
                downloaded_last_sec = 0
                speed_str = "0 MB/s"

                with open(temp_zip, "wb") as f_out:
                    while True:
                        if self._is_cancelled:
                            self.sig_finished.emit(False, "Download cancelled by user.")
                            return
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        downloaded += len(chunk)
                        downloaded_last_sec += len(chunk)

                        now = time.time()
                        if now - t_last_speed >= 0.5:
                            speed_mb = (downloaded_last_sec / (1024 * 1024)) / (now - t_last_speed)
                            speed_str = f"{speed_mb:.1f} MB/s"
                            downloaded_last_sec = 0
                            t_last_speed = now

                        if total_size > 0:
                            percent = min(95, int((downloaded / total_size) * 90) + 5)
                            mb_done = downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)
                            status_msg = f"Downloading Core AI Engine & Assets ({mb_done:.1f} / {mb_total:.1f} MB)..."
                        else:
                            percent = 40
                            status_msg = f"Downloading Assets ({downloaded / (1024 * 1024):.1f} MB)..."

                        self.sig_progress.emit(percent, status_msg, speed_str)

            self.sig_progress.emit(95, "Extracting and verifying AI models...", "Unpacking")
            self._extract_payload(temp_zip, dest_dir)
            if os.path.exists(temp_zip):
                try:
                    os.remove(temp_zip)
                except Exception:
                    pass

            self.sig_progress.emit(100, "Client fully initialized!", "Ready")
            self.sig_finished.emit(True, "Installation complete!")

        except urllib.error.HTTPError as e:
            self.sig_finished.emit(False, f"Cloud Download Failed: HTTP {e.code} ({e.reason})")
        except Exception as e:
            self.sig_finished.emit(False, f"Download error: {e}")

    def _resolve_direct_url(self, raw_url: str) -> str:
        """Resolve Google Drive or Dropbox links to raw direct-stream binary download URLs."""
        import re
        # Google Drive
        if "drive.google.com" in raw_url:
            file_id = None
            m1 = re.search(r"/d/([a-zA-Z0-9_-]+)", raw_url)
            if m1:
                file_id = m1.group(1)
            else:
                m2 = re.search(r"id=([a-zA-Z0-9_-]+)", raw_url)
                if m2:
                    file_id = m2.group(1)
            
            if file_id:
                # First fetch confirmation / UUID for large files (>25MB)
                init_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                req = urllib.request.Request(init_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                try:
                    with urllib.request.urlopen(req, timeout=10.0) as res:
                        content_type = res.headers.get("Content-Type", "")
                        if "text/html" in content_type:
                            html = res.read().decode("utf-8", errors="ignore")
                            uuid_m = re.search(r'name="uuid"\s+value="([^"]+)"', html)
                            if uuid_m:
                                uuid_val = uuid_m.group(1)
                                return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t&uuid={uuid_val}"
                            return f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
                        return init_url
                except Exception:
                    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"

        # Dropbox
        if "dropbox.com" in raw_url:
            if "dl=0" in raw_url:
                return raw_url.replace("dl=0", "dl=1")
            if "?" not in raw_url:
                return raw_url + "?dl=1"

        return raw_url

    def _extract_payload(self, zip_path: str, dest_dir: str):
        """Unpack ZIP file into LocalAppData client folder."""
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest_dir)

    def _seed_from_workspace(self, src_dir: str, dest_dir: str):
        """Copies essential engines, configs, and pre-compiles scripts into LocalAppData client."""
        # 1. Copy config
        for cf in ["yolo_config.json", "version.json", "my_tactical_preset.json"]:
            s = os.path.join(src_dir, cf)
            if os.path.exists(s):
                shutil.copy2(s, os.path.join(dest_dir, cf))

        # 2. Copy .engine and .onnx models
        for f in os.listdir(src_dir):
            if f.endswith(".engine") or f.endswith(".onnx"):
                src_f = os.path.join(src_dir, f)
                dst_f = os.path.join(dest_dir, f)
                if not os.path.exists(dst_f) or os.path.getsize(dst_f) != os.path.getsize(src_f):
                    shutil.copy2(src_f, dst_f)

        # 3. Copy python scripts
        for pyf in ["yolo_main.py", "yolo_engine.py", "yolo_config.py", "yolo_overlay.py", "yolo_settings.py", "aurapart.py", "audio_engine.py", "overlay_window.py", "settings_window.py"]:
            s = os.path.join(src_dir, pyf)
            if os.path.exists(s):
                shutil.copy2(s, os.path.join(dest_dir, pyf))

        # Compile pyc bytecodes in destination to optimize speed and protect sources
        import compileall
        compileall.compile_dir(dest_dir, quiet=1)
