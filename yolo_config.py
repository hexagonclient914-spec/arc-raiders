"""
ARC Raiders YOLO Tactical Vision HUD - Configuration Manager
"""

import json
import os

DEFAULT_YOLO_CONFIG = {
    # Detection Engine Settings
    "enabled": True,
    "model_path": "battlefield_2042.onnx",
    "device": "cuda:0",               # "cuda:0" or "cpu"
    "confidence_threshold": 0.42,      # 0.10 - 0.95
    "iou_threshold": 0.45,             # NMS IoU threshold
    "detect_all_classes": True,        # True to detect all 13 ARC Raiders classes
    "target_classes": [0],             # COCO 0 = person / player
    "scan_region_mode": "center_640",  # "center_480", "center_640", "center_960", "fullscreen"
    "dynamic_combat_zoom": True,       # Sub-2ms high-FPS dynamic ROI zoom when engaging targets
    "combat_zoom_size": 384,           # Crop size in pixels during active combat (320 or 384)
    "use_half_precision": True,        # FP16 on NVIDIA RTX GPUs for extreme speed
    "max_fps": 300,

    # Overlay Visual Appearance
    "headless_mode": False,            # True to disable all on-screen overlay rendering
    "streamer_mode": True,             # Hide HUD from OBS, Discord screenshare & Medal clips
    "show_boxes": True,                # True to draw bounding boxes around enemies
    "overlay_opacity": 0.95,
    "box_style": "corners",            # "corners", "box", "glow"
    "box_thickness": 2,
    "corner_length": 14,
    "enemy_color": "#FF3355",          # Neon Red/Crimson for enemies
    "closest_color": "#00FFCC",        # Neon Cyan for closest locked enemy
    "text_color": "#FFFFFF",
    "show_labels": True,
    "show_confidence": True,
    "show_distance": True,
    "show_snaplines": True,            # Tracer line to nearest target
    "snapline_origin": "bottom",       # "bottom" or "center"
    "show_closest_indicator": True,    # Distinct reticle/badge on closest threat
    "show_scan_zone": True,            # Visual boundary of the active scanning area
    "scan_zone_color": "#00FFCC",
    "show_hud_stats": True,            # Top corner FPS, targets & latency display
    "show_crosshair": True,
    "crosshair_size": 4,
    "crosshair_color": "#00FFCC",
    "on_target_crosshair": True,       # Dynamic on-target crosshair color shift & lock pulse
    "on_target_color": "#FFE600",      # Neon Gold when aimed directly at an enemy
    "ghost_tracking": True,            # Occlusion tracking: maintain ghost box behind cover
    "ghost_duration": 1.5,             # Seconds ghost box persists after losing direct line of sight

    # Visual Enhancements & Headshot Precision
    "show_head_marker": True,          # Precision golden diamond on enemy head level
    "head_marker_color": "#FFE600",    # Neon Gold for headshot diamond
    "box_smoothing": True,             # Anti-jitter Exponential Moving Average (EMA)
    "box_smoothing_factor": 0.65,      # 0.2 (ultra smooth) to 0.9 (instant raw)
    "adaptive_smoothing": True,        # Velocity-adaptive One-Euro smoothing (eliminates micro-jitter)
    "stance_detection": True,          # Detect standing vs crouching for exact head height
    "latency_compensation": True,      # Sub-frame latency compensation (leads moving targets)
    "agnostic_nms": True,              # Agnostic NMS to eliminate overlapping double boxes
    "active_game_profile": "valorant", # "valorant", "cs2", "arc_raiders", "custom"

    # Hotkeys & Audio Feedback
    "hotkey_toggle_engine": "c",       # Global on/off toggle hotkey
    "hotkey_toggle_overlay": "f7",
    "hotkey_toggle_settings": "f8",
    "hotkey_sound": True,              # Audible dual-tone beep on hotkey toggle
    "auto_eco_mode": True,             # Auto-throttle when desktop idle
    "high_process_priority": True,     # Boost Windows process & thread priority for stable frametimes

    # MAKCU Hardware Aim Assist
    "makcu_enabled": True,             # Enable/Disable hardware aim assist
    "makcu_port": "auto",              # "auto" or specific COM port (e.g. "COM19")
    "makcu_aim_key": "rmb",            # "rmb", "lalt", "xbutton1", "xbutton2", "lshift", "ctrl", "always"
    "makcu_fov": 160,                  # Aim Assist FOV radius in pixels around crosshair
    "makcu_smooth": 4.5,               # Smoothing divisor (1.0 = instant snap, 10.0 = very smooth/legit)
    "makcu_target_bone": "head",       # "head", "neck", "chest", "center"
    "makcu_prediction": True,          # Lead moving targets based on target velocity
    "makcu_show_fov": True,            # Draw circular FOV reticle on overlay
    "makcu_triggerbot": False,                 # Auto-shoot when crosshair is directly on target
    "makcu_triggerbot_delay_ms": 35,           # Triggerbot click interval in ms
    "makcu_triggerbot_head_only": True,        # Only fire when crosshair is directly on head
    "makcu_triggerbot_mode": "tap",            # "tap" (1-tap reset), "burst" (2-shot), "auto"
    "makcu_triggerbot_burst_shots": 2,         # Number of shots in burst mode
    "makcu_triggerbot_recoil_delay_ms": 180,   # Wait time after tap/burst for weapon recoil reset
    "makcu_triggerbot_stop_to_shoot": True,    # Only fire when standing still (no WASD movement / counter-strafe)
    "makcu_triggerbot_snap_check": True,       # Suppress firing during fast aiming snaps until reticle settles
    "makcu_trigger_on_lock_only": True,        # True = Triggerbot only fires when crosshair is firmly on target
    "makcu_trigger_tolerance": 5,              # Max pixel distance from crosshair to aim target to allow firing (2-15 px)
    "makcu_trigger_lock_delay_ms": 25,         # Milliseconds crosshair must settle on target before firing
    "makcu_lock_on_target": False,             # Hardware-level physical mouse freeze when reticle is on target
    "linear_head_snap": True,                  # True = Direct snap onto head center with zero braking
    "head_decel_strength": 0,                  # 0% = Pure linear (no deceleration), 100% = Maximum landing brake
    "head_hysteresis_lock": False,             # False = Never freeze mouse before reaching head center
    "makcu_lead_time_ms": 55,                  # Advance prediction lead in milliseconds on running targets (20-120 ms)
    "velocity_feedforward": True,              # Feedforward speed matching: eliminates trailing behind running targets
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolo_config.json")


class YOLOConfig:
    def __init__(self):
        self.data = dict(DEFAULT_YOLO_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception as e:
                print(f"[YOLOConfig] Error loading config, using defaults: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"[YOLOConfig] Error saving config: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()
