"""
ARC Raiders YOLO Tactical Vision - MAKCU Hardware Aim Assist Engine
Ultra-low latency hardware mouse control via dual ESP32-S3 MAKCU device.
"""

import time
import math
import threading
import win32api
import win32con

try:
    import makcu
    from makcu import MouseButton
    MAKCU_LIB_AVAILABLE = True
except ImportError:
    MAKCU_LIB_AVAILABLE = False
    MouseButton = None


# Virtual Key code mapping for aim key activation
AIM_KEY_MAP = {
    "rmb": win32con.VK_RBUTTON,        # Right Mouse Button (Default ADS)
    "lalt": win32con.VK_MENU,          # Left Alt Key
    "xbutton1": win32con.VK_XBUTTON1,  # Mouse 4 (Back)
    "xbutton2": win32con.VK_XBUTTON2,  # Mouse 5 (Forward)
    "lshift": win32con.VK_LSHIFT,      # Left Shift
    "ctrl": win32con.VK_CONTROL,       # Ctrl Key
    "caps": win32con.VK_CAPITAL,       # CapsLock
    "always": -1,                      # Always aim assist when target in FOV
}

AIM_KEY_DISPLAY_NAMES = [
    ("Right Mouse Button (RMB)", "rmb"),
    ("Left Alt (Alt)", "lalt"),
    ("Mouse Button 4 (Back)", "xbutton1"),
    ("Mouse Button 5 (Forward)", "xbutton2"),
    ("Left Shift (Shift)", "lshift"),
    ("Ctrl Key (Control)", "ctrl"),
    ("Caps Lock", "caps"),
    ("Always On (Auto-Track in FOV)", "always"),
]

BONE_HEIGHT_RATIOS = {
    "head": 0.11,    # Head level (top 11% of bounding box)
    "neck": 0.25,    # Upper 25% of bounding box
    "chest": 0.40,   # Upper 40% (Upper Torso / Center of mass)
    "center": 0.50,  # Dead center of box
}


class MAKCU_AimbotEngine:
    def __init__(self, config=None):
        self.config = config or {}
        self.controller = None
        self.is_connected = False
        self.port = "Disconnected"
        self.device_info = {}
        self._lock = threading.Lock()
        self._connect_lock = threading.Lock()

        # State tracking
        self.is_aiming = False
        self.target_locked = None
        self._mouse_locked = False
        self.last_move_time = 0.0
        self.last_trigger_time = 0.0
        self.trigger_burst_count = 0
        self.burst_cooldown_until = 0.0

        # Auto-connect asynchronously in background so startup remains instant
        threading.Thread(target=self.connect, daemon=True).start()

    def connect(self):
        """Establish connection to MAKCU device via official driver."""
        with self._connect_lock:
            with self._lock:
                if self.is_connected and self.controller:
                    return True

            if not MAKCU_LIB_AVAILABLE:
                print("[MAKCU] makcu library not installed. Aim assist disabled.")
                return False

            try:
                print("[MAKCU] Probing for MAKCU hardware device...")
                target_port = self.config.get("makcu_port", "auto")
                ctrl = None
                
                if target_port and target_port.lower() != "auto":
                    # Explicit port configuration
                    try:
                        ctrl = makcu.create_controller(fallback_com_port=target_port, override_port=True)
                    except TypeError:
                        ctrl = makcu.create_controller(target_port)
                else:
                    # Auto-discovery via official library method
                    try:
                        ctrl = makcu.create_controller()
                    except Exception:
                        ctrl = None
                    
                    # Multi-port fallback: if auto-discovery failed, probe all active COM ports
                    if not (ctrl and ctrl.is_connected()):
                        try:
                            from serial.tools import list_ports
                            for p in list_ports.comports():
                                try:
                                    candidate = makcu.create_controller(fallback_com_port=p.device, override_port=True)
                                    if candidate and candidate.is_connected():
                                        ctrl = candidate
                                        print(f"[MAKCU] Auto-detected via port fallback on {p.device}")
                                        break
                                except Exception:
                                    continue
                        except Exception:
                            pass

                if ctrl and ctrl.is_connected():
                    info = ctrl.get_device_info()
                    fw = ctrl.get_firmware_version()
                    with self._lock:
                        self.controller = ctrl
                        self.is_connected = True
                        self.port = info.get("port", getattr(ctrl, "port", "COM"))
                        self.device_info = info
                    print(f"[MAKCU] Connected successfully to {self.port} (Firmware: {fw})")
                    return True
                else:
                    with self._lock:
                        self.is_connected = False
                        self.port = "Not Found"
                    print("[MAKCU] Device not found or handshake failed.")
                    return False
            except Exception as e:
                with self._lock:
                    self.is_connected = False
                    self.port = f"Error: {e}"
                print(f"[MAKCU] Connection error: {e}")
                return False

    def _set_hardware_mouse_lock(self, lock: bool):
        """
        Hardware-level physical mouse suppression via MAKCU ESP32 firmware.
        When locked, physical mouse movement is ignored so hand jitter cannot disrupt aim.
        """
        if self._mouse_locked == lock:
            return
        self._mouse_locked = lock
        try:
            ser = getattr(getattr(self.controller, "transport", None), "serial", None)
            if ser and getattr(ser, "is_open", False):
                cmd_x = b"km.lock_mx(1)\r\n" if lock else b"km.lock_mx(0)\r\n"
                cmd_y = b"km.lock_my(1)\r\n" if lock else b"km.lock_my(0)\r\n"
                ser.write(cmd_x + cmd_y)
            elif self.controller:
                self.controller.lock_x(lock)
                self.controller.lock_y(lock)
        except Exception as e:
            pass

    def disconnect(self):
        """Disconnect and release the serial port cleanly."""
        self._set_hardware_mouse_lock(False)
        with self._lock:
            if self.controller:
                try:
                    self.controller.disconnect()
                except Exception:
                    pass
                self.controller = None
            self.is_connected = False
            self.port = "Disconnected"

    def __del__(self):
        try:
            self._set_hardware_mouse_lock(False)
        except Exception:
            pass

    def is_key_pressed(self, key_name):
        """Check if designated aim activation key is currently pressed."""
        vkey = AIM_KEY_MAP.get(str(key_name).lower(), win32con.VK_RBUTTON)
        if vkey == -1:
            return True  # Always active mode
        # GetAsyncKeyState returns negative when key is held down
        return bool(win32api.GetAsyncKeyState(vkey) & 0x8000)

    def process_targets(self, targets, crosshair_x, crosshair_y, latency_ms=0.0):
        """
        Evaluate detected targets, check aim key, and apply smooth MAKCU hardware movement.
        Called directly in YOLO inference loop for ultra-low latency execution.
        """
        if not self.config.get("makcu_enabled", True):
            self.is_aiming = False
            self.target_locked = None
            self._set_hardware_mouse_lock(False)
            return

        if not self.is_connected or not self.controller:
            self.is_aiming = False
            self.target_locked = None
            self._set_hardware_mouse_lock(False)
            return

        aim_key = self.config.get("makcu_aim_key", "rmb")
        key_active = self.is_key_pressed(aim_key)

        if not key_active:
            self.is_aiming = False
            self.target_locked = None
            self._set_hardware_mouse_lock(False)
            return

        if not targets:
            self.is_aiming = False
            self.target_locked = None
            self._set_hardware_mouse_lock(False)
            return

        fov_radius = float(self.config.get("makcu_fov", 160))
        bone_mode = self.config.get("makcu_target_bone", "head").lower()
        bone_ratio = BONE_HEIGHT_RATIOS.get(bone_mode, 0.11)
        smooth = max(1.0, float(self.config.get("makcu_smooth", 4.5)))
        use_prediction = bool(self.config.get("makcu_prediction", True))

        # Find best target inside FOV radius closest to crosshair (strictly measuring distance to HEAD)
        best_target = None
        best_dist = float("inf")

        for t in targets:
            # 100% Strict Head Targeting: use detected head center if available, otherwise exact 11% ratio
            target_cx = t.get("head_cx", t["cx"])
            target_cy = t.get("head_cy", t["y1"] + t["h"] * bone_ratio)
            dist_to_crosshair = math.hypot(target_cx - crosshair_x, target_cy - crosshair_y)

            if dist_to_crosshair <= fov_radius and dist_to_crosshair < best_dist:
                best_dist = dist_to_crosshair
                best_target = t

        if not best_target:
            self.is_aiming = False
            self.target_locked = None
            self._set_hardware_mouse_lock(False)
            return

        # Target found inside FOV
        self.is_aiming = True
        self.target_locked = best_target

        # 100% STRICT HEAD LOCK: Exact Head coordinates
        if bone_mode == "head":
            aim_x = best_target.get("head_cx", best_target["cx"])
            aim_y = best_target.get("head_cy", best_target["y1"] + best_target["h"] * bone_ratio)
        else:
            aim_x = best_target["cx"]
            aim_y = best_target["y1"] + best_target["h"] * bone_ratio

        # Delta relative to crosshair
        delta_x = aim_x - crosshair_x
        delta_y = aim_y - crosshair_y
        dist_px = math.hypot(delta_x, delta_y)

        # Check if crosshair is directly on the enemy
        x1, y1, x2, y2 = best_target["x1"], best_target["y1"], best_target["x2"], best_target["y2"]
        is_on_target = ((x1 <= crosshair_x <= x2) and (y1 <= crosshair_y <= y2)) or (dist_px <= 14.0)

        # Hardware-level physical mouse freeze while reticle is on target
        if self.config.get("makcu_lock_on_target", False):
            if is_on_target:
                self._set_hardware_mouse_lock(True)
            else:
                self._set_hardware_mouse_lock(False)
        elif self._mouse_locked:
            self._set_hardware_mouse_lock(False)

        lead_x = 0.0
        lead_y = 0.0
        if ("vx" in best_target) and ("vy" in best_target):
            tv_x = best_target.get("vx", 0.0)
            tv_y = best_target.get("vy", 0.0)
            target_vel = math.hypot(tv_x, tv_y)

            # Active when enemy moves (> 25 px/s)
            if target_vel > 25.0:
                # Total latency pipeline: capture + tensorrt + USB transfer (~26-32ms)
                lead_dt = 0.030
                lead_x = tv_x * lead_dt
                lead_y = tv_y * lead_dt

                # Generous safety clamp so it stays locked right onto the center of the head
                max_lead = max(8.0, best_target.get("w", 30) * 0.40)
                lead_x = max(-max_lead, min(max_lead, lead_x))
                lead_y = max(-max_lead, min(max_lead, lead_y))

                delta_x += lead_x
                delta_y += lead_y

        # Deadzone: stable deadzone so the mouse NEVER oscillates or wiggles around the head
        if dist_px <= 3.0:
            click_cmd = self._evaluate_triggerbot(best_target, crosshair_x, crosshair_y, move_dist=0.0, lead_x=0.0, lead_y=0.0)
            if click_cmd:
                try:
                    ser = getattr(getattr(self.controller, "transport", None), "serial", None)
                    if ser and getattr(ser, "is_open", False):
                        ser.write(click_cmd)
                    elif self.controller and MouseButton:
                        self.controller.click(MouseButton.LEFT)
                except Exception:
                    pass
            return

        # Clean Linear Snap (Zero Wiggle, Zero Overshoot)
        # S-Curve damping prevents the mouse from oscillating back and forth across the head
        snap_smooth = max(1.0, smooth)
        if snap_smooth <= 1.05:
            # Clean snappy move with critically damped landing:
            # 75% step per frame = reaches head in 2 fast frames without ever overshooting
            step_x = delta_x * 0.75
            step_y = delta_y * 0.75
            max_step = 60.0
        elif dist_px <= 5.0:
            step_x = delta_x * 0.50
            step_y = delta_y * 0.50
            max_step = 25.0
        else:
            curve_smooth = max(1.2, snap_smooth * 0.80)
            step_x = delta_x / curve_smooth
            step_y = delta_y / curve_smooth
            max_step = 45.0

        step_x = max(-max_step, min(max_step, step_x))
        step_y = max(-max_step, min(max_step, step_y))

        move_x = int(round(step_x))
        move_y = int(round(step_y))

        # Check triggerbot in the same frame (with lead prediction included!)
        move_dist = math.hypot(move_x, move_y)
        click_cmd = self._evaluate_triggerbot(best_target, crosshair_x, crosshair_y, move_dist=move_dist, lead_x=lead_x, lead_y=lead_y)

        # Feature 7: Zero-Latency Batched Serial Pipeline
        # Fuses move + click into a single atomic byte packet to halve USB bus latency
        if move_x != 0 or move_y != 0 or click_cmd:
            try:
                ser = getattr(getattr(self.controller, "transport", None), "serial", None)
                if ser and getattr(ser, "is_open", False):
                    packet = bytearray()
                    if move_x != 0 or move_y != 0:
                        packet += b"km.move(%d,%d)\r\n" % (move_x, move_y)
                    if click_cmd:
                        packet += click_cmd
                    ser.write(packet)
                else:
                    if move_x != 0 or move_y != 0:
                        self.controller.move(move_x, move_y)
                    if click_cmd and MouseButton:
                        self.controller.click(MouseButton.LEFT)
            except Exception as e:
                try:
                    if move_x != 0 or move_y != 0:
                        self.controller.move(move_x, move_y)
                except Exception:
                    self.is_connected = False
                    print(f"[MAKCU] Move command error: {e}")

    def _is_moving(self):
        """Check if movement keys (W, A, S, D, Space) are currently pressed."""
        movement_keys = (0x57, 0x41, 0x53, 0x44, win32con.VK_SPACE)  # W, A, S, D, Space
        try:
            for vk in movement_keys:
                if win32api.GetAsyncKeyState(vk) & 0x8000:
                    return True
        except Exception:
            pass
        return False

    def _evaluate_triggerbot(self, target, crosshair_x, crosshair_y, move_dist=0.0, lead_x=0.0, lead_y=0.0):
        """Evaluate triggerbot conditions and return direct byte command if ready to fire."""
        if not self.config.get("makcu_triggerbot", False):
            self.trigger_burst_count = 0
            return None

        # Counter-Strafing / Stillness Check: Don't shoot while moving
        if bool(self.config.get("makcu_triggerbot_stop_to_shoot", True)):
            if self._is_moving():
                return None

        # Aim Snap Check: Don't shoot while the aimbot is snapping / rapidly correcting
        if bool(self.config.get("makcu_triggerbot_snap_check", True)):
            if move_dist > 3.0:
                return None

        now = time.time()
        if now < getattr(self, "burst_cooldown_until", 0.0):
            return None

        # 1. Hit validation (Headshot-only vs Full-body)
        head_only = bool(self.config.get("makcu_triggerbot_head_only", True))

        # Include real-time motion lead in hit evaluation so running targets are validated accurately
        head_x = target.get("head_cx", target["cx"]) + lead_x
        head_y = target.get("head_cy", target["y1"] + target["h"] * 0.11) + lead_y
        hw_rad = max(4.0, target.get("head_w", 12.0) / 2.0)
        hh_rad = max(4.0, target.get("head_h", 14.0) / 2.0)
        norm_head_sq = ((crosshair_x - head_x) / hw_rad) ** 2 + ((crosshair_y - head_y) / hh_rad) ** 2
        is_on_head = norm_head_sq <= 1.45

        x1 = target["x1"] + lead_x
        y1 = target["y1"] + lead_y
        x2 = target["x2"] + lead_x
        y2 = target["y2"] + lead_y
        is_on_body = (x1 <= crosshair_x <= x2) and (y1 <= crosshair_y <= y2)

        if head_only:
            if not is_on_head:
                return None
        else:
            if not is_on_body:
                return None

        # 2. Timing and Mode control
        mode = str(self.config.get("makcu_triggerbot_mode", "tap")).lower()
        shot_delay = max(0.02, float(self.config.get("makcu_triggerbot_delay_ms", 35)) / 1000.0)

        if now - self.last_trigger_time < shot_delay:
            return None

        self.last_trigger_time = now

        # Update burst / cooldown counters
        if mode == "tap":
            reset_pause = max(0.08, float(self.config.get("makcu_triggerbot_recoil_delay_ms", 180)) / 1000.0)
            self.burst_cooldown_until = now + reset_pause
            self.trigger_burst_count = 0
        elif mode == "burst":
            self.trigger_burst_count = getattr(self, "trigger_burst_count", 0) + 1
            max_burst = int(self.config.get("makcu_triggerbot_burst_shots", 2))
            if self.trigger_burst_count >= max_burst:
                reset_pause = max(0.10, float(self.config.get("makcu_triggerbot_recoil_delay_ms", 220)) / 1000.0)
                self.burst_cooldown_until = now + reset_pause
                self.trigger_burst_count = 0
        else:
            self.trigger_burst_count = 0

        return b"km.left(1)\r\nkm.left(0)\r\n"

    def test_move(self):
        """Send a subtle test wiggle to verify MAKCU hardware response."""
        # Wait briefly for initial async background connect if in progress
        t0 = time.time()
        while not self.is_connected and time.time() - t0 < 1.5:
            time.sleep(0.05)

        if not self.is_connected or not self.controller:
            if not self.connect():
                return False
        try:
            self.controller.move(12, 0)
            time.sleep(0.04)
            self.controller.move(-12, 0)
            return True
        except Exception as e:
            print(f"[MAKCU] Test move failed: {e}")
            return False

    def get_state(self):
        """Thread-safe state snapshot for UI and Overlay."""
        with self._lock:
            return {
                "is_connected": self.is_connected,
                "port": self.port,
                "is_aiming": self.is_aiming,
                "has_lock": self.target_locked is not None,
                "is_mouse_locked": self._mouse_locked,
                "locked_target": dict(self.target_locked) if self.target_locked else None,
            }
