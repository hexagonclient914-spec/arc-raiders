"""
ARC Raiders Sound Overlay - Configuration Manager (v3.0)
"""

import json
import os

DEFAULT_CONFIG = {
    "overlay_mode": "radar",       # "radar", "edge", "bar", "all"
    "gain": 3.0,                  # Audio amplification multiplier (1.0 - 8.0)
    "noise_threshold": 0.002,     # Ambient noise cut-off threshold
    "hold_duration": 0.9,         # Threat icon persistence on screen (seconds)
    "stereo_boost": 1.4,          # Panning separation multiplier (1.0 - 2.5)
    "overlay_size": 220,          # Size of radar compass in pixels
    "overlay_opacity": 0.90,      # Global opacity (0.1 - 1.0)
    "y_offset": 0,                # Vertical offset from screen center
    "show_crosshair": True,       # Center crosshair dot
    "crosshair_size": 4,          # Crosshair dot size in px
    "crosshair_color": "#00FFCC", # Crosshair hex color
    "footstep_color": "#FF8800",  # Amber/Orange for footsteps
    "gunshot_color": "#00E5FF",   # Cyan for gunshots / ARC machines
    "general_color": "#EEEEEE",   # Neutral sound color
    "hotkey_toggle": "f9",        # Hotkey to hide/show overlay
    "hotkey_settings": "f10",     # Hotkey to open settings window
    "device_index": None          # Audio loopback device index (None = auto default)
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

class Config:
    def __init__(self):
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception as e:
                print(f"Error loading config, using defaults: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()
