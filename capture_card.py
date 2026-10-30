"""
AURA TACTICAL VISION // DUAL-PC CAPTURE CARD ENGINE
Hardware-isolated HDMI Capture Card receiver for Dual-PC setups.
Supports DirectShow hardware decoding (NV12, YUY2, MJPG) with zero-latency
buffer flushing, auto-reconnect, and sub-frame region cropping.
"""

import time
import threading
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


def list_capture_devices(max_devices: int = 4) -> list:
    """
    Fast, non-blocking scan of available video capture devices.
    Returns list of dicts with device index, resolution, and availability.
    """
    if not CV2_AVAILABLE:
        return []

    devices = []
    for idx in range(max_devices):
        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, _ = cap.read()
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))
                cap.release()
                devices.append({
                    "index": idx,
                    "width": w if w > 0 else 1920,
                    "height": h if h > 0 else 1080,
                    "fps": fps if fps > 0 else 60,
                    "active": bool(ret),
                    "name": f"HDMI Capture Device #{idx} ({w}x{h})" if idx > 0 else f"Video Device #{idx} ({w}x{h})"
                })
        except Exception:
            pass
    return devices


class CaptureCardStream:
    """
    High-performance, zero-latency threaded capture stream for HDMI capture cards.
    Flushes internal video buffer so inference engine always reads the freshest frame.
    """
    def __init__(self, device_index: int = 0, width: int = 1920, height: int = 1080, fps: int = 60):
        self.device_index = int(device_index)
        self.target_width = int(width)
        self.target_height = int(height)
        self.target_fps = int(fps)

        self.cap = None
        self.running = False
        self.has_signal = False
        self.latest_frame = None
        self._lock = threading.Lock()
        self._thread = None

        self.fps_counter = 0
        self.current_fps = 0.0
        self.last_fps_calc = time.time()
        self.last_frame_time = 0.0
        self.consecutive_errors = 0

    def start(self) -> bool:
        """Start background frame grabber thread."""
        if not CV2_AVAILABLE:
            print("[CaptureCard] Error: OpenCV (cv2) is not available.")
            return False

        self.running = True
        self._thread = threading.Thread(target=self._capture_loop, name="AuraCaptureCardWorker", daemon=True)
        self._thread.start()
        return True

    def _init_capture(self) -> bool:
        """Initialize DirectShow capture device with optimal low-latency flags."""
        try:
            if self.cap is not None:
                self.cap.release()

            self.cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                return False

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
            if self.target_fps > 0:
                self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)

            # Critical: Buffer size 1 to avoid queueing latency
            try:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[CaptureCard] Device #{self.device_index} init failed: {e}")
            return False

    def _capture_loop(self):
        """Worker loop that continuously grabs freshest HDMI frames."""
        retry_delay = 0.5
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                if not self._init_capture():
                    with self._lock:
                        self.has_signal = False
                    time.sleep(retry_delay)
                    continue

            ret, frame = self.cap.read()
            now = time.perf_counter()

            if ret and frame is not None and frame.size > 0:
                self.consecutive_errors = 0
                self.last_frame_time = now
                with self._lock:
                    self.latest_frame = frame
                    self.has_signal = True

                self.fps_counter += 1
                if now - self.last_fps_calc >= 1.0:
                    self.current_fps = self.fps_counter / (now - self.last_fps_calc)
                    self.fps_counter = 0
                    self.last_fps_calc = now
            else:
                self.consecutive_errors += 1
                if self.consecutive_errors > 15:
                    with self._lock:
                        self.has_signal = False
                    time.sleep(0.01)
                else:
                    time.sleep(0.001)

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def read_region(self, left: int, top: int, width: int, height: int) -> np.ndarray:
        """
        Extract centered sub-region crop from the latest HDMI frame.
        Guarantees fast numpy slicing with bounds checking.
        """
        with self._lock:
            if self.latest_frame is None or not self.has_signal:
                return None
            frame = self.latest_frame

        fh, fw = frame.shape[:2]
        # Clamp crop coordinates inside frame bounds
        cl = max(0, min(int(left), fw - 1))
        ct = max(0, min(int(top), fh - 1))
        cr = max(cl + 1, min(cl + int(width), fw))
        cb = max(ct + 1, min(ct + int(height), fh))

        crop = frame[ct:cb, cl:cr]
        if crop.shape[0] != height or crop.shape[1] != width:
            # Resize if boundary clipped
            crop = cv2.resize(crop, (width, height), interpolation=cv2.INTER_LINEAR)
        return crop

    def is_signal_active(self) -> bool:
        """Check if HDMI stream is currently transmitting frames."""
        with self._lock:
            return self.has_signal and (time.perf_counter() - self.last_frame_time < 2.0)

    def stop(self):
        """Cleanly terminate worker and free DirectShow resources."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
