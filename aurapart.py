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
        self.head_lock_active = False
        self.acc_x = 0.0
        self.acc_y = 0.0
        self.smooth_vx = 0.0
        self.smooth_vy = 0.0
        self.last_move_time = 0.0
        self.last_trigger_time = 0.0
        self.trigger_burst_count = 0
        self.burst_cooldown_until = 0.0
        self.target_lock_start_time = 0.0
        self.last_process_time = time.perf_counter()
        self._running = True

        # Auto-connect and continuous background watchdog to ensure 100% connection uptime
        self._watchdog_thread = threading.Thread(target=self._connection_watchdog, daemon=True)
        self._watchdog_thread.start()

    def _connection_watchdog(self):
        """Continuously ensure MAKCU hardware is connected, responsive and healthy."""
        while getattr(self, "_running", True):
            try:
                needs_connect = False
                with self._lock:
                    if not self.is_connected or not self.controller:
                        needs_connect = True
                    elif hasattr(self.controller, "is_connected") and not self.controller.is_connected():
                        needs_connect = True
                if needs_connect:
                    self.connect()
            except Exception:
                pass
            time.sleep(2.0)

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
            self.smooth_vx = 0.0
            self.smooth_vy = 0.0
            self._set_hardware_mouse_lock(False)
            return

        if not targets:
            self.is_aiming = False
            self.target_locked = None
            self.smooth_vx = 0.0
            self.smooth_vy = 0.0
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
            self.smooth_vx = 0.0
            self.smooth_vy = 0.0
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
        target_vel = 0.0
        tv_x = 0.0
        tv_y = 0.0
        if ("vx" in best_target) and ("vy" in best_target):
            tv_x = float(best_target.get("vx", 0.0))
            tv_y = float(best_target.get("vy", 0.0))
            raw_vel = math.hypot(tv_x, tv_y)

            # Smooth velocity with Exponential Moving Average (EMA) to prevent camera optical flow feedback jitter
            if raw_vel < 20.0:
                self.smooth_vx *= 0.50
                self.smooth_vy *= 0.50
            else:
                if abs(self.smooth_vx) < 5.0 and abs(self.smooth_vy) < 5.0:
                    self.smooth_vx = tv_x * 0.65
                    self.smooth_vy = tv_y * 0.65
                else:
                    self.smooth_vx = 0.65 * self.smooth_vx + 0.35 * tv_x
                    self.smooth_vy = 0.65 * self.smooth_vy + 0.35 * tv_y

            smooth_speed = math.hypot(self.smooth_vx, self.smooth_vy)
            target_vel = smooth_speed

            # Single stable lead calculation strictly in aurapart.py
            if smooth_speed > 20.0 and bool(self.config.get("makcu_prediction", True)):
                lead_ms = float(self.config.get("makcu_lead_time_ms", 45.0))
                lead_dt = max(0.015, min(0.065, lead_ms / 1000.0))
                lead_x = self.smooth_vx * lead_dt
                lead_y = self.smooth_vy * lead_dt

                # Generous safety clamp based on enemy dimensions
                max_lead_x = max(14.0, min(26.0, float(best_target.get("w", 30)) * 0.75))
                max_lead_y = max(8.0, min(16.0, float(best_target.get("h", 60)) * 0.35))
                lead_x = max(-max_lead_x, min(max_lead_x, lead_x))
                lead_y = max(-max_lead_y, min(max_lead_y, lead_y))

                delta_x += lead_x
                delta_y += lead_y
        else:
            self.smooth_vx *= 0.50
            self.smooth_vy *= 0.50

        # Deceleration & Linear Snap Configuration
        linear_snap = bool(self.config.get("linear_head_snap", True))
        decel_strength = int(self.config.get("head_decel_strength", 0))  # 0 to 100%
        use_hysteresis = bool(self.config.get("head_hysteresis_lock", False))

        # -----------------------------------------------------------------
        # ANTI-JITTER HEAD HYSTERESIS & MICRO-LOCK (Optional)
        # -----------------------------------------------------------------
        if use_hysteresis and not linear_snap:
            head_radius = max(3.0, float(best_target.get("head_w", 14.0)) * 0.25)
            
            # Hysteresis: lock firmly inside radius, require clear separation to unlock
            if dist_px <= head_radius:
                self.head_lock_active = True
            elif dist_px > head_radius * 1.5:
                self.head_lock_active = False

            if self.head_lock_active:
                # We are firmly on the head: lock mouse in place and wipe fractional accumulations
                self.acc_x = 0.0
                self.acc_y = 0.0
                move_x = 0
                move_y = 0

                # Gentle smooth tracking only if enemy is actively running (> 30 px/s)
                if ("vx" in best_target) and ("vy" in best_target):
                    tv_x = best_target.get("vx", 0.0)
                    tv_y = best_target.get("vy", 0.0)
                    if math.hypot(tv_x, tv_y) > 30.0:
                        step_x = (delta_x + tv_x * 0.020) * 0.25
                        step_y = (delta_y + tv_y * 0.020) * 0.25
                        move_x = int(round(step_x))
                        move_y = int(round(step_y))

                click_cmd = self._evaluate_triggerbot(
                    best_target, crosshair_x, crosshair_y,
                    move_dist=0.0, lead_x=0.0, lead_y=0.0,
                    dist_to_aim=dist_px, is_aiming=True,
                    bone_mode=bone_mode
                )
                if move_x != 0 or move_y != 0 or click_cmd:
                    try:
                        if move_x != 0 or move_y != 0:
                            self.controller.move(move_x, move_y)
                        if click_cmd:
                            if MouseButton:
                                self.controller.click(MouseButton.LEFT)
                            else:
                                tr = getattr(self.controller, "transport", None)
                                if tr:
                                    tr.send_command("km.left(1)\r\nkm.left(0)")
                    except Exception:
                        pass
                return
        else:
            self.head_lock_active = False

        # -------------------------------------------------------------
        # SPEED & TRAJECTORY CALCULATION (Linear Snap vs Deceleration Curve)
        # -----------------------------------------------------------------
        snap_smooth = max(1.0, smooth)

        # Dynamic Speed Boost (Velocity Tracking):
        # Gracefully reduce smoothing resistance on running enemies so the crosshair never trails behind,
        # but WITHOUT direct velocity step addition to guarantee zero optical-flow flutter or over-oscillation.
        feedforward_active = bool(self.config.get("velocity_feedforward", True))
        if feedforward_active and target_vel > 20.0:
            speed_ratio = min(1.8, target_vel / 150.0)
            snap_smooth = max(1.0, snap_smooth / (1.0 + speed_ratio * 0.60))

        if linear_snap or decel_strength <= 0:
            # 100% Pure Linear Snap
            step_x = delta_x / snap_smooth
            step_y = delta_y / snap_smooth
            max_step = 65.0
        else:
            # Distance-adaptive curve scaled by user deceleration strength (0% = none, 100% = full)
            ratio = decel_strength / 100.0
            dist_factor = min(2.5, max(0.85, dist_px / 35.0))
            curve_factor = 1.0 + ratio * ((1.0 / dist_factor) - 1.0)
            curve_smooth = max(1.0, snap_smooth * 0.75 * curve_factor)
            step_x = delta_x / curve_smooth
            step_y = delta_y / curve_smooth
            max_step = 50.0

        step_x = max(-max_step, min(max_step, step_x))
        step_y = max(-max_step, min(max_step, step_y))

        # Fractional Sub-Pixel Accumulator (prevents 1-pixel rounding twitching)
        self.acc_x += step_x
        self.acc_y += step_y
        move_x = int(self.acc_x)
        move_y = int(self.acc_y)
        self.acc_x -= move_x
        self.acc_y -= move_y

        # Check triggerbot in the same frame (with lead prediction included!)
        move_dist = math.hypot(move_x, move_y)
        click_cmd = self._evaluate_triggerbot(
            best_target, crosshair_x, crosshair_y,
            move_dist=move_dist, lead_x=lead_x, lead_y=lead_y,
            dist_to_aim=dist_px, is_aiming=self.is_aiming,
            bone_mode=bone_mode
        )

        # Feature 7: Zero-Latency Batched Serial Pipeline
        # Fuses move + click into a single atomic byte packet to halve USB bus latency
        if move_x != 0 or move_y != 0 or click_cmd:
            try:
                if move_x != 0 or move_y != 0:
                    self.controller.move(move_x, move_y)
                if click_cmd:
                    if MouseButton:
                        self.controller.click(MouseButton.LEFT)
                    else:
                        tr = getattr(self.controller, "transport", None)
                        if tr:
                            tr.send_command("km.left(1)\r\nkm.left(0)")
            except Exception as e:
                try:
                    if not self.controller.is_connected():
                        with self._lock:
                            self.is_connected = False
                except Exception:
                    with self._lock:
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

    def _evaluate_triggerbot(self, target, crosshair_x, crosshair_y, move_dist=0.0, lead_x=0.0, lead_y=0.0, dist_to_aim=None, is_aiming=False, bone_mode="head"):
        """
        Evaluate triggerbot conditions and return direct byte command if ready to fire.
        Prevents premature firing before the aimbot has locked onto the target!
        """
        if not self.config.get("makcu_triggerbot", False):
            self.trigger_burst_count = 0
            self.target_lock_start_time = 0.0
            return None

        # Counter-Strafing / Stillness Check: Don't shoot while moving
        if bool(self.config.get("makcu_triggerbot_stop_to_shoot", True)):
            if self._is_moving():
                self.target_lock_start_time = 0.0
                return None

        now = time.time()
        if now < getattr(self, "burst_cooldown_until", 0.0):
            return None

        # 1. Lock-Before-Fire Check: When aimbot is aiming, NEVER fire before crosshair reaches target!
        lock_on_aim = bool(self.config.get("makcu_trigger_on_lock_only", True))
        max_tolerance = float(self.config.get("makcu_trigger_tolerance", 5.0))

        if is_aiming and lock_on_aim:
            if dist_to_aim is not None and dist_to_aim > max_tolerance:
                self.target_lock_start_time = 0.0
                return None

        # 2. Aim Snap Check: Don't shoot while the aimbot is actively moving / snapping (> 2.5 px/frame)
        if bool(self.config.get("makcu_triggerbot_snap_check", True)):
            if move_dist > 2.5:
                self.target_lock_start_time = 0.0
                return None

        # 3. Hit Validation (Strict Head Ellipse vs Full-body)
        head_only = bool(self.config.get("makcu_triggerbot_head_only", True)) or (bone_mode == "head" and lock_on_aim)

        # Include real-time motion lead in hit evaluation so running targets are validated accurately
        head_x = target.get("head_cx", target["cx"]) + lead_x
        head_y = target.get("head_cy", target["y1"] + target["h"] * 0.11) + lead_y
        hw_rad = max(4.0, target.get("head_w", 12.0) / 2.0)
        hh_rad = max(4.0, target.get("head_h", 14.0) / 2.0)
        norm_head_sq = ((crosshair_x - head_x) / hw_rad) ** 2 + ((crosshair_y - head_y) / hh_rad) ** 2
        is_on_head = norm_head_sq <= 1.15  # Strict head radius verification

        x1 = target["x1"] + lead_x
        y1 = target["y1"] + lead_y
        x2 = target["x2"] + lead_x
        y2 = target["y2"] + lead_y
        is_on_body = (x1 <= crosshair_x <= x2) and (y1 <= crosshair_y <= y2)

        if head_only:
            if not is_on_head:
                self.target_lock_start_time = 0.0
                return None
        else:
            if not is_on_body:
                self.target_lock_start_time = 0.0
                return None

        # 4. Lock Duration / Pre-Fire Settling Delay (ms)
        lock_delay_s = max(0.0, float(self.config.get("makcu_trigger_lock_delay_ms", 25)) / 1000.0)
        if lock_delay_s > 0:
            if getattr(self, "target_lock_start_time", 0.0) <= 0.0:
                self.target_lock_start_time = now
                return None
            elif (now - self.target_lock_start_time) < lock_delay_s:
                return None
        else:
            self.target_lock_start_time = now

        # 5. Timing and Mode Control
        mode = str(self.config.get("makcu_triggerbot_mode", "tap")).lower()
        shot_delay = max(0.015, float(self.config.get("makcu_triggerbot_delay_ms", 25)) / 1000.0)

        if now - self.last_trigger_time < shot_delay:
            return None

        self.last_trigger_time = now

        # Update burst / cooldown counters
        if mode == "tap":
            reset_pause = max(0.08, float(self.config.get("makcu_triggerbot_recoil_delay_ms", 180)) / 1000.0)
            self.burst_cooldown_until = now + reset_pause
            self.trigger_burst_count = 0
            self.target_lock_start_time = 0.0
        elif mode == "burst":
            self.trigger_burst_count = getattr(self, "trigger_burst_count", 0) + 1
            max_burst = int(self.config.get("makcu_triggerbot_burst_shots", 2))
            if self.trigger_burst_count >= max_burst:
                reset_pause = max(0.10, float(self.config.get("makcu_triggerbot_recoil_delay_ms", 220)) / 1000.0)
                self.burst_cooldown_until = now + reset_pause
                self.trigger_burst_count = 0
                self.target_lock_start_time = 0.0
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
