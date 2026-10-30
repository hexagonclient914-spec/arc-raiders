"""
ARC Raiders Sound Overlay - Settings Window (Control Panel v3.0)
Multi-Threat Visualizer Settings with Hold Time, Stereo Boost, Device Selector, & Test Triggers.
"""

import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, 
    QCheckBox, QPushButton, QGroupBox, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

class SettingsWindow(QWidget):
    def __init__(self, audio_engine, config, overlay_window):
        super().__init__()
        self.audio_engine = audio_engine
        self.config = config
        self.overlay_window = overlay_window

        self.setWindowTitle("ARC Raiders - Tactical Sound Radar v3.0")
        self.setFixedSize(540, 800)
        self.setStyleSheet("""
            QWidget {
                background-color: #121418;
                color: #DDE2E8;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #2A303C;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 12px;
                font-weight: bold;
                color: #FF9900;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QLabel {
                color: #B5BDC8;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #222731;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #FF8800;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00E5FF;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #73F7FF;
            }
            QComboBox {
                background-color: #1A1F29;
                border: 1px solid #363E4D;
                border-radius: 5px;
                padding: 6px 12px;
                color: #FFFFFF;
            }
            QComboBox::drop-down {
                border: none;
            }
            QCheckBox {
                color: #DDE2E8;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #363E4D;
                background-color: #1A1F29;
            }
            QCheckBox::indicator:checked {
                background-color: #FF8800;
                border-color: #FFA534;
            }
            QPushButton {
                background-color: #1E2530;
                border: 1px solid #3A4454;
                border-radius: 6px;
                padding: 8px 16px;
                color: #FFFFFF;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2D3747;
                border-color: #00E5FF;
                color: #00E5FF;
            }
            QProgressBar {
                border: 1px solid #28303C;
                border-radius: 4px;
                background-color: #161A22;
                text-align: center;
                height: 12px;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #FF8800;
                border-radius: 3px;
            }
        """)

        self.init_ui()

        self.meter_timer = QTimer(self)
        self.meter_timer.timeout.connect(self.update_meters)
        self.meter_timer.start(33)

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(10)

        title_label = QLabel("⚡ ARC RAIDERS - TACTICAL SOUND RADAR v3.0")
        title_label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #FF9900; letter-spacing: 1px;")
        main_layout.addWidget(title_label)

        sub_label = QLabel("Fortnite/Sonic Radar Style: Multi-Threat Tracking mit 👣 Schritten & 💥 Schüssen")
        sub_label.setStyleSheet("color: #7B8594; font-size: 11px;")
        main_layout.addWidget(sub_label)

        # 1. Device Selection
        dev_group = QGroupBox("AUDIO-AUSGABEGERÄT (WASAPI LOOPBACK)")
        dev_layout = QVBoxLayout()
        self.dev_combo = QComboBox()
        self.dev_combo.addItem("🔄 Automatisch (Windows Standard-Ausgabe)", None)
        
        devices = self.audio_engine.get_output_devices()
        cur_dev = self.config.get("device_index", None)
        selected_combo_idx = 0

        for i, d in enumerate(devices):
            label = f"{d['name']} ({d['channels']} Kanäle)"
            self.dev_combo.addItem(label, d["index"])
            if cur_dev is not None and d["index"] == cur_dev:
                selected_combo_idx = i + 1

        self.dev_combo.setCurrentIndex(selected_combo_idx)
        self.dev_combo.currentIndexChanged.connect(self.on_device_changed)
        dev_layout.addWidget(self.dev_combo)
        dev_group.setLayout(dev_layout)
        main_layout.addWidget(dev_group)

        # 2. Display Mode
        mode_group = QGroupBox("ANZEIGE-MODUS")
        mode_layout = QVBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🎯 Radar Kompass (Mitte)", "radar")
        self.mode_combo.addItem("✨ Bildschirm-Ränder Glow (Edge Glow)", "edge")
        self.mode_combo.addItem("📊 Taktische Sound-Leiste (Bottom Bar)", "bar")
        self.mode_combo.addItem("🔥 Kombination (Radar + Edge Glow)", "all")

        current_mode = self.config.get("overlay_mode", "radar")
        idx = self.mode_combo.findData(current_mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)

        # 3. Tuning & Persistence
        audio_group = QGroupBox("ORTUNG & PERSISTENZ (HOLD TIME)")
        audio_layout = QVBoxLayout()

        # Hold Duration Slider
        hold_box = QHBoxLayout()
        hold_box.addWidget(QLabel("Anzeige-Dauer (Hold Time):"))
        self.hold_val_lbl = QLabel(f"{self.config.get('hold_duration', 0.95):.2f}s")
        self.hold_val_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        hold_box.addStretch()
        hold_box.addWidget(self.hold_val_lbl)
        audio_layout.addLayout(hold_box)

        self.hold_slider = QSlider(Qt.Orientation.Horizontal)
        self.hold_slider.setRange(40, 200) # 0.4s to 2.0s
        self.hold_slider.setValue(int(self.config.get("hold_duration", 0.95) * 100))
        self.hold_slider.valueChanged.connect(self.on_hold_changed)
        audio_layout.addWidget(self.hold_slider)

        # Stereo Boost Slider
        boost_box = QHBoxLayout()
        boost_box.addWidget(QLabel("Stereo-Trennung (Separation Boost):"))
        self.boost_val_lbl = QLabel(f"{self.config.get('stereo_boost', 1.4):.1f}x")
        self.boost_val_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        boost_box.addStretch()
        boost_box.addWidget(self.boost_val_lbl)
        audio_layout.addLayout(boost_box)

        self.boost_slider = QSlider(Qt.Orientation.Horizontal)
        self.boost_slider.setRange(10, 25) # 1.0x to 2.5x
        self.boost_slider.setValue(int(self.config.get("stereo_boost", 1.4) * 10))
        self.boost_slider.valueChanged.connect(self.on_boost_changed)
        audio_layout.addWidget(self.boost_slider)

        # Gain Slider
        gain_box = QHBoxLayout()
        gain_box.addWidget(QLabel("Verstärkung (Gain):"))
        self.gain_val_lbl = QLabel(f"{self.config.get('gain', 3.0):.1f}x")
        self.gain_val_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        gain_box.addStretch()
        gain_box.addWidget(self.gain_val_lbl)
        audio_layout.addLayout(gain_box)

        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(10, 80)
        self.gain_slider.setValue(int(self.config.get("gain", 3.0) * 10))
        self.gain_slider.valueChanged.connect(self.on_gain_changed)
        audio_layout.addWidget(self.gain_slider)

        # Live Meters
        meter_l_box = QHBoxLayout()
        meter_l_box.addWidget(QLabel("L:"))
        self.prog_l = QProgressBar()
        self.prog_l.setRange(0, 100)
        meter_l_box.addWidget(self.prog_l)
        audio_layout.addLayout(meter_l_box)

        meter_r_box = QHBoxLayout()
        meter_r_box.addWidget(QLabel("R:"))
        self.prog_r = QProgressBar()
        self.prog_r.setRange(0, 100)
        meter_r_box.addWidget(self.prog_r)
        audio_layout.addLayout(meter_r_box)

        audio_group.setLayout(audio_layout)
        main_layout.addWidget(audio_group)

        # 4. Visuals
        visual_group = QGroupBox("VISUELLE EINSTELLUNGEN")
        vis_layout = QVBoxLayout()

        size_box = QHBoxLayout()
        size_box.addWidget(QLabel("Radar-Größe:"))
        self.size_val_lbl = QLabel(f"{self.config.get('overlay_size', 220)} px")
        self.size_val_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        size_box.addStretch()
        size_box.addWidget(self.size_val_lbl)
        vis_layout.addLayout(size_box)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(120, 360)
        self.size_slider.setValue(self.config.get("overlay_size", 220))
        self.size_slider.valueChanged.connect(self.on_size_changed)
        vis_layout.addWidget(self.size_slider)

        self.crosshair_chk = QCheckBox("Fadenkreuz-Punkt im Zentrum anzeigen")
        self.crosshair_chk.setChecked(self.config.get("show_crosshair", True))
        self.crosshair_chk.toggled.connect(self.on_crosshair_toggled)
        vis_layout.addWidget(self.crosshair_chk)

        visual_group.setLayout(vis_layout)
        main_layout.addWidget(visual_group)

        # 5. Live Test Triggers
        test_group = QGroupBox("RICHTUNGEN TESTEN (SOFORT-CHECK)")
        test_layout = QHBoxLayout()

        btn_left = QPushButton("⬅️ Links")
        btn_left.clicked.connect(lambda: self.trigger_test_threat("left"))
        test_layout.addWidget(btn_left)

        btn_front = QPushButton("⬆️ Vorne")
        btn_front.clicked.connect(lambda: self.trigger_test_threat("front"))
        test_layout.addWidget(btn_front)

        btn_right = QPushButton("Rechts ➡️")
        btn_right.clicked.connect(lambda: self.trigger_test_threat("right"))
        test_layout.addWidget(btn_right)

        btn_rear = QPushButton("⬇️ Hinten")
        btn_rear.clicked.connect(lambda: self.trigger_test_threat("rear"))
        test_layout.addWidget(btn_rear)

        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)

        # Bottom Bar
        bottom_layout = QHBoxLayout()
        btn_toggle_overlay = QPushButton("Overlay Ein/Aus [F9]")
        btn_toggle_overlay.setStyleSheet("background-color: #FF8800; color: #000000; font-weight: bold;")
        btn_toggle_overlay.clicked.connect(self.toggle_overlay)
        bottom_layout.addWidget(btn_toggle_overlay)

        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

    def on_device_changed(self):
        dev_idx = self.dev_combo.currentData()
        self.config.set("device_index", dev_idx)
        self.audio_engine.stop()
        self.audio_engine.start(device_index=dev_idx)

    def on_mode_changed(self):
        mode = self.mode_combo.currentData()
        self.config.set("overlay_mode", mode)

    def on_hold_changed(self, val):
        hd = val / 100.0
        self.hold_val_lbl.setText(f"{hd:.2f}s")
        self.config.set("hold_duration", hd)
        self.audio_engine.hold_duration = hd

    def on_boost_changed(self, val):
        b = val / 10.0
        self.boost_val_lbl.setText(f"{b:.1f}x")
        self.config.set("stereo_boost", b)
        self.audio_engine.stereo_boost = b

    def on_gain_changed(self, val):
        gain = val / 10.0
        self.gain_val_lbl.setText(f"{gain:.1f}x")
        self.config.set("gain", gain)
        self.audio_engine.gain = gain

    def on_size_changed(self, val):
        self.size_val_lbl.setText(f"{val} px")
        self.config.set("overlay_size", val)

    def on_crosshair_toggled(self, checked):
        self.config.set("show_crosshair", checked)

    def toggle_overlay(self):
        if self.overlay_window.isVisible():
            self.overlay_window.hide()
        else:
            self.overlay_window.show()

    def update_meters(self):
        state = self.audio_engine.get_state()
        lvl_l = int(state.get("level_l", 0.0) * 100)
        lvl_r = int(state.get("level_r", 0.0) * 100)
        self.prog_l.setValue(min(100, lvl_l))
        self.prog_r.setValue(min(100, lvl_r))

    def trigger_test_threat(self, mode="left"):
        """Triggers test audio and registers threat directly on HUD."""
        sr = 44100
        dur = 0.30
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        envelope = np.exp(-10 * t)

        if mode == "left":
            self.audio_engine._register_threat(-80.0, "footstep", 0.90, "close")
            sig = 0.40 * np.sin(2 * np.pi * 180 * t) * envelope
            stereo = np.column_stack((sig, np.zeros_like(sig)))
        elif mode == "right":
            self.audio_engine._register_threat(80.0, "gunshot", 0.90, "medium")
            noise = np.random.uniform(-0.3, 0.3, len(t))
            sig = (0.35 * np.sin(2 * np.pi * 2600 * t) + noise * 0.3) * envelope
            stereo = np.column_stack((np.zeros_like(sig), sig))
        elif mode == "front":
            self.audio_engine._register_threat(0.0, "gunshot", 0.90, "close")
            sig = 0.35 * np.sin(2 * np.pi * 3200 * t) * envelope
            stereo = np.column_stack((sig, sig))
        else: # rear
            self.audio_engine._register_threat(180.0, "footstep", 0.90, "close")
            sig = 0.35 * np.sin(2 * np.pi * 120 * t) * envelope
            stereo = np.column_stack((sig, sig))

        try:
            sd.play(stereo.astype(np.float32), sr)
        except Exception:
            pass
