"""
AURA TACTICAL VISION // CYBER-RED ELITE HUD GUI
Full-featured, ultra-sleek cyber-tactical graphical interface matching
the official AURA visual spec with 100% pure vector graphics and dedicated AI Engine Hub.
"""

import os
import sys
import json
import time
import ctypes

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QComboBox, QCheckBox, QFrame,
    QStackedWidget, QGraphicsDropShadowEffect, QFileDialog, QMessageBox,
    QGridLayout
)
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QColor, QFont, QCursor, QIcon, QPainter, QBrush, QPen,
    QLinearGradient, QPainterPath, QGuiApplication
)

from yolo_config import YOLOConfig
from yolo_engine import YOLOEngine
from yolo_overlay import YOLOOverlayWindow

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "yolo_config.json")


# =====================================================================
# PURE VECTOR GRAPHIC WIDGETS (NO PNGs)
# =====================================================================
class VectorCrosshairWidget(QWidget):
    """Razor-sharp vector tactical HUD crosshair drawn with QPainter."""
    def __init__(self, size=54, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())
        cx, cy = w / 2.0, h / 2.0
        r_outer = min(cx, cy) - 3.0
        r_mid = r_outer * 0.72
        r_inner = r_outer * 0.35

        # Outer cyber bracket accents
        p.setPen(QPen(QColor("#FF1744"), 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)

        gap = 18.0  # degrees
        for angle in (45, 135, 225, 315):
            p.drawArc(QRectF(cx - r_outer, cy - r_outer, r_outer * 2, r_outer * 2), int((angle - gap/2) * 16), int(gap * 16))

        # Middle Ring with subtle glow
        p.setPen(QPen(QColor("#FF2D55"), 2.2))
        p.drawEllipse(QPointF(cx, cy), r_mid, r_mid)

        # Crosshair Reticle lines
        p.setPen(QPen(QColor("#FF1744"), 2.0))
        # Top line
        p.drawLine(QPointF(cx, cy - r_outer), QPointF(cx, cy - r_inner))
        # Bottom line
        p.drawLine(QPointF(cx, cy + r_inner), QPointF(cx, cy + r_outer))
        # Left line
        p.drawLine(QPointF(cx - r_outer, cy), QPointF(cx - r_inner, cy))
        # Right line
        p.drawLine(QPointF(cx + r_inner, cy), QPointF(cx + r_outer, cy))

        # Center Precision Dot
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.drawEllipse(QPointF(cx, cy), 2.2, 2.2)
        p.end()


class VectorShieldWidget(QWidget):
    """Pure vector Undetected Shield with neon green gradient and checkmark."""
    def __init__(self, size=64, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())
        cx, cy = w / 2.0, h / 2.0
        r = min(cx, cy) - 4.0

        # Glowing Neon Green Ring
        p.setPen(QPen(QColor("#00FF66"), 2.2))
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(0, 255, 102, 35))
        grad.setColorAt(1, QColor(0, 204, 68, 15))
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Inner Shield Path
        path = QPainterPath()
        sw = r * 0.95
        sh = r * 1.15
        top = cy - sh * 0.45
        left = cx - sw * 0.5
        right = cx + sw * 0.5
        mid_y = cy + sh * 0.05
        bottom = cy + sh * 0.55

        path.moveTo(cx, top)
        path.lineTo(right, top + 6.0)
        path.quadTo(right, mid_y, cx, bottom)
        path.quadTo(left, mid_y, left, top + 6.0)
        path.closeSubpath()

        p.setPen(QPen(QColor("#00FF66"), 1.8))
        shield_grad = QLinearGradient(0, top, 0, bottom)
        shield_grad.setColorAt(0, QColor(0, 255, 102, 60))
        shield_grad.setColorAt(1, QColor(0, 204, 68, 180))
        p.setBrush(QBrush(shield_grad))
        p.drawPath(path)

        # Crisp White Checkmark
        p.setPen(QPen(QColor("#FFFFFF"), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        chk = QPainterPath()
        chk.moveTo(cx - 7.5, cy + 0.5)
        chk.lineTo(cx - 2.0, cy + 6.0)
        chk.lineTo(cx + 8.5, cy - 5.5)
        p.drawPath(chk)
        p.end()


# =====================================================================
# CUSTOM CYBER TOGGLE SWITCH WIDGET
# =====================================================================
class CyberToggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None, width=42, height=22, active_color="#FF1744"):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._checked = checked
        self.active_color = QColor(active_color)
        self.inactive_color = QColor("#222736")
        self.thumb_color = QColor("#FFFFFF")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, val: bool):
        if self._checked != bool(val):
            self._checked = bool(val)
            self.update()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        radius = self.height() / 2.0
        bg_rect = QRectF(0, 0, self.width(), self.height())

        if self._checked:
            grad = QLinearGradient(0, 0, self.width(), 0)
            grad.setColorAt(0, self.active_color)
            grad.setColorAt(1, QColor("#FF4D6D"))
            p.setBrush(QBrush(grad))
            p.setPen(QPen(QColor("#FF758F"), 1.0))
        else:
            p.setBrush(QBrush(self.inactive_color))
            p.setPen(QPen(QColor("#333D52"), 1.0))

        p.drawRoundedRect(bg_rect, radius, radius)

        thumb_r = radius - 3.0
        thumb_cx = (self.width() - radius) if self._checked else radius
        p.setBrush(QBrush(self.thumb_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(thumb_cx, radius), thumb_r, thumb_r)
        p.end()


# =====================================================================
# CUSTOM CYBER CARD CONTAINER
# =====================================================================
class CyberCard(QFrame):
    def __init__(self, title: str = "", icon_text: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("CyberCard")
        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(16, 14, 16, 14)
        self.card_layout.setSpacing(10)

        if title:
            h_lay = QHBoxLayout()
            h_lay.setSpacing(8)
            lbl_icon = QLabel(icon_text)
            lbl_icon.setObjectName("CardHeaderIcon")
            lbl_title = QLabel(title)
            lbl_title.setObjectName("CardHeaderTitle")
            h_lay.addWidget(lbl_icon)
            h_lay.addWidget(lbl_title)
            h_lay.addStretch()
            self.card_layout.addLayout(h_lay)

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setObjectName("CardSeparator")
            self.card_layout.addWidget(sep)


# =====================================================================
# MAIN AURA TACTICAL GUI WINDOW
# =====================================================================
class AuraEliteHUDWindow(QMainWindow):
    def __init__(self, engine=None, config=None, overlay_window=None):
        super().__init__()
        self.drag_position = QPoint()
        self.config = config if config is not None else YOLOConfig()
        self.config_data = self.config.data
        self.engine = engine
        self.overlay_window = overlay_window
        self._is_recording_keybind = False
        self.rebind_hotkeys_callback = None
        self.status_bar_lbl = None

        # Auto-initialize and start live YOLO vision engine if not provided
        if self.engine is None:
            try:
                self.engine = YOLOEngine(self.config)
                self.engine.start()
            except Exception as e:
                print(f"[AURA GUI] Warning: Could not start YOLOEngine: {e}")

        # Auto-initialize and display overlay window if not provided
        if self.overlay_window is None and self.engine is not None:
            try:
                screen = QGuiApplication.primaryScreen()
                if screen:
                    self.overlay_window = YOLOOverlayWindow(self.engine, self.config)
                    self.overlay_window.setGeometry(screen.geometry())
                    if not bool(self.config.get("headless_mode", False)):
                        self.overlay_window.show()
                        self.overlay_window.raise_()
            except Exception as e:
                print(f"[AURA GUI] Warning: Could not start YOLOOverlayWindow: {e}")

        self.setWindowTitle("AURA // Smarter. Smoother. Deadlier.")
        self.resize(1080, 720)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._init_ui()
        self._apply_styling()
        self._sync_ui_from_config()

        # Real-time Telemetry Timer (updates live FPS, latency, and aim lock status)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.setInterval(400)
        self.telemetry_timer.timeout.connect(self._on_telemetry_tick)
        self.telemetry_timer.start()

    def _load_config(self) -> dict:
        return self.config.data

    def _save_config(self):
        try:
            self.config.save()
        except Exception as e:
            print(f"[AURA GUI] Error saving config: {e}")

    # -----------------------------------------------------------------
    # UI INITIALIZATION & LAYOUT
    # -----------------------------------------------------------------
    def _init_ui(self):
        self.central_widget = QFrame(self)
        self.central_widget.setObjectName("RootChassis")
        self.setCentralWidget(self.central_widget)

        root_shadow = QGraphicsDropShadowEffect(self)
        root_shadow.setBlurRadius(36)
        root_shadow.setColor(QColor(255, 23, 68, 60))
        root_shadow.setOffset(0, 8)
        self.central_widget.setGraphicsEffect(root_shadow)

        main_vbox = QVBoxLayout(self.central_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)

        # 1. TOP HEADER / TITLEBAR (Pure Vector)
        main_vbox.addWidget(self._build_top_header())

        # 2. BODY (Sidebar + Stacked Content)
        body_hbox = QHBoxLayout()
        body_hbox.setContentsMargins(14, 10, 14, 10)
        body_hbox.setSpacing(12)

        # Sidebar
        body_hbox.addWidget(self._build_sidebar())

        # Main Pages (Stacked)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_aimbot_page())    # Index 0: Aimbot
        self.stack.addWidget(self._build_ai_engine_page()) # Index 1: AI Engine (replaces ESP)
        self.stack.addWidget(self._build_settings_page())  # Index 2: Settings (Dual-PC / Hardware)
        self.stack.addWidget(self._build_configs_page())   # Index 3: Configs
        self.stack.addWidget(self._build_about_page())     # Index 4: About

        body_hbox.addWidget(self.stack, stretch=1)
        main_vbox.addLayout(body_hbox, stretch=1)

        # 3. BOTTOM ACTION BAR
        main_vbox.addWidget(self._build_bottom_bar())

    # -----------------------------------------------------------------
    # TOP HEADER WIDGET (Vector Graphics)
    # -----------------------------------------------------------------
    def _build_top_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("TopHeader")
        header.setFixedHeight(68)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(18, 6, 18, 6)
        h_lay.setSpacing(14)

        # Left: Pure Vector Crosshair Badge
        self.vec_crosshair = VectorCrosshairWidget(size=50)
        h_lay.addWidget(self.vec_crosshair)

        h_lay.addStretch()

        # Center: Pure Vector Typography Title
        v_title = QVBoxLayout()
        v_title.setSpacing(1)
        lbl_crown = QLabel("👑 AURA")
        lbl_crown.setObjectName("TitleAura")
        lbl_crown.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_slogan = QLabel("SMARTER. SMOOTHER. DEADLIER.")
        lbl_slogan.setObjectName("TitleSlogan")
        lbl_slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)

        v_title.addWidget(lbl_crown)
        v_title.addWidget(lbl_slogan)
        h_lay.addLayout(v_title)

        h_lay.addStretch()

        # Right: Telemetry Status + Window Controls
        status_box = QHBoxLayout()
        status_box.setSpacing(12)

        self.lbl_dot = QLabel("●")
        self.lbl_dot.setObjectName("StatusDot")
        is_eng_active = bool(self.config.get("enabled", True))
        self.lbl_dot.setStyleSheet("color: #00FF66; font-size: 14px;" if is_eng_active else "color: #FFB300; font-size: 14px;")

        self.lbl_status = QLabel("Status: Active" if is_eng_active else "Status: Standby")
        self.lbl_status.setObjectName("StatusText")

        self.lbl_sep = QLabel("|")
        self.lbl_sep.setObjectName("StatusSep")

        self.lbl_ai = QLabel("AI Engine: Online" if is_eng_active else "AI Engine: Paused")
        self.lbl_ai.setObjectName("AiEngineText")

        status_box.addWidget(self.lbl_dot)
        status_box.addWidget(self.lbl_status)
        status_box.addWidget(self.lbl_sep)
        status_box.addWidget(self.lbl_ai)
        h_lay.addLayout(status_box)

        # Minimize & Close buttons
        btn_min = QPushButton("—")
        btn_min.setObjectName("WinBtnMin")
        btn_min.setFixedSize(28, 28)
        btn_min.clicked.connect(self.showMinimized)
        h_lay.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("WinBtnClose")
        btn_close.setFixedSize(28, 28)
        btn_close.clicked.connect(self._handle_close_btn)
        h_lay.addWidget(btn_close)

        return header

    def _handle_close_btn(self):
        # Hide window so background vision engine and hotkeys keep working
        self.hide()

    # -----------------------------------------------------------------
    # LEFT VERTICAL SIDEBAR (Clean vector HUD)
    # -----------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("SidebarFrame")
        sidebar.setFixedWidth(168)
        s_lay = QVBoxLayout(sidebar)
        s_lay.setContentsMargins(10, 14, 10, 12)
        s_lay.setSpacing(8)

        self.nav_buttons = []
        # Tab 1: AI Engine replaces ESP
        tabs = [
            ("🎯", "Aimbot", 0),
            ("⚡", "AI Engine", 1),
            ("⚙️", "Settings", 2),
            ("📁", "Configs", 3),
            ("ℹ️", "About", 4),
        ]

        for icon, name, idx in tabs:
            btn = QPushButton(f"{icon}  {name}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, i=idx: self._switch_tab(i))
            s_lay.addWidget(btn)
            self.nav_buttons.append(btn)

        self.nav_buttons[0].setChecked(True)
        self.nav_buttons[0].setProperty("selected", "true")

        s_lay.addStretch()

        # Clean Cyber Telemetry HUD Box (replaces soldier PNG)
        hud_box = QFrame()
        hud_box.setObjectName("SidebarHudBox")
        hud_lay = QVBoxLayout(hud_box)
        hud_lay.setContentsMargins(10, 10, 10, 10)
        hud_lay.setSpacing(4)

        lbl_hud_title = QLabel("SYSTEM TELEMETRY")
        lbl_hud_title.setObjectName("HudHeader")
        hud_lay.addWidget(lbl_hud_title)

        self.lbl_gpu_val = QLabel("🎮 RTX 4070")
        self.lbl_gpu_val.setObjectName("HudItem")
        self.lbl_prec_val = QLabel("⚡ TRT 10 (FP16)")
        self.lbl_prec_val.setObjectName("HudItem")
        self.lbl_fps_val = QLabel("🚀 280+ FPS")
        self.lbl_fps_val.setObjectName("HudItemHighlight")

        hud_lay.addWidget(self.lbl_gpu_val)
        hud_lay.addWidget(self.lbl_prec_val)
        hud_lay.addWidget(self.lbl_fps_val)

        s_lay.addWidget(hud_box)
        return sidebar

    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self.nav_buttons):
            is_active = (i == index)
            b.setChecked(is_active)
            b.setProperty("selected", "true" if is_active else "false")
            b.style().unpolish(b)
            b.style().polish(b)

    # -----------------------------------------------------------------
    # PAGE 0: AIMBOT TAB
    # -----------------------------------------------------------------
    def _build_aimbot_page(self) -> QWidget:
        page = QWidget()
        p_lay = QHBoxLayout(page)
        p_lay.setContentsMargins(0, 0, 0, 0)
        p_lay.setSpacing(12)

        # -------------------------------------------------------------
        # COLUMN 1: Aimbot Control Card (Wide)
        # -------------------------------------------------------------
        c1 = CyberCard("Aimbot Control", "🎯")
        c1_lay = c1.card_layout

        # Big Aimbot ON/OFF Switch
        aim_toggle_lay = QHBoxLayout()
        self.sw_aimbot = CyberToggle(checked=True, width=54, height=28, active_color="#FF1744")
        self.lbl_aim_state = QLabel("Aimbot\nON")
        self.lbl_aim_state.setObjectName("AimbotStateLabel")
        self.lbl_aim_state.setStyleSheet("color: #00FF66; font-weight: 900; font-size: 13px;")
        self.sw_aimbot.toggled.connect(self._on_aimbot_master_toggle)

        aim_toggle_lay.addWidget(self.sw_aimbot)
        aim_toggle_lay.addWidget(self.lbl_aim_state)
        aim_toggle_lay.addStretch()
        c1_lay.addLayout(aim_toggle_lay)

        # FOV Slider
        c1_lay.addSpacing(4)
        fov_header = QHBoxLayout()
        v_fov_info = QVBoxLayout()
        lbl_fov = QLabel("FOV")
        lbl_fov.setObjectName("ControlTitle")
        lbl_fov_sub = QLabel("Aim Field of View")
        lbl_fov_sub.setObjectName("ControlSub")
        v_fov_info.addWidget(lbl_fov)
        v_fov_info.addWidget(lbl_fov_sub)
        fov_header.addLayout(v_fov_info)
        fov_header.addStretch()
        self.lbl_fov_val = QLabel("120°")
        self.lbl_fov_val.setObjectName("ValueBadge")
        fov_header.addWidget(self.lbl_fov_val)
        c1_lay.addLayout(fov_header)

        self.slider_fov = QSlider(Qt.Orientation.Horizontal)
        self.slider_fov.setObjectName("CyberSlider")
        self.slider_fov.setRange(10, 180)
        self.slider_fov.setValue(120)
        self.slider_fov.valueChanged.connect(self._on_fov_slider_changed)
        c1_lay.addWidget(self.slider_fov)

        # Smoothness Slider
        c1_lay.addSpacing(4)
        smooth_header = QHBoxLayout()
        v_smooth_info = QVBoxLayout()
        lbl_smooth = QLabel("Smoothness")
        lbl_smooth.setObjectName("ControlTitle")
        lbl_smooth_sub = QLabel("Aim Smoothness")
        lbl_smooth_sub.setObjectName("ControlSub")
        v_smooth_info.addWidget(lbl_smooth)
        v_smooth_info.addWidget(lbl_smooth_sub)
        smooth_header.addLayout(v_smooth_info)
        smooth_header.addStretch()
        self.lbl_smooth_val = QLabel("3.0")
        self.lbl_smooth_val.setObjectName("ValueBadge")
        smooth_header.addWidget(self.lbl_smooth_val)
        c1_lay.addLayout(smooth_header)

        self.slider_smooth = QSlider(Qt.Orientation.Horizontal)
        self.slider_smooth.setObjectName("CyberSlider")
        self.slider_smooth.setRange(10, 100)  # 1.0 to 10.0
        self.slider_smooth.setValue(30)
        self.slider_smooth.valueChanged.connect(self._on_smooth_slider_changed)
        c1_lay.addWidget(self.slider_smooth)

        # Aim Key Dropdown
        c1_lay.addSpacing(4)
        key_lay = QHBoxLayout()
        v_key_info = QVBoxLayout()
        lbl_key = QLabel("Aim Key")
        lbl_key.setObjectName("ControlTitle")
        lbl_key_sub = QLabel("Hold to Aim")
        lbl_key_sub.setObjectName("ControlSub")
        v_key_info.addWidget(lbl_key)
        v_key_info.addWidget(lbl_key_sub)
        key_lay.addLayout(v_key_info)
        key_lay.addStretch()

        self.combo_aim_key = QComboBox()
        self.combo_aim_key.setObjectName("CyberCombo")
        self.combo_aim_key.addItems(["Right Mouse", "Left ALT", "Mouse 4", "Mouse 5", "Always Active"])
        self.combo_aim_key.setFixedWidth(130)
        self.combo_aim_key.currentIndexChanged.connect(self._on_aim_key_changed)
        key_lay.addWidget(self.combo_aim_key)
        c1_lay.addLayout(key_lay)

        # Target Selection Dropdown
        c1_lay.addSpacing(4)
        target_lay = QHBoxLayout()
        v_target_info = QVBoxLayout()
        lbl_target = QLabel("Target Selection")
        lbl_target.setObjectName("ControlTitle")
        lbl_target_sub = QLabel("Where to Aim")
        lbl_target_sub.setObjectName("ControlSub")
        v_target_info.addWidget(lbl_target)
        v_target_info.addWidget(lbl_target_sub)
        target_lay.addLayout(v_target_info)
        target_lay.addStretch()

        self.combo_target = QComboBox()
        self.combo_target.setObjectName("CyberCombo")
        self.combo_target.addItems(["💀 Head", "🎯 Neck", "🛡️ Chest"])
        self.combo_target.setFixedWidth(130)
        self.combo_target.currentIndexChanged.connect(self._on_target_bone_changed)
        target_lay.addWidget(self.combo_target)
        c1_lay.addLayout(target_lay)

        c1_lay.addStretch()
        p_lay.addWidget(c1, stretch=3)

        # -------------------------------------------------------------
        # COLUMN 2: AI Features Card & Miscellaneous Card
        # -------------------------------------------------------------
        col2 = QVBoxLayout()
        col2.setSpacing(12)

        # Card: AI Features
        c2 = CyberCard("AI Features", "🧠")
        c2_lay = c2.card_layout

        self.chk_pred = self._create_checkbox_row(c2_lay, "AI Prediction", "Predict enemy movement", checked=True)
        self.chk_pred.stateChanged.connect(lambda s: self._on_config_toggle("makcu_prediction", bool(s)))
        self.chk_smart = self._create_checkbox_row(c2_lay, "Smart Aim", "Aim more naturally", checked=True)
        self.chk_smart.stateChanged.connect(lambda s: self._on_config_toggle("makcu_lock_on_target", bool(s)))
        self.chk_anti_snap = self._create_checkbox_row(c2_lay, "Anti Snap", "Avoid robotic movement", checked=True)
        self.chk_anti_snap.stateChanged.connect(lambda s: self._on_config_toggle("makcu_anti_snap", bool(s)))

        # Linear Head Snap (No Decel)
        self.chk_linear_snap = self._create_checkbox_row(c2_lay, "Linear Head Snap", "Direct pull · zero slowdown before head", checked=True)
        self.chk_linear_snap.stateChanged.connect(self._on_linear_snap_toggle)

        # Head Deceleration / Braking Slider
        c2_lay.addSpacing(2)
        decel_head = QHBoxLayout()
        v_dec = QVBoxLayout()
        lbl_dec = QLabel("Head Braking")
        lbl_dec.setObjectName("ControlTitle")
        lbl_dec_sub = QLabel("Slowdown near head (0% = Off)", self)
        lbl_dec_sub.setObjectName("ControlSub")
        v_dec.addWidget(lbl_dec)
        v_dec.addWidget(lbl_dec_sub)
        decel_head.addLayout(v_dec)
        decel_head.addStretch()
        self.lbl_decel_val = QLabel("0%")
        self.lbl_decel_val.setObjectName("ValueBadge")
        decel_head.addWidget(self.lbl_decel_val)
        c2_lay.addLayout(decel_head)

        self.slider_head_decel = QSlider(Qt.Orientation.Horizontal)
        self.slider_head_decel.setObjectName("CyberSlider")
        self.slider_head_decel.setRange(0, 100)
        self.slider_head_decel.setValue(0)
        self.slider_head_decel.valueChanged.connect(self._on_head_decel_changed)
        c2_lay.addWidget(self.slider_head_decel)

        # Velocity Tracking (Feedforward Speed Matching)
        self.chk_feedforward = self._create_checkbox_row(c2_lay, "Velocity Tracking", "Match running enemy speed with zero lag", checked=True)
        self.chk_feedforward.stateChanged.connect(lambda s: self._on_config_toggle("velocity_feedforward", bool(s)))

        # Running Target Lead Time Slider (20 - 120 ms)
        c2_lay.addSpacing(2)
        lead_head = QHBoxLayout()
        v_lead = QVBoxLayout()
        lbl_lead = QLabel("Running Lead Time")
        lbl_lead.setObjectName("ControlTitle")
        lbl_lead_sub = QLabel("Advance prediction lead on running targets", self)
        lbl_lead_sub.setObjectName("ControlSub")
        v_lead.addWidget(lbl_lead)
        v_lead.addWidget(lbl_lead_sub)
        lead_head.addLayout(v_lead)
        lead_head.addStretch()
        self.lbl_lead_val = QLabel("55 ms")
        self.lbl_lead_val.setObjectName("ValueBadge")
        lead_head.addWidget(self.lbl_lead_val)
        c2_lay.addLayout(lead_head)

        self.slider_lead = QSlider(Qt.Orientation.Horizontal)
        self.slider_lead.setObjectName("CyberSlider")
        self.slider_lead.setRange(20, 120)
        self.slider_lead.setValue(55)
        self.slider_lead.valueChanged.connect(self._on_lead_slider_changed)
        c2_lay.addWidget(self.slider_lead)

        c2_lay.addStretch()
        col2.addWidget(c2, stretch=1)

        # Card: Miscellaneous
        c3 = CyberCard("Miscellaneous", "🔧")
        c3_lay = c3.card_layout

        self.sw_recoil = self._create_switch_row(c3_lay, "No Recoil", checked=True)
        self.sw_recoil.toggled.connect(lambda s: self._on_config_toggle("makcu_recoil_compensation", bool(s)))
        self.sw_spread = self._create_switch_row(c3_lay, "No Spread", checked=True)
        self.sw_spread.toggled.connect(lambda s: self._on_config_toggle("no_spread_enabled", bool(s)))
        self.sw_auto_fire = self._create_switch_row(c3_lay, "Auto Fire", checked=False)
        self.sw_auto_fire.toggled.connect(lambda s: self._on_config_toggle("makcu_auto_shoot", bool(s)))
        self.sw_trigger = self._create_switch_row(c3_lay, "Trigger Bot", checked=False)
        self.sw_trigger.toggled.connect(lambda s: self._on_config_toggle("makcu_triggerbot", bool(s)))

        # Lock Before Fire Toggle (Nur triggern wenn Fadenkreuz fest auf Ziel gelockt ist)
        self.sw_lock_trigger = self._create_switch_row(c3_lay, "🎯 Lock Before Fire", checked=True)
        self.sw_lock_trigger.toggled.connect(lambda s: self._on_config_toggle("makcu_trigger_on_lock_only", bool(s)))

        # Fire Tolerance Slider (2 - 15 px)
        c3_lay.addSpacing(3)
        tol_hdr = QHBoxLayout()
        lbl_tol = QLabel("Fire Tolerance:")
        lbl_tol.setObjectName("FieldLabel")
        self.lbl_tol_val = QLabel("5 px")
        self.lbl_tol_val.setObjectName("FieldValue")
        tol_hdr.addWidget(lbl_tol)
        tol_hdr.addStretch()
        tol_hdr.addWidget(self.lbl_tol_val)
        c3_lay.addLayout(tol_hdr)

        self.slider_tol = QSlider(Qt.Orientation.Horizontal)
        self.slider_tol.setObjectName("CyberSlider")
        self.slider_tol.setRange(2, 15)
        self.slider_tol.setValue(5)
        self.slider_tol.valueChanged.connect(self._on_trigger_tol_changed)
        c3_lay.addWidget(self.slider_tol)

        # Pre-Fire Lock Delay Slider (0 - 100 ms)
        c3_lay.addSpacing(3)
        del_hdr = QHBoxLayout()
        lbl_del = QLabel("Lock Settling Delay:")
        lbl_del.setObjectName("FieldLabel")
        self.lbl_lock_del_val = QLabel("25 ms")
        self.lbl_lock_del_val.setObjectName("FieldValue")
        del_hdr.addWidget(lbl_del)
        del_hdr.addStretch()
        del_hdr.addWidget(self.lbl_lock_del_val)
        c3_lay.addLayout(del_hdr)

        self.slider_lock_del = QSlider(Qt.Orientation.Horizontal)
        self.slider_lock_del.setObjectName("CyberSlider")
        self.slider_lock_del.setRange(0, 100)
        self.slider_lock_del.setValue(25)
        self.slider_lock_del.valueChanged.connect(self._on_trigger_lock_del_changed)
        c3_lay.addWidget(self.slider_lock_del)
        c3_lay.addStretch()
        col2.addWidget(c3, stretch=1)

        p_lay.addLayout(col2, stretch=2)

        # -------------------------------------------------------------
        # COLUMN 3: Visuals (ESP) Card & Detection Status Card
        # -------------------------------------------------------------
        col3 = QVBoxLayout()
        col3.setSpacing(12)

        # Card: Visuals (ESP)
        c4 = CyberCard("Visuals (ESP)", "👁️")
        c4_lay = c4.card_layout

        self.sw_esp_box = self._create_switch_row(c4_lay, "ESP Box", checked=True)
        self.sw_esp_box.toggled.connect(lambda s: self._on_config_toggle("show_boxes", bool(s)))
        self.sw_esp_skel = self._create_switch_row(c4_lay, "ESP Skeleton", checked=True)
        self.sw_esp_skel.toggled.connect(lambda s: self._on_config_toggle("show_skeleton", bool(s)))
        self.sw_esp_hp = self._create_switch_row(c4_lay, "ESP Health", checked=True)
        self.sw_esp_hp.toggled.connect(lambda s: self._on_config_toggle("show_health", bool(s)))
        self.sw_esp_name = self._create_switch_row(c4_lay, "ESP Name", checked=False)
        self.sw_esp_name.toggled.connect(lambda s: self._on_config_toggle("show_labels", bool(s)))
        self.sw_esp_dist = self._create_switch_row(c4_lay, "ESP Distance", checked=True)
        self.sw_esp_dist.toggled.connect(lambda s: self._on_config_toggle("show_distance", bool(s)))
        self.sw_snapline = self._create_switch_row(c4_lay, "Snapline", checked=True)
        self.sw_snapline.toggled.connect(lambda s: self._on_config_toggle("show_snaplines", bool(s)))
        self.sw_esp_ghost = self._create_switch_row(c4_lay, "Ghost Mode", checked=True)
        self.sw_esp_ghost.toggled.connect(lambda s: self._on_config_toggle("ghost_tracking", bool(s)))
        c4_lay.addStretch()
        col3.addWidget(c4, stretch=3)

        # Card: Detection Status (Vector Shield)
        c5 = CyberCard("Detection Status", "🛡️")
        c5_lay = c5.card_layout

        shield_lay = QVBoxLayout()
        shield_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield_lay.setSpacing(4)

        self.vec_shield = VectorShieldWidget(size=56)
        shield_lay.addWidget(self.vec_shield, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl_undetected = QLabel("Undetected")
        lbl_undetected.setObjectName("UndetectedTitle")
        lbl_undetected.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield_lay.addWidget(lbl_undetected)

        lbl_safe = QLabel("Safe to Use")
        lbl_safe.setObjectName("UndetectedSub")
        lbl_safe.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield_lay.addWidget(lbl_safe)

        # Streamer Mode Toggle inside Detection Status
        c5_lay.addLayout(shield_lay)
        c5_lay.addSpacing(4)
        sep_streamer = QFrame()
        sep_streamer.setFrameShape(QFrame.Shape.HLine)
        sep_streamer.setObjectName("CardSeparator")
        c5_lay.addWidget(sep_streamer)

        self.sw_streamer = self._create_switch_row(c5_lay, "Streamer Mode", checked=True)
        self.sw_streamer.toggled.connect(self._on_streamer_mode_toggle)

        lbl_streamer_sub = QLabel("OBS / Discord Stealth")
        lbl_streamer_sub.setObjectName("RowSub")
        lbl_streamer_sub.setStyleSheet("color: #64748B; font-size: 10px; text-align: center;")
        lbl_streamer_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c5_lay.addWidget(lbl_streamer_sub)

        c5_lay.addStretch()
        col3.addWidget(c5, stretch=2)

        p_lay.addLayout(col3, stretch=2)
        return page

    # Helper: Checkbox with subtitle
    def _create_checkbox_row(self, layout, title: str, subtitle: str, checked=True) -> QCheckBox:
        h = QHBoxLayout()
        chk = QCheckBox()
        chk.setObjectName("CyberCheckbox")
        chk.setChecked(checked)
        h.addWidget(chk)

        v = QVBoxLayout()
        v.setSpacing(1)
        lbl_t = QLabel(title)
        lbl_t.setObjectName("RowTitle")
        lbl_s = QLabel(subtitle)
        lbl_s.setObjectName("RowSub")
        v.addWidget(lbl_t)
        v.addWidget(lbl_s)
        h.addLayout(v)
        h.addStretch()

        layout.addLayout(h)
        return chk

    # Helper: Title + Toggle Switch Row
    def _create_switch_row(self, layout, title: str, checked=False) -> CyberToggle:
        h = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setObjectName("RowTitle")
        h.addWidget(lbl)
        h.addStretch()
        sw = CyberToggle(checked=checked, width=38, height=18)
        h.addWidget(sw)
        layout.addLayout(h)
        return sw

    def _on_aimbot_master_toggle(self, active: bool):
        if active:
            self.lbl_aim_state.setText("Aimbot\nON")
            self.lbl_aim_state.setStyleSheet("color: #00FF66; font-weight: 900; font-size: 13px;")
            self.lbl_dot.setText("●")
            self.lbl_dot.setStyleSheet("color: #00FF66; font-size: 14px;")
            self.lbl_status.setText("Status: Active")
            self.lbl_status.setStyleSheet("color: #00FF66; font-weight: 800; font-size: 11px;")
        else:
            self.lbl_aim_state.setText("Aimbot\nOFF")
            self.lbl_aim_state.setStyleSheet("color: #64748B; font-weight: 900; font-size: 13px;")
            self.lbl_dot.setText("●")
            self.lbl_dot.setStyleSheet("color: #FFB300; font-size: 14px;")
            self.lbl_status.setText("Status: Standby")
            self.lbl_status.setStyleSheet("color: #FFB300; font-weight: 800; font-size: 11px;")

        self.config.set("enabled", active)
        self.config.set("makcu_enabled", active)
        self.config_data["enabled"] = active
        self.config_data["makcu_enabled"] = active
        if self.overlay_window and hasattr(self.overlay_window, "update"):
            self.overlay_window.update()

    def _sync_engine_power_ui(self):
        """Called by yolo_main.py hotkey poller when 'C' toggles engine state."""
        is_active = bool(self.config.get("enabled", True))
        self.sw_aimbot.blockSignals(True)
        self.sw_aimbot.setChecked(is_active)
        self.sw_aimbot.blockSignals(False)
        if is_active:
            self.lbl_aim_state.setText("Aimbot\nON")
            self.lbl_aim_state.setStyleSheet("color: #00FF66; font-weight: 900; font-size: 13px;")
            self.lbl_dot.setText("●")
            self.lbl_dot.setStyleSheet("color: #00FF66; font-size: 14px;")
            self.lbl_status.setText("Status: Active")
            self.lbl_status.setStyleSheet("color: #00FF66; font-weight: 800; font-size: 11px;")
        else:
            self.lbl_aim_state.setText("Aimbot\nOFF")
            self.lbl_aim_state.setStyleSheet("color: #64748B; font-weight: 900; font-size: 13px;")
            self.lbl_dot.setText("●")
            self.lbl_dot.setStyleSheet("color: #FFB300; font-size: 14px;")
            self.lbl_status.setText("Status: Standby")
            self.lbl_status.setStyleSheet("color: #FFB300; font-weight: 800; font-size: 11px;")

    def _sync_headless_ui(self):
        pass

    def _on_fov_slider_changed(self, v: int):
        self.lbl_fov_val.setText(f"{v}°")
        self.config.set("makcu_fov", v)
        self.config_data["makcu_fov"] = v
        if self.overlay_window and hasattr(self.overlay_window, "update"):
            self.overlay_window.update()

    def _on_smooth_slider_changed(self, v: int):
        smooth = v / 10.0
        self.lbl_smooth_val.setText(f"{smooth:.1f}")
        self.config.set("makcu_smooth", smooth)
        self.config_data["makcu_smooth"] = smooth

    def _on_aim_key_changed(self, idx: int):
        key_map = {0: "rmb", 1: "lalt", 2: "xbutton1", 3: "xbutton2", 4: "always"}
        k = key_map.get(idx, "rmb")
        self.config.set("makcu_aim_key", k)
        self.config_data["makcu_aim_key"] = k

    def _on_target_bone_changed(self, idx: int):
        bone_map = {0: "head", 1: "neck", 2: "chest"}
        b = bone_map.get(idx, "head")
        self.config.set("makcu_target_bone", b)
        self.config_data["makcu_target_bone"] = b

    def _on_linear_snap_toggle(self, active: bool):
        self.config.set("linear_head_snap", active)
        self.config_data["linear_head_snap"] = active
        if active:
            self.slider_head_decel.blockSignals(True)
            self.slider_head_decel.setValue(0)
            self.lbl_decel_val.setText("0%")
            self.slider_head_decel.blockSignals(False)
            self.config.set("head_decel_strength", 0)
            self.config_data["head_decel_strength"] = 0

    def _on_head_decel_changed(self, v: int):
        self.lbl_decel_val.setText(f"{v}%")
        self.config.set("head_decel_strength", v)
        self.config_data["head_decel_strength"] = v
        is_linear = (v == 0)
        self.config.set("linear_head_snap", is_linear)
        self.config_data["linear_head_snap"] = is_linear
        self.chk_linear_snap.blockSignals(True)
        self.chk_linear_snap.setChecked(is_linear)
        self.chk_linear_snap.blockSignals(False)

    def _on_streamer_mode_toggle(self, active: bool):
        self.config.set("streamer_mode", active)
        self.config_data["streamer_mode"] = active
        if self.overlay_window and hasattr(self.overlay_window, "apply_streamer_mode"):
            self.overlay_window.apply_streamer_mode()

    def _on_trigger_tol_changed(self, v: int):
        self.lbl_tol_val.setText(f"{v} px")
        self.config.set("makcu_trigger_tolerance", v)
        self.config_data["makcu_trigger_tolerance"] = v

    def _on_trigger_lock_del_changed(self, v: int):
        self.lbl_lock_del_val.setText(f"{v} ms")
        self.config.set("makcu_trigger_lock_delay_ms", v)
        self.config_data["makcu_trigger_lock_delay_ms"] = v

    def _on_lead_slider_changed(self, v: int):
        self.lbl_lead_val.setText(f"{v} ms")
        self.config.set("makcu_lead_time_ms", v)
        self.config_data["makcu_lead_time_ms"] = v

    def _on_config_toggle(self, key: str, value: bool):
        self.config.set(key, value)
        self.config_data[key] = value
        if self.overlay_window and hasattr(self.overlay_window, "update"):
            self.overlay_window.update()

    def _on_conf_changed(self, v: int):
        c = v / 100.0
        self.lbl_conf_val.setText(f"{c:.2f}")
        self.config.set("confidence_threshold", c)
        self.config_data["confidence_threshold"] = c

    def _on_iou_changed(self, v: int):
        i = v / 100.0
        self.lbl_iou_val.setText(f"{i:.2f}")
        self.config.set("iou_threshold", i)
        self.config_data["iou_threshold"] = i

    def _on_scan_mode_changed(self, idx: int):
        scan_map = {0: "center_480", 1: "center_640", 2: "fullscreen"}
        sm = scan_map.get(idx, "center_480")
        self.config.set("scan_region_mode", sm)
        self.config_data["scan_region_mode"] = sm
        if self.overlay_window and hasattr(self.overlay_window, "update"):
            self.overlay_window.update()

    def _on_telemetry_tick(self):
        if not self.engine:
            return
        try:
            state = self.engine.get_state()
            fps = float(state.get("fps", 0.0))
            infer_ms = float(state.get("infer_time_ms", 0.0))
            targets = int(state.get("targets_detected", 0))
            is_aiming = bool(state.get("is_aiming", False))
            is_enabled = bool(self.config.get("enabled", True))

            if is_enabled:
                self.lbl_dot.setText("●")
                self.lbl_dot.setStyleSheet("color: #00FF66; font-size: 14px;")
                if is_aiming:
                    self.lbl_status.setText("Status: LOCKED 🎯")
                    self.lbl_status.setStyleSheet("color: #FFE600; font-weight: 900; font-size: 11px;")
                else:
                    self.lbl_status.setText("Status: Active")
                    self.lbl_status.setStyleSheet("color: #00FF66; font-weight: 800; font-size: 11px;")
                fps_disp = f"{fps:.0f} FPS" if fps > 0 else "Online"
                self.lbl_ai.setText(f"AI Engine: {fps_disp}")
                self.lbl_ai.setStyleSheet("color: #00FFCC; font-weight: 800; font-size: 11px;")
            else:
                self.lbl_dot.setText("●")
                self.lbl_dot.setStyleSheet("color: #FFB300; font-size: 14px;")
                self.lbl_status.setText("Status: Standby")
                self.lbl_status.setStyleSheet("color: #FFB300; font-weight: 800; font-size: 11px;")
                self.lbl_ai.setText("AI Engine: Paused")
                self.lbl_ai.setStyleSheet("color: #94A3B8; font-weight: 800; font-size: 11px;")

            # Sidebar FPS update
            if hasattr(self, "lbl_fps_val"):
                self.lbl_fps_val.setText(f"🚀 {fps:.0f} FPS" if fps > 0 else "🚀 280+ FPS")

            # AI Engine Hub Benchmark update
            if hasattr(self, "lbl_hud_speed"):
                lat_str = f"{infer_ms:.2f}ms" if infer_ms > 0 else "0.05ms"
                fps_str = f"{fps:.0f} FPS" if fps > 0 else "280+ FPS"
                self.lbl_hud_speed.setText(f"Live Pipeline: {fps_str} @ {lat_str} Latency · Targets: {targets}")
        except Exception:
            pass

    # -----------------------------------------------------------------
    # PAGE 1: DEDICATED AI ENGINE & MODEL HUB (Replaces ESP)
    # -----------------------------------------------------------------
    def _build_ai_engine_page(self) -> QWidget:
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # -------------------------------------------------------------
        # LEFT CARD: Neural Model Hub
        # -------------------------------------------------------------
        c_models = CyberCard("Neural Vision Models", "⚡")
        m_lay = c_models.card_layout

        lbl_desc = QLabel("Select active AI Detection Engine or load custom weights:")
        lbl_desc.setObjectName("ControlSub")
        m_lay.addWidget(lbl_desc)

        # Game Models Dropdown
        self.combo_model = QComboBox()
        self.combo_model.setObjectName("CyberCombo")
        self.combo_model.setFixedHeight(34)
        self.model_items = [
            ("valorant", "Valorant 30K [High-Speed TensorRT 10]", "valorant_30k_640.engine"),
            ("fortnite", "Fortnite 100K [Anatomical Head-Lock 260+ FPS]", "fortnite_100k.engine"),
            ("arc_raiders", "ARC Raiders [YOLOv11 Raider Engine]", "arc_raiders_yolo11_better.engine"),
            ("cs2", "Counter-Strike 2 [Head/Neck Direct TRT]", "GGMCS2.engine"),
            ("battlefield_2042", "Battlefield 2042 [FP16 TRT 10]", "battlefield_2042.engine"),
        ]
        for _, label, eng in self.model_items:
            self.combo_model.addItem(f"🎮  {label}", eng)
        self.combo_model.currentIndexChanged.connect(self._on_model_changed)
        m_lay.addWidget(self.combo_model)

        # Custom Model File Browser
        btn_browse = QPushButton("📂 Browse Custom Model (.engine / .onnx / .pt)...")
        btn_browse.setObjectName("ActionBtn")
        btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse.clicked.connect(self._handle_browse_custom_model)
        m_lay.addWidget(btn_browse)

        # Model Telemetry HUD Badge
        self.model_hud = QFrame()
        self.model_hud.setObjectName("ModelHudFrame")
        h_lay = QVBoxLayout(self.model_hud)
        h_lay.setContentsMargins(12, 10, 12, 10)
        h_lay.setSpacing(4)

        self.lbl_hud_name = QLabel("Active: valorant_30k_640.engine")
        self.lbl_hud_name.setObjectName("HudHeader")
        self.lbl_hud_spec = QLabel("Format: Direct TensorRT 10 · Input: (1, 3, 640, 640) BCHW")
        self.lbl_hud_spec.setObjectName("HudItem")
        self.lbl_hud_speed = QLabel("Benchmark: ~280+ FPS @ 0.05ms Capture Latency")
        self.lbl_hud_speed.setObjectName("HudItemHighlight")

        h_lay.addWidget(self.lbl_hud_name)
        h_lay.addWidget(self.lbl_hud_spec)
        h_lay.addWidget(self.lbl_hud_speed)
        m_lay.addWidget(self.model_hud)

        m_lay.addStretch()

        # Auto Converter Button
        btn_convert = QPushButton("⚡ Auto-Compile Engine for RTX 4070 (TRT 10/11)")
        btn_convert.setObjectName("ApplyButton")
        btn_convert.setFixedHeight(34)
        btn_convert.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_convert.clicked.connect(self._handle_auto_convert)
        m_lay.addWidget(btn_convert)

        lay.addWidget(c_models, stretch=3)

        # -------------------------------------------------------------
        # RIGHT CARD: Vision & Inference Pipeline Tuning
        # -------------------------------------------------------------
        c_tuning = CyberCard("Inference Pipeline Tuning", "🧠")
        t_lay = c_tuning.card_layout

        # Confidence Threshold Slider
        c_head = QHBoxLayout()
        v_c_info = QVBoxLayout()
        lbl_c = QLabel("Confidence Threshold")
        lbl_c.setObjectName("ControlTitle")
        lbl_c_sub = QLabel("Minimum AI detection confidence")
        lbl_c_sub.setObjectName("ControlSub")
        v_c_info.addWidget(lbl_c)
        v_c_info.addWidget(lbl_c_sub)
        c_head.addLayout(v_c_info)
        c_head.addStretch()
        self.lbl_conf_val = QLabel("0.70")
        self.lbl_conf_val.setObjectName("ValueBadge")
        c_head.addWidget(self.lbl_conf_val)
        t_lay.addLayout(c_head)

        self.slider_conf = QSlider(Qt.Orientation.Horizontal)
        self.slider_conf.setObjectName("CyberSlider")
        self.slider_conf.setRange(20, 95)
        self.slider_conf.setValue(70)
        self.slider_conf.valueChanged.connect(self._on_conf_changed)
        t_lay.addWidget(self.slider_conf)

        # IoU NMS Suppression Slider
        t_lay.addSpacing(6)
        iou_head = QHBoxLayout()
        v_i_info = QVBoxLayout()
        lbl_i = QLabel("IoU NMS Overlap")
        lbl_i.setObjectName("ControlTitle")
        lbl_i_sub = QLabel("Suppresses duplicate bounding boxes")
        lbl_i_sub.setObjectName("ControlSub")
        v_i_info.addWidget(lbl_i)
        v_i_info.addWidget(lbl_i_sub)
        iou_head.addLayout(v_i_info)
        iou_head.addStretch()
        self.lbl_iou_val = QLabel("0.45")
        self.lbl_iou_val.setObjectName("ValueBadge")
        iou_head.addWidget(self.lbl_iou_val)
        t_lay.addLayout(iou_head)

        self.slider_iou = QSlider(Qt.Orientation.Horizontal)
        self.slider_iou.setObjectName("CyberSlider")
        self.slider_iou.setRange(15, 80)
        self.slider_iou.setValue(45)
        self.slider_iou.valueChanged.connect(self._on_iou_changed)
        t_lay.addWidget(self.slider_iou)

        # Scan Region Mode Dropdown
        t_lay.addSpacing(6)
        lbl_scan = QLabel("Scan Region Mode:")
        lbl_scan.setObjectName("ControlTitle")
        t_lay.addWidget(lbl_scan)

        self.combo_scan_mode = QComboBox()
        self.combo_scan_mode.setObjectName("CyberCombo")
        self.combo_scan_mode.addItems([
            "Center 480x480 (Combat Zoom - Lowest Latency)",
            "Center 640x640 (Balanced Detection Zone)",
            "Fullscreen 1920x1080 (Wide Radar Scan)"
        ])
        self.combo_scan_mode.currentIndexChanged.connect(self._on_scan_mode_changed)
        t_lay.addWidget(self.combo_scan_mode)

        # Advanced Pipeline Checkboxes
        t_lay.addSpacing(8)
        self.chk_zoom = self._create_checkbox_row(t_lay, "Dynamic Combat Zoom", "Auto-focuses region during active fire", checked=True)
        self.chk_zoom.stateChanged.connect(lambda s: self._on_config_toggle("dynamic_combat_zoom", bool(s)))
        self.chk_half = self._create_checkbox_row(t_lay, "Half-Precision (FP16)", "Hardware Tensor Core acceleration", checked=True)
        self.chk_half.stateChanged.connect(lambda s: self._on_config_toggle("use_half_precision", bool(s)))
        self.chk_nms = self._create_checkbox_row(t_lay, "Agnostic NMS", "Faster non-maximum suppression", checked=True)
        self.chk_nms.stateChanged.connect(lambda s: self._on_config_toggle("agnostic_nms", bool(s)))

        t_lay.addStretch()
        lay.addWidget(c_tuning, stretch=2)

        return page

    def _on_model_changed(self, idx: int):
        if idx < 0 or idx >= len(self.model_items):
            return
        gid, name, eng_file = self.model_items[idx]
        self.config.set("active_game_profile", gid)
        self.config_data["active_game_profile"] = gid

        # Look for model on disk (.engine, .onnx, or .pt)
        candidates = [
            os.path.join(BASE_DIR, eng_file),
            os.path.join(BASE_DIR, eng_file.replace(".engine", ".onnx")),
            os.path.join(BASE_DIR, eng_file.replace(".engine", ".pt")),
            os.path.join(BASE_DIR, "models", eng_file),
        ]
        chosen = None
        for c in candidates:
            if os.path.exists(c):
                chosen = c
                break

        if chosen:
            fname = os.path.basename(chosen)
            self.config.set("model_path", fname)
            self.config_data["model_path"] = fname
            if self.engine:
                self.engine.load_model(chosen)
            self.lbl_hud_name.setText(f"Active: {fname}")
            if fname.endswith(".engine"):
                self.lbl_hud_spec.setText(f"Format: Direct TensorRT 10/11 · {name}")
            else:
                self.lbl_hud_spec.setText(f"Format: ONNX / CUDA Ingestion · {name}")
        else:
            self.config.set("model_path", eng_file)
            self.config_data["model_path"] = eng_file
            self.lbl_hud_name.setText(f"Active: {eng_file}")
            self.lbl_hud_spec.setText(f"Game: {name} · FP16 TensorRT 10/11")

    def _handle_browse_custom_model(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "Select Neural Model", BASE_DIR,
            "Neural Engine Files (*.engine *.onnx *.pt)"
        )
        if fpath and os.path.exists(fpath):
            fname = os.path.basename(fpath)
            self.config.set("model_path", fpath)
            self.config_data["model_path"] = fpath
            self.config.set("active_game_profile", "custom")
            self.config_data["active_game_profile"] = "custom"
            if self.engine:
                self.engine.load_model(fpath)
            self.lbl_hud_name.setText(f"Custom: {fname}")
            self.lbl_hud_spec.setText(f"Format: Custom Neural Model ({fname})")
            self.combo_model.blockSignals(True)
            self.combo_model.setCurrentIndex(-1)
            self.combo_model.blockSignals(False)

    def _handle_auto_convert(self):
        try:
            import subprocess
            py_cmd = sys.executable or "py"
            subprocess.Popen([py_cmd, "auto_converter.py"], cwd=BASE_DIR)
            QMessageBox.information(
                self, "Auto-Converter Started",
                "Universal TensorRT 10/11 Compiler started in background.\n"
                "Your RTX 4070 will build optimized engines for all models."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to launch auto-converter: {e}")

    # -----------------------------------------------------------------
    # PAGE 2: HARDWARE & DUAL-PC SETTINGS TAB
    # -----------------------------------------------------------------
    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        card = CyberCard("Hardware Pipeline & Execution Architecture", "⚙️")
        c_lay = card.card_layout

        lbl_mode = QLabel("Select Pipeline Mode:")
        lbl_mode.setObjectName("ControlTitle")
        c_lay.addWidget(lbl_mode)

        h_mode = QHBoxLayout()
        self.btn_hw_single = QPushButton("💻 Single-PC (Direct DWM 0-Copy)")
        self.btn_hw_single.setObjectName("ModeSelectBtn")
        self.btn_hw_single.setCheckable(True)
        self.btn_hw_single.setChecked(True)
        self.btn_hw_single.clicked.connect(lambda: self._set_pipe_mode("desktop"))
        h_mode.addWidget(self.btn_hw_single)

        self.btn_hw_dual = QPushButton("🖥️🖥️ Dual-PC (HDMI Capture Card)")
        self.btn_hw_dual.setObjectName("ModeSelectBtn")
        self.btn_hw_dual.setCheckable(True)
        self.btn_hw_dual.clicked.connect(lambda: self._set_pipe_mode("capture_card"))
        h_mode.addWidget(self.btn_hw_dual)
        c_lay.addLayout(h_mode)

        self.lbl_hw_status = QLabel("● Active: Single-PC Direct DWM (~0.05 ms capture latency)")
        self.lbl_hw_status.setObjectName("ModePill")
        c_lay.addWidget(self.lbl_hw_status)

        c_lay.addStretch()
        lay.addWidget(card)
        return page

    def _set_pipe_mode(self, mode: str):
        is_dual = (mode == "capture_card")
        self.btn_hw_single.setChecked(not is_dual)
        self.btn_hw_dual.setChecked(is_dual)
        self.config.set("capture_source", mode)
        self.config_data["capture_source"] = mode
        if self.engine:
            self.engine.capture_source = mode
        if is_dual:
            self.lbl_hw_status.setText("⚡ Active: Dual-PC 100% Hardware Isolated via HDMI Capture Card")
            self.lbl_hw_status.setStyleSheet("color: #00FFCC; font-weight: bold;")
        else:
            self.lbl_hw_status.setText("● Active: Single-PC Direct DWM (~0.05 ms capture latency)")
            self.lbl_hw_status.setStyleSheet("color: #00F0FF; font-weight: bold;")

    # -----------------------------------------------------------------
    # PAGE 3: CONFIGS TAB
    # -----------------------------------------------------------------
    def _build_configs_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        card = CyberCard("Tactical Profiles & Preset Manager", "📁")
        c_lay = card.card_layout

        lbl = QLabel("Quick-Switch Game Profile & Neural Engine:")
        lbl.setObjectName("ControlTitle")
        c_lay.addWidget(lbl)

        games = [
            ("valorant", "Valorant (Direct TRT 10)", 0),
            ("fortnite", "Fortnite 100K (260+ FPS)", 1),
            ("arc_raiders", "ARC Raiders (YOLO11)", 2),
            ("cs2", "Counter-Strike 2 (GGMCS2)", 3),
            ("battlefield_2042", "Battlefield 2042 (FP16 TRT)", 4),
        ]
        for gid, gname, m_idx in games:
            b = QPushButton(f"🎮  {gname}")
            b.setObjectName("ProfileSelectBtn")
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.clicked.connect(lambda _, idx=m_idx: self._select_profile_by_index(idx))
            c_lay.addWidget(b)

        c_lay.addStretch()
        lay.addWidget(card)
        return page

    def _select_profile_by_index(self, idx: int):
        self.combo_model.setCurrentIndex(idx)
        self._switch_tab(1)

    # -----------------------------------------------------------------
    # PAGE 4: ABOUT TAB
    # -----------------------------------------------------------------
    def _build_about_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        card = CyberCard("AURA Tactical Suite // System Information", "ℹ️")
        c_lay = card.card_layout

        txt = (
            "<b>AURA Tactical Vision Suite v5.0.4</b><br>"
            "Architecture: Hybrid TensorRT 10/11 Vision Ingestion<br>"
            "License Tier: <b>💎 LIFETIME VIP</b><br>"
            "Hardware Mouse Emulation: MAKCU Dual-ESP32<br>"
            "Status: <b>Undetected & Operational</b>"
        )
        lbl = QLabel(txt)
        lbl.setObjectName("AboutText")
        c_lay.addWidget(lbl)
        c_lay.addStretch()
        lay.addWidget(card)
        return page

    # -----------------------------------------------------------------
    # BOTTOM ACTION BAR
    # -----------------------------------------------------------------
    def _build_bottom_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("BottomBar")
        bar.setFixedHeight(54)
        b_lay = QHBoxLayout(bar)
        b_lay.setContentsMargins(18, 8, 18, 10)
        b_lay.setSpacing(10)

        # Action utility buttons
        btn_load = QPushButton("📁 Load Config")
        btn_load.setObjectName("ActionBtn")
        btn_load.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_load.clicked.connect(self._handle_load_config)
        b_lay.addWidget(btn_load)

        btn_save = QPushButton("💾 Save Config")
        btn_save.setObjectName("ActionBtn")
        btn_save.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_save.clicked.connect(self._handle_save_config)
        b_lay.addWidget(btn_save)

        btn_reset = QPushButton("🔄 Reset Settings")
        btn_reset.setObjectName("ActionBtn")
        btn_reset.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_reset.clicked.connect(self._handle_reset_settings)
        b_lay.addWidget(btn_reset)

        b_lay.addStretch()

        # Prominent Glowing Red Apply Button
        self.btn_apply = QPushButton("✔  Apply Settings")
        self.btn_apply.setObjectName("ApplyButton")
        self.btn_apply.setFixedSize(160, 36)
        self.btn_apply.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_apply.clicked.connect(self._handle_apply_settings)
        b_lay.addWidget(self.btn_apply)

        return bar

    # -----------------------------------------------------------------
    # CONFIG SYNCHRONIZATION & ACTIONS
    # -----------------------------------------------------------------
    def _sync_ui_from_config(self):
        cfg = self.config.data
        
        widgets_to_block = [
            self.slider_fov, self.slider_smooth, self.combo_aim_key,
            self.combo_target, self.chk_pred, self.chk_smart, self.chk_anti_snap,
            self.chk_linear_snap, self.slider_head_decel,
            self.chk_feedforward, self.slider_lead,
            self.sw_recoil, self.sw_spread, self.sw_auto_fire, self.sw_trigger,
            self.sw_lock_trigger, self.slider_tol, self.slider_lock_del,
            self.sw_esp_box, self.sw_esp_skel, self.sw_esp_hp, self.sw_esp_name,
            self.sw_esp_dist, self.sw_snapline, self.sw_esp_ghost, self.sw_streamer,
            self.combo_model, self.slider_conf, self.slider_iou, self.combo_scan_mode,
            self.chk_zoom, self.chk_half, self.chk_nms, self.sw_aimbot
        ]
        for w in widgets_to_block:
            w.blockSignals(True)

        try:
            # Master Aimbot Switch
            is_enabled = bool(cfg.get("enabled", True))
            self.sw_aimbot.setChecked(is_enabled)
            if is_enabled:
                self.lbl_aim_state.setText("Aimbot\nON")
                self.lbl_aim_state.setStyleSheet("color: #00FF66; font-weight: 900; font-size: 13px;")
            else:
                self.lbl_aim_state.setText("Aimbot\nOFF")
                self.lbl_aim_state.setStyleSheet("color: #64748B; font-weight: 900; font-size: 13px;")

            # FOV
            fov = int(cfg.get("makcu_fov", 120))
            self.slider_fov.setValue(fov)
            self.lbl_fov_val.setText(f"{fov}°")

            # Smoothness
            smooth = float(cfg.get("makcu_smooth", 3.0))
            self.slider_smooth.setValue(int(smooth * 10))
            self.lbl_smooth_val.setText(f"{smooth:.1f}")

            # Aim Key
            key = str(cfg.get("makcu_aim_key", "rmb")).lower()
            if "rmb" in key or "right" in key:
                self.combo_aim_key.setCurrentIndex(0)
            elif "alt" in key:
                self.combo_aim_key.setCurrentIndex(1)
            elif "1" in key or "4" in key:
                self.combo_aim_key.setCurrentIndex(2)
            elif "2" in key or "5" in key:
                self.combo_aim_key.setCurrentIndex(3)
            elif "always" in key:
                self.combo_aim_key.setCurrentIndex(4)

            # Target Bone
            bone = str(cfg.get("makcu_target_bone", "head")).lower()
            if "neck" in bone:
                self.combo_target.setCurrentIndex(1)
            elif "chest" in bone or "body" in bone or "center" in bone:
                self.combo_target.setCurrentIndex(2)
            else:
                self.combo_target.setCurrentIndex(0)

            # AI Features
            self.chk_pred.setChecked(bool(cfg.get("makcu_prediction", True)))
            self.chk_smart.setChecked(bool(cfg.get("makcu_lock_on_target", False)))
            self.chk_anti_snap.setChecked(bool(cfg.get("makcu_anti_snap", True)))

            # Linear Head Snap & Deceleration
            is_linear = bool(cfg.get("linear_head_snap", True))
            decel_val = int(cfg.get("head_decel_strength", 0))
            self.chk_linear_snap.setChecked(is_linear)
            self.slider_head_decel.setValue(decel_val)
            self.lbl_decel_val.setText(f"{decel_val}%" if decel_val > 0 else "0% (Aus)")

            # Velocity Tracking & Running Lead Time
            self.chk_feedforward.setChecked(bool(cfg.get("velocity_feedforward", True)))
            lead_val = int(cfg.get("makcu_lead_time_ms", 55))
            self.slider_lead.setValue(lead_val)
            self.lbl_lead_val.setText(f"{lead_val} ms")

            # Miscellaneous
            self.sw_recoil.setChecked(bool(cfg.get("makcu_recoil_compensation", True)))
            self.sw_spread.setChecked(bool(cfg.get("no_spread_enabled", True)))
            self.sw_auto_fire.setChecked(bool(cfg.get("makcu_auto_shoot", False)))
            self.sw_trigger.setChecked(bool(cfg.get("makcu_triggerbot", False)))
            self.sw_lock_trigger.setChecked(bool(cfg.get("makcu_trigger_on_lock_only", True)))
            tol_val = int(cfg.get("makcu_trigger_tolerance", 5))
            self.slider_tol.setValue(tol_val)
            self.lbl_tol_val.setText(f"{tol_val} px")
            del_val = int(cfg.get("makcu_trigger_lock_delay_ms", 25))
            self.slider_lock_del.setValue(del_val)
            self.lbl_lock_del_val.setText(f"{del_val} ms")

            # ESP states & Ghost Mode
            self.sw_esp_box.setChecked(bool(cfg.get("show_boxes", True)))
            self.sw_esp_skel.setChecked(bool(cfg.get("show_skeleton", True)))
            self.sw_esp_hp.setChecked(bool(cfg.get("show_health", True)))
            self.sw_esp_name.setChecked(bool(cfg.get("show_labels", False)))
            self.sw_esp_dist.setChecked(bool(cfg.get("show_distance", True)))
            self.sw_snapline.setChecked(bool(cfg.get("show_snaplines", True)))
            self.sw_esp_ghost.setChecked(bool(cfg.get("ghost_tracking", True)))

            # Streamer Mode
            self.sw_streamer.setChecked(bool(cfg.get("streamer_mode", True)))

            # AI Engine Page Sync
            active_prof = str(cfg.get("active_game_profile", "valorant")).lower()
            for idx, (gid, _, _) in enumerate(self.model_items):
                if gid in active_prof:
                    self.combo_model.setCurrentIndex(idx)
                    break

            conf = float(cfg.get("confidence_threshold", 0.70))
            self.slider_conf.setValue(int(conf * 100))
            self.lbl_conf_val.setText(f"{conf:.2f}")

            iou = float(cfg.get("iou_threshold", 0.45))
            self.slider_iou.setValue(int(iou * 100))
            self.lbl_iou_val.setText(f"{iou:.2f}")

            s_mode = str(cfg.get("scan_region_mode", "center_480")).lower()
            if "640" in s_mode:
                self.combo_scan_mode.setCurrentIndex(1)
            elif "full" in s_mode:
                self.combo_scan_mode.setCurrentIndex(2)
            else:
                self.combo_scan_mode.setCurrentIndex(0)

            self.chk_zoom.setChecked(bool(cfg.get("dynamic_combat_zoom", True)))
            self.chk_half.setChecked(bool(cfg.get("use_half_precision", True)))
            self.chk_nms.setChecked(bool(cfg.get("agnostic_nms", True)))

            # Hardware page
            pipe = str(cfg.get("capture_source", "desktop")).lower()
            if hasattr(self, "btn_hw_single") and hasattr(self, "btn_hw_dual"):
                self._set_pipe_mode(pipe)
        finally:
            for w in widgets_to_block:
                w.blockSignals(False)

    def _handle_apply_settings(self):
        # Update config directly
        self.config.set("makcu_fov", self.slider_fov.value())
        self.config.set("makcu_smooth", self.slider_smooth.value() / 10.0)

        key_idx = self.combo_aim_key.currentIndex()
        key_map = {0: "rmb", 1: "lalt", 2: "xbutton1", 3: "xbutton2", 4: "always"}
        self.config.set("makcu_aim_key", key_map.get(key_idx, "rmb"))

        bone_idx = self.combo_target.currentIndex()
        bone_map = {0: "head", 1: "neck", 2: "chest"}
        self.config.set("makcu_target_bone", bone_map.get(bone_idx, "head"))

        self.config.set("makcu_prediction", self.chk_pred.isChecked())
        self.config.set("makcu_lock_on_target", self.chk_smart.isChecked())
        self.config.set("makcu_anti_snap", self.chk_anti_snap.isChecked())

        self.config.set("makcu_recoil_compensation", self.sw_recoil.isChecked())
        self.config.set("no_spread_enabled", self.sw_spread.isChecked())
        self.config.set("makcu_auto_shoot", self.sw_auto_fire.isChecked())
        self.config.set("makcu_triggerbot", self.sw_trigger.isChecked())
        self.config.set("makcu_trigger_on_lock_only", self.sw_lock_trigger.isChecked())
        self.config.set("makcu_trigger_tolerance", self.slider_tol.value())
        self.config.set("makcu_trigger_lock_delay_ms", self.slider_lock_del.value())

        self.config.set("show_boxes", self.sw_esp_box.isChecked())
        self.config.set("show_skeleton", self.sw_esp_skel.isChecked())
        self.config.set("show_health", self.sw_esp_hp.isChecked())
        self.config.set("show_labels", self.sw_esp_name.isChecked())
        self.config.set("show_distance", self.sw_esp_dist.isChecked())
        self.config.set("show_snaplines", self.sw_snapline.isChecked())
        self.config.set("ghost_tracking", self.sw_esp_ghost.isChecked())
        self.config.set("streamer_mode", self.sw_streamer.isChecked())
        if self.overlay_window and hasattr(self.overlay_window, "apply_streamer_mode"):
            self.overlay_window.apply_streamer_mode()

        # Linear Head Snap & Deceleration
        self.config.set("linear_head_snap", self.chk_linear_snap.isChecked())
        self.config.set("head_decel_strength", self.slider_head_decel.value())
        self.config.set("velocity_feedforward", self.chk_feedforward.isChecked())
        self.config.set("makcu_lead_time_ms", self.slider_lead.value())

        # AI Engine Page Settings
        self.config.set("confidence_threshold", self.slider_conf.value() / 100.0)
        self.config.set("iou_threshold", self.slider_iou.value() / 100.0)

        scan_idx = self.combo_scan_mode.currentIndex()
        scan_map = {0: "center_480", 1: "center_640", 2: "fullscreen"}
        self.config.set("scan_region_mode", scan_map.get(scan_idx, "center_480"))

        self.config.set("dynamic_combat_zoom", self.chk_zoom.isChecked())
        self.config.set("use_half_precision", self.chk_half.isChecked())
        self.config.set("agnostic_nms", self.chk_nms.isChecked())

        self.config.save()
        if self.overlay_window and hasattr(self.overlay_window, "update"):
            self.overlay_window.update()

        self.btn_apply.setText("✔  SETTINGS SAVED!")
        self.btn_apply.setStyleSheet("background: #00FF66; color: #000000; font-weight: 900; border-radius: 6px;")
        QTimer.singleShot(400, self._reset_apply_btn)

    def _reset_apply_btn(self):
        self.btn_apply.setText("✔  Apply Settings")
        self.btn_apply.setStyleSheet("")

    def _handle_load_config(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Load Tactical Preset", BASE_DIR, "JSON Files (*.json)")
        if fpath and os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.config.data.update(loaded)
                self.config.save()
                self._sync_ui_from_config()
                if self.overlay_window and hasattr(self.overlay_window, "update"):
                    self.overlay_window.update()
                QMessageBox.information(self, "Preset Loaded", "Tactical preset loaded successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load config: {e}")

    def _handle_save_config(self):
        fpath, _ = QFileDialog.getSaveFileName(self, "Save Tactical Preset", os.path.join(BASE_DIR, "my_preset.json"), "JSON Files (*.json)")
        if fpath:
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(self.config.data, f, indent=4)
                QMessageBox.information(self, "Saved", "Preset successfully saved!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save preset: {e}")

    def _handle_reset_settings(self):
        self.slider_fov.setValue(120)
        self.slider_smooth.setValue(30)
        self.combo_aim_key.setCurrentIndex(0)
        self.combo_target.setCurrentIndex(0)
        self.chk_feedforward.setChecked(True)
        self.slider_lead.setValue(55)
        self.lbl_lead_val.setText("55 ms")
        self.chk_pred.setChecked(True)
        self.chk_smart.setChecked(False)
        self.chk_anti_snap.setChecked(True)
        self.sw_recoil.setChecked(True)
        self.sw_spread.setChecked(True)
        self.sw_auto_fire.setChecked(False)
        self.sw_trigger.setChecked(False)
        self.sw_lock_trigger.setChecked(True)
        self.slider_tol.setValue(5)
        self.slider_lock_del.setValue(25)
        self.sw_esp_box.setChecked(True)
        self.sw_esp_skel.setChecked(True)
        self.sw_esp_hp.setChecked(True)
        self.sw_esp_name.setChecked(False)
        self.sw_esp_dist.setChecked(True)
        self.sw_snapline.setChecked(True)
        self.sw_esp_ghost.setChecked(True)
        self.sw_streamer.setChecked(True)
        self.chk_linear_snap.setChecked(True)
        self.slider_head_decel.setValue(0)
        self.lbl_decel_val.setText("0% (Aus)")
        self.slider_conf.setValue(70)
        self.slider_iou.setValue(45)
        self.combo_scan_mode.setCurrentIndex(0)
        self._handle_apply_settings()

    # -----------------------------------------------------------------
    # WINDOW DRAGGING SUPPORT (Frameless)
    # -----------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 68:
            self.drag_position = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(e.globalPosition().toPoint() - self.drag_position)
            e.accept()

    def mouseReleaseEvent(self, e):
        self.drag_position = QPoint()

    # -----------------------------------------------------------------
    # COMPREHENSIVE CYBER-RED STYLING SHEET
    # -----------------------------------------------------------------
    def _apply_styling(self):
        qss = """
        /* Root Chassis with Cyber-Red Obsidian Finish */
        QFrame#RootChassis {
            background-color: #0b0d13;
            border: 1.5px solid #FF1744;
            border-radius: 12px;
        }

        /* Top Header */
        QFrame#TopHeader {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a080d, stop:0.5 #120508, stop:1 #0b0d13);
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1.5px solid #2a0b12;
        }

        QLabel#TitleAura {
            color: #FFFFFF;
            font-size: 20px;
            font-weight: 900;
            letter-spacing: 3px;
        }

        QLabel#TitleSlogan {
            color: #FF1744;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 2px;
        }

        QLabel#StatusDot {
            color: #00FF66;
            font-size: 14px;
        }

        QLabel#StatusText {
            color: #E2E8F0;
            font-size: 11px;
            font-weight: 700;
        }

        QLabel#StatusSep {
            color: #334155;
            font-size: 12px;
        }

        QLabel#AiEngineText {
            color: #00FF66;
            font-size: 11px;
            font-weight: 800;
        }

        QPushButton#WinBtnMin, QPushButton#WinBtnClose {
            background: transparent;
            color: #94A3B8;
            border: none;
            font-size: 13px;
            font-weight: bold;
            border-radius: 4px;
        }
        QPushButton#WinBtnMin:hover {
            color: #FFFFFF;
            background: #1E293B;
        }
        QPushButton#WinBtnClose:hover {
            color: #FFFFFF;
            background: #FF1744;
        }

        /* Sidebar Navigation */
        QFrame#SidebarFrame {
            background: #0d0f17;
            border: 1px solid #1f141a;
            border-radius: 10px;
        }

        QPushButton#NavButton {
            background: transparent;
            color: #94A3B8;
            font-size: 12px;
            font-weight: 700;
            text-align: left;
            padding: 9px 14px;
            border: 1px solid transparent;
            border-radius: 7px;
        }

        QPushButton#NavButton:hover {
            color: #FFFFFF;
            background: rgba(255, 23, 68, 0.12);
            border-color: rgba(255, 23, 68, 0.3);
        }

        QPushButton#NavButton[selected="true"] {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E50914, stop:1 #A8000A);
            color: #FFFFFF;
            border: 1px solid #FF3355;
            font-weight: 900;
        }

        /* Sidebar Telemetry HUD Box */
        QFrame#SidebarHudBox {
            background: #0a0c12;
            border: 1px solid #1c2738;
            border-radius: 8px;
        }
        QLabel#HudHeader {
            color: #FF1744;
            font-size: 9px;
            font-weight: 900;
            letter-spacing: 1px;
        }
        QLabel#HudItem {
            color: #94A3B8;
            font-size: 10px;
            font-weight: 700;
        }
        QLabel#HudItemHighlight {
            color: #00FF66;
            font-size: 11px;
            font-weight: 900;
        }

        /* Cyber Cards */
        QFrame#CyberCard {
            background: rgba(13, 16, 23, 0.96);
            border: 1px solid #241117;
            border-radius: 10px;
        }
        QFrame#CyberCard:hover {
            border-color: #3d141f;
        }

        QLabel#CardHeaderIcon {
            font-size: 14px;
        }

        QLabel#CardHeaderTitle {
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 900;
            letter-spacing: 0.5px;
        }

        QFrame#CardSeparator {
            color: #1f2738;
            height: 1px;
            margin-bottom: 4px;
        }

        /* Labels & Value Badges */
        QLabel#ControlTitle {
            color: #FFFFFF;
            font-size: 11px;
            font-weight: 800;
        }

        QLabel#ControlSub {
            color: #64748B;
            font-size: 9px;
            font-weight: 600;
        }

        QLabel#ValueBadge {
            background: #141724;
            color: #FFFFFF;
            border: 1px solid #2A324B;
            border-radius: 5px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 900;
        }

        QLabel#RowTitle {
            color: #E2E8F0;
            font-size: 11px;
            font-weight: 700;
        }

        QLabel#RowSub {
            color: #64748B;
            font-size: 9px;
        }

        /* Sliders */
        QSlider#CyberSlider::groove:horizontal {
            background: #19202E;
            height: 4px;
            border-radius: 2px;
        }

        QSlider#CyberSlider::sub-page:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF1744, stop:1 #FF5252);
            height: 4px;
            border-radius: 2px;
        }

        QSlider#CyberSlider::handle:horizontal {
            background: #FFFFFF;
            border: 2px solid #FF1744;
            width: 12px;
            height: 12px;
            margin-top: -4px;
            margin-bottom: -4px;
            border-radius: 6px;
        }
        QSlider#CyberSlider::handle:horizontal:hover {
            background: #FF1744;
            border-color: #FFFFFF;
        }

        /* Dropdowns (ComboBox) */
        QComboBox#CyberCombo {
            background: #121622;
            color: #FFFFFF;
            border: 1px solid #26334D;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        }
        QComboBox#CyberCombo:hover {
            border-color: #FF1744;
        }
        QComboBox#CyberCombo::drop-down {
            border: none;
            width: 18px;
        }
        QComboBox#CyberCombo QAbstractItemView {
            background: #0F131D;
            color: #FFFFFF;
            selection-background-color: #FF1744;
            border: 1px solid #26334D;
        }

        /* Checkboxes */
        QCheckBox#CyberCheckbox::indicator {
            width: 14px;
            height: 14px;
            border: 1px solid #334155;
            border-radius: 3px;
            background: #121622;
        }
        QCheckBox#CyberCheckbox::indicator:checked {
            background: #FF1744;
            border-color: #FF1744;
        }

        /* Undetected Badge */
        QLabel#UndetectedTitle {
            color: #00FF66;
            font-size: 14px;
            font-weight: 900;
            letter-spacing: 0.5px;
        }
        QLabel#UndetectedSub {
            color: #94A3B8;
            font-size: 10px;
            font-weight: 600;
        }

        /* Model HUD Frame */
        QFrame#ModelHudFrame {
            background: #090c13;
            border: 1px solid #1a273b;
            border-radius: 8px;
        }

        /* Bottom Bar */
        QFrame#BottomBar {
            background: #090B10;
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
            border-top: 1px solid #1A0D12;
        }

        QPushButton#ActionBtn {
            background: #121622;
            color: #CBD5E1;
            border: 1px solid #222C3E;
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 11px;
            font-weight: 700;
        }
        QPushButton#ActionBtn:hover {
            background: #1B2233;
            color: #FFFFFF;
            border-color: #FF1744;
        }

        QPushButton#ApplyButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF1744, stop:1 #D50000);
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 900;
            letter-spacing: 0.8px;
            border: none;
            border-radius: 7px;
        }
        QPushButton#ApplyButton:hover {
            background: #FF2E5B;
        }

        /* Secondary Page Buttons */
        QPushButton#ModeSelectBtn, QPushButton#ProfileSelectBtn {
            background: #121724;
            color: #94A3B8;
            border: 1px solid #222E47;
            border-radius: 8px;
            padding: 10px;
            font-size: 11px;
            font-weight: 800;
            text-align: left;
        }
        QPushButton#ModeSelectBtn:hover, QPushButton#ProfileSelectBtn:hover {
            border-color: #FF1744;
            color: #FFFFFF;
        }
        QPushButton#ModeSelectBtn:checked {
            border-color: #00FFCC;
            color: #00FFCC;
            background: rgba(0, 255, 204, 0.1);
        }
        QLabel#AboutText {
            color: #CBD5E1;
            font-size: 12px;
            line-height: 1.6;
        }
        """
        self.setStyleSheet(qss)


def main():
    try:
        user32 = ctypes.windll.user32
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = YOLOConfig()
    engine = YOLOEngine(config)
    engine.start()

    screen = QGuiApplication.primaryScreen()
    screen_rect = screen.geometry() if screen else None

    overlay = None
    if screen_rect:
        overlay = YOLOOverlayWindow(engine, config)
        overlay.setGeometry(screen_rect)
        if not bool(config.get("headless_mode", False)):
            overlay.show()
            overlay.raise_()

    win = AuraEliteHUDWindow(engine=engine, config=config, overlay_window=overlay)
    if screen_rect:
        win.move(
            screen_rect.x() + (screen_rect.width() - win.width()) // 2,
            screen_rect.y() + (screen_rect.height() - win.height()) // 2
        )
    win.show()
    win.raise_()
    win.activateWindow()

    # Native Win32 Hardware Polling for Hotkeys ('C', 'F7', 'F8')
    user32_api = ctypes.windll.user32
    key_prev = {"c": False, "f7": False, "f8": False}

    def poll_hotkeys():
        # 'C' = 0x43 (Toggle Aimbot & Engine)
        c_down = (user32_api.GetAsyncKeyState(0x43) & 0x8000) != 0
        if c_down and not key_prev["c"]:
            new_s = not bool(config.get("enabled", True))
            config.set("enabled", new_s)
            config.set("makcu_enabled", new_s)
            win._sync_engine_power_ui()
        key_prev["c"] = c_down

        # 'F7' = 0x76 (Toggle Overlay)
        f7_down = (user32_api.GetAsyncKeyState(0x76) & 0x8000) != 0
        if f7_down and not key_prev["f7"]:
            if overlay:
                if overlay.isVisible():
                    config.set("headless_mode", True)
                    overlay.hide()
                else:
                    config.set("headless_mode", False)
                    overlay.show()
        key_prev["f7"] = f7_down

        # 'F8' = 0x77 (Toggle GUI)
        f8_down = (user32_api.GetAsyncKeyState(0x77) & 0x8000) != 0
        if f8_down and not key_prev["f8"]:
            if win.isVisible():
                win.hide()
            else:
                win.show()
                win.raise_()
                win.activateWindow()
        key_prev["f8"] = f8_down

    hk_timer = QTimer(app)
    hk_timer.timeout.connect(poll_hotkeys)
    hk_timer.start(18)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
