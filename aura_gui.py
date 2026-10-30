"""
AURA TACTICAL VISION // CYBER-RED ELITE HUD GUI
Full-featured, ultra-sleek cyber-tactical graphical interface matching
the official AURA visual spec with hardware-accelerated rendering.
"""

import os
import sys
import json
import time
import ctypes

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QComboBox, QCheckBox, QFrame,
    QStackedWidget, QGraphicsDropShadowEffect, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QCursor, QIcon, QPainter, QBrush, QPen,
    QLinearGradient, QPixmap
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "yolo_config.json")
ASSETS_DIR = os.path.join(BASE_DIR, "gui_assets")


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
    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self.config_data = self._load_config()

        self.setWindowTitle("AURA // Smarter. Smoother. Deadlier.")
        self.resize(1024, 576)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._init_ui()
        self._apply_styling()
        self._sync_ui_from_config()

    def _load_config(self) -> dict:
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            print(f"[AURA GUI] Error saving config: {e}")

    # -----------------------------------------------------------------
    # UI INITIALIZATION & LAYOUT
    # -----------------------------------------------------------------
    def _init_ui(self):
        # Outer shell
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

        # 1. TOP HEADER / TITLEBAR
        main_vbox.addWidget(self._build_top_header())

        # 2. BODY (Sidebar + Stacked Content)
        body_hbox = QHBoxLayout()
        body_hbox.setContentsMargins(14, 10, 14, 10)
        body_hbox.setSpacing(12)

        # Sidebar
        body_hbox.addWidget(self._build_sidebar())

        # Main Pages (Stacked)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_aimbot_page())    # Index 0: Aimbot (matching screenshot)
        self.stack.addWidget(self._build_esp_page())       # Index 1: ESP
        self.stack.addWidget(self._build_settings_page())  # Index 2: Settings (Dual-PC, Hardware)
        self.stack.addWidget(self._build_configs_page())   # Index 3: Configs
        self.stack.addWidget(self._build_about_page())     # Index 4: About

        body_hbox.addWidget(self.stack, stretch=1)
        main_vbox.addLayout(body_hbox, stretch=1)

        # 3. BOTTOM ACTION BAR
        main_vbox.addWidget(self._build_bottom_bar())

    # -----------------------------------------------------------------
    # TOP HEADER WIDGET
    # -----------------------------------------------------------------
    def _build_top_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("TopHeader")
        header.setFixedHeight(68)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(18, 6, 18, 6)
        h_lay.setSpacing(14)

        # Left: Crosshair Badge
        crosshair_path = os.path.join(ASSETS_DIR, "crosshair.png")
        lbl_cross = QLabel()
        if os.path.exists(crosshair_path):
            pix = QPixmap(crosshair_path).scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_cross.setPixmap(pix)
        else:
            lbl_cross.setText("🎯")
            lbl_cross.setStyleSheet("font-size: 28px;")
        h_lay.addWidget(lbl_cross)

        h_lay.addStretch()

        # Center: AURA Title Banner
        banner_path = os.path.join(ASSETS_DIR, "title_banner.png")
        if os.path.exists(banner_path):
            lbl_banner = QLabel()
            pix = QPixmap(banner_path).scaled(240, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_banner.setPixmap(pix)
            h_lay.addWidget(lbl_banner)
        else:
            v_title = QVBoxLayout()
            v_title.setSpacing(0)
            lbl_crown = QLabel("👑 AURA")
            lbl_crown.setObjectName("TitleAura")
            lbl_slogan = QLabel("SMARTER. SMOOTHER. DEADLIER.")
            lbl_slogan.setObjectName("TitleSlogan")
            v_title.addWidget(lbl_crown, alignment=Qt.AlignmentFlag.AlignCenter)
            v_title.addWidget(lbl_slogan, alignment=Qt.AlignmentFlag.AlignCenter)
            h_lay.addLayout(v_title)

        h_lay.addStretch()

        # Right: Telemetry Status + Window Controls
        status_box = QHBoxLayout()
        status_box.setSpacing(12)

        lbl_dot = QLabel("●")
        lbl_dot.setObjectName("StatusDot")
        lbl_status = QLabel("Status: Ready")
        lbl_status.setObjectName("StatusText")

        lbl_sep = QLabel("|")
        lbl_sep.setObjectName("StatusSep")

        lbl_ai = QLabel("AI Engine: Online")
        lbl_ai.setObjectName("AiEngineText")

        status_box.addWidget(lbl_dot)
        status_box.addWidget(lbl_status)
        status_box.addWidget(lbl_sep)
        status_box.addWidget(lbl_ai)
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
        btn_close.clicked.connect(self.close)
        h_lay.addWidget(btn_close)

        return header

    # -----------------------------------------------------------------
    # LEFT VERTICAL SIDEBAR
    # -----------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("SidebarFrame")
        sidebar.setFixedWidth(168)
        s_lay = QVBoxLayout(sidebar)
        s_lay.setContentsMargins(10, 14, 10, 10)
        s_lay.setSpacing(8)

        self.nav_buttons = []
        tabs = [
            ("🎯", "Aimbot", 0),
            ("🖥️", "ESP", 1),
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

        # Soldier Graphic at bottom
        soldier_path = os.path.join(ASSETS_DIR, "soldier.png")
        if os.path.exists(soldier_path):
            lbl_soldier = QLabel()
            pix = QPixmap(soldier_path).scaled(148, 148, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_soldier.setPixmap(pix)
            lbl_soldier.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s_lay.addWidget(lbl_soldier)

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
    # PAGE 0: AIMBOT TAB (Exact layout matching user's image)
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
        self.slider_fov.valueChanged.connect(lambda v: self.lbl_fov_val.setText(f"{v}°"))
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
        self.slider_smooth.valueChanged.connect(lambda v: self.lbl_smooth_val.setText(f"{v/10.0:.1f}"))
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
        self.chk_smart = self._create_checkbox_row(c2_lay, "Smart Aim", "Aim more naturally", checked=True)
        self.chk_anti_snap = self._create_checkbox_row(c2_lay, "Anti Snap", "Avoid robotic movement", checked=True)
        c2_lay.addStretch()
        col2.addWidget(c2, stretch=1)

        # Card: Miscellaneous
        c3 = CyberCard("Miscellaneous", "🔧")
        c3_lay = c3.card_layout

        self.sw_recoil = self._create_switch_row(c3_lay, "No Recoil", checked=True)
        self.sw_spread = self._create_switch_row(c3_lay, "No Spread", checked=True)
        self.sw_auto_fire = self._create_switch_row(c3_lay, "Auto Fire", checked=False)
        self.sw_trigger = self._create_switch_row(c3_lay, "Trigger Bot", checked=False)
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
        self.sw_esp_skel = self._create_switch_row(c4_lay, "ESP Skeleton", checked=True)
        self.sw_esp_hp = self._create_switch_row(c4_lay, "ESP Health", checked=True)
        self.sw_esp_name = self._create_switch_row(c4_lay, "ESP Name", checked=False)
        self.sw_esp_dist = self._create_switch_row(c4_lay, "ESP Distance", checked=True)
        self.sw_snapline = self._create_switch_row(c4_lay, "Snapline", checked=True)
        c4_lay.addStretch()
        col3.addWidget(c4, stretch=3)

        # Card: Detection Status
        c5 = CyberCard("Detection Status", "🛡️")
        c5_lay = c5.card_layout

        shield_lay = QVBoxLayout()
        shield_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield_lay.setSpacing(4)

        shield_path = os.path.join(ASSETS_DIR, "shield.png")
        lbl_shield = QLabel()
        if os.path.exists(shield_path):
            pix = QPixmap(shield_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_shield.setPixmap(pix)
        else:
            lbl_shield.setText("🛡️")
            lbl_shield.setStyleSheet("font-size: 36px;")
        lbl_shield.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield_lay.addWidget(lbl_shield)

        lbl_undetected = QLabel("Undetected")
        lbl_undetected.setObjectName("UndetectedTitle")
        lbl_undetected.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield_lay.addWidget(lbl_undetected)

        lbl_safe = QLabel("Safe to Use")
        lbl_safe.setObjectName("UndetectedSub")
        lbl_safe.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield_lay.addWidget(lbl_safe)

        c5_lay.addLayout(shield_lay)
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
        else:
            self.lbl_aim_state.setText("Aimbot\nOFF")
            self.lbl_aim_state.setStyleSheet("color: #64748B; font-weight: 900; font-size: 13px;")

    # -----------------------------------------------------------------
    # PAGE 1: ESP CUSTOMIZATION TAB
    # -----------------------------------------------------------------
    def _build_esp_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        card = CyberCard("Visual Overlay & ESP Customization", "🖥️")
        c_lay = card.card_layout

        info = QLabel(
            "Configure real-time HUD rendering, bounding boxes, tracers, and stance markers.\n"
            "All visual elements are drawn transparently via hardware Direct2D overlays."
        )
        info.setObjectName("SubText")
        c_lay.addWidget(info)
        c_lay.addStretch()
        lay.addWidget(card)
        return page

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
        self.config_data["capture_source"] = mode
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

        lbl = QLabel("Active Game Profiles:")
        lbl.setObjectName("ControlTitle")
        c_lay.addWidget(lbl)

        games = ["Valorant (Direct TRT 10)", "Fortnite 100K (260+ FPS)", "ARC Raiders (YOLO11)", "CS2 (GGMCS2)", "Battlefield 2042"]
        for g in games:
            b = QPushButton(f"🎮  {g}")
            b.setObjectName("ProfileSelectBtn")
            c_lay.addWidget(b)

        c_lay.addStretch()
        lay.addWidget(card)
        return page

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
        cfg = self.config_data
        # FOV
        fov = int(cfg.get("makcu_fov", 120))
        self.slider_fov.setValue(fov)
        self.lbl_fov_val.setText(f"{fov}°")

        # Smoothness
        smooth = float(cfg.get("makcu_smooth", 3.0))
        self.slider_smooth.setValue(int(smooth * 10))
        self.lbl_smooth_val.setText(f"{smooth:.1f}")

        # Aim Key
        key = str(cfg.get("makcu_aim_key", "right")).lower()
        if "right" in key or "rmb" in key:
            self.combo_aim_key.setCurrentIndex(0)
        elif "alt" in key:
            self.combo_aim_key.setCurrentIndex(1)
        elif "4" in key:
            self.combo_aim_key.setCurrentIndex(2)
        elif "5" in key:
            self.combo_aim_key.setCurrentIndex(3)
        elif "always" in key:
            self.combo_aim_key.setCurrentIndex(4)

        # Target Bone
        bone = str(cfg.get("makcu_target_bone", "head")).lower()
        if "neck" in bone:
            self.combo_target.setCurrentIndex(1)
        elif "chest" in bone or "body" in bone:
            self.combo_target.setCurrentIndex(2)
        else:
            self.combo_target.setCurrentIndex(0)

        # AI Prediction
        self.chk_pred.setChecked(bool(cfg.get("makcu_prediction", True)))
        self.sw_trigger.setChecked(bool(cfg.get("makcu_triggerbot", False)))

        # ESP states
        self.sw_esp_box.setChecked(bool(cfg.get("show_boxes", True)))
        self.sw_snapline.setChecked(bool(cfg.get("show_snaplines", True)))
        self.sw_esp_dist.setChecked(bool(cfg.get("show_distance", True)))

    def _handle_apply_settings(self):
        # Update config dict
        self.config_data["makcu_fov"] = self.slider_fov.value()
        self.config_data["makcu_smooth"] = self.slider_smooth.value() / 10.0

        key_idx = self.combo_aim_key.currentIndex()
        key_map = {0: "right", 1: "alt", 2: "mouse4", 3: "mouse5", 4: "always"}
        self.config_data["makcu_aim_key"] = key_map.get(key_idx, "right")

        bone_idx = self.combo_target.currentIndex()
        bone_map = {0: "head", 1: "neck", 2: "chest"}
        self.config_data["makcu_target_bone"] = bone_map.get(bone_idx, "head")

        self.config_data["makcu_prediction"] = self.chk_pred.isChecked()
        self.config_data["makcu_triggerbot"] = self.sw_trigger.isChecked()

        self.config_data["show_boxes"] = self.sw_esp_box.isChecked()
        self.config_data["show_snaplines"] = self.sw_snapline.isChecked()
        self.config_data["show_distance"] = self.sw_esp_dist.isChecked()

        self._save_config()

        self.btn_apply.setText("✔  SETTINGS SAVED!")
        self.btn_apply.setStyleSheet("background: #00FF66; color: #000000; font-weight: 900; border-radius: 6px;")
        QApplication.processEvents()
        time.sleep(0.4)
        self.btn_apply.setText("✔  Apply Settings")
        self.btn_apply.setStyleSheet("")

    def _handle_load_config(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Load Tactical Preset", BASE_DIR, "JSON Files (*.json)")
        if fpath and os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
                self._sync_ui_from_config()
                self._save_config()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load config: {e}")

    def _handle_save_config(self):
        fpath, _ = QFileDialog.getSaveFileName(self, "Save Tactical Preset", os.path.join(BASE_DIR, "my_preset.json"), "JSON Files (*.json)")
        if fpath:
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(self.config_data, f, indent=4)
                QMessageBox.information(self, "Saved", "Preset successfully saved!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save preset: {e}")

    def _handle_reset_settings(self):
        self.slider_fov.setValue(120)
        self.slider_smooth.setValue(30)
        self.combo_aim_key.setCurrentIndex(0)
        self.combo_target.setCurrentIndex(0)
        self.chk_pred.setChecked(True)
        self.chk_smart.setChecked(True)
        self.chk_anti_snap.setChecked(True)
        self.sw_recoil.setChecked(True)
        self.sw_spread.setChecked(True)
        self.sw_auto_fire.setChecked(False)
        self.sw_trigger.setChecked(False)
        self.sw_esp_box.setChecked(True)
        self.sw_esp_skel.setChecked(True)
        self.sw_esp_hp.setChecked(True)
        self.sw_esp_name.setChecked(False)
        self.sw_esp_dist.setChecked(True)
        self.sw_snapline.setChecked(True)
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
    app = QApplication(sys.argv)
    win = AuraEliteHUDWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
