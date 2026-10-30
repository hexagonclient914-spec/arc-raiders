"""
ARC Raiders / Valorant - YOLO Tactical Vision HUD & MAKCU Hardware Control
Next-Gen Cyberpunk / Tactical Esports Control Dashboard (PyQt6)
Features:
- Custom Animated Neon CyberSwitch Toggles
- Interactive Live HUD Preview Canvas (Real-time visualization of ESP, FOV, Crosshair, Head Diamond)
- Instant Settings Search & Filter Bar
- Custom Preset Save / Load Manager (.json)
- Enhanced Sliders with Pill Value Badges & Quick Fine-Tuning
- Full Visual Customization (Colors, Opacity, Box Style, Thickness)
"""

import os
import json
import math
import subprocess
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox,
    QCheckBox, QPushButton, QFileDialog, QScrollArea, QFrame,
    QStackedWidget, QButtonGroup, QLineEdit, QColorDialog, QSizePolicy,
    QGridLayout, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QPoint, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QLinearGradient, QRadialGradient, QPolygonF, QCursor
)

try:
    from aurapart import AIM_KEY_DISPLAY_NAMES
except ImportError:
    from makcu_aimbot import AIM_KEY_DISPLAY_NAMES


# =====================================================================
# 1. CUSTOM MODERN CYBERPUNK TOGGLE SWITCH WIDGET
# =====================================================================

class CyberSwitch(QCheckBox):
    """
    Modern iOS / Cyberpunk pill toggle switch with smooth animated knob
    and glowing neon state indicator. Drop-in replacement for QCheckBox.
    """
    def __init__(self, text="", parent=None, accent_color="#00F0FF"):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._accent = QColor(accent_color)
        self._position = 1.0 if self.isChecked() else 0.0

        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.stateChanged.connect(self._on_state_changed)
        self.setMinimumHeight(26)

    @pyqtProperty(float)
    def knob_pos(self):
        return self._position

    @knob_pos.setter
    def knob_pos(self, pos):
        self._position = pos
        self.update()

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._position = 1.0 if checked else 0.0
        self.update()

    def _on_state_changed(self, state):
        self._anim.stop()
        self._anim.setStartValue(self._position)
        self._anim.setEndValue(1.0 if state else 0.0)
        self._anim.start()

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        sw_w = 40
        sw_h = 20
        sw_y = (self.height() - sw_h) / 2.0
        sw_rect = QRectF(2, sw_y, sw_w, sw_h)

        # Track Background & Border
        if self._position > 0.05:
            r = int(20 + (self._accent.red() - 20) * self._position * 0.35)
            g = int(28 + (self._accent.green() - 28) * self._position * 0.35)
            b = int(42 + (self._accent.blue() - 42) * self._position * 0.35)
            track_bg = QColor(r, g, b)
            border_c = QColor(
                int(42 + (self._accent.red() - 42) * self._position),
                int(56 + (self._accent.green() - 56) * self._position),
                int(78 + (self._accent.blue() - 78) * self._position),
            )
        else:
            track_bg = QColor("#121826")
            border_c = QColor("#263248")

        painter.setBrush(QBrush(track_bg))
        painter.setPen(QPen(border_c, 1.3))
        painter.drawRoundedRect(sw_rect, sw_h / 2.0, sw_h / 2.0)

        # Knob Position & Color
        knob_d = 14.0
        knob_min_x = 5.0
        knob_max_x = sw_w - knob_d - 1.0
        knob_x = knob_min_x + (knob_max_x - knob_min_x) * self._position
        knob_y = sw_y + (sw_h - knob_d) / 2.0

        if self._position > 0.5:
            knob_color = self._accent
            # Subtle outer glow
            glow = QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 85)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QRectF(knob_x - 2, knob_y - 2, knob_d + 4, knob_d + 4))
        else:
            knob_color = QColor("#68778D")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(knob_color))
        painter.drawEllipse(QRectF(knob_x, knob_y, knob_d, knob_d))

        # Label Text
        text_x = sw_w + 12
        text_rect = QRectF(text_x, 0, self.width() - text_x, self.height())
        painter.setFont(self.font())
        text_c = QColor("#F0F6FC") if self.isChecked() else QColor("#9BA9BB")
        painter.setPen(text_c)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        painter.end()


# =====================================================================
# 2. INTERACTIVE LIVE HUD PREVIEW WIDGET
# =====================================================================

class LiveHUDPreviewWidget(QFrame):
    """
    Real-time interactive mini-canvas simulating the in-game Tactical HUD.
    Shows live changes to Bounding Box style, Colors, Crosshair, FOV Ring,
    Headshot Diamond, and Snaplines before even tabbing into the game.
    """
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setMinimumHeight(195)
        self.setMaximumHeight(215)
        self.setStyleSheet("""
            LiveHUDPreviewWidget {
                background-color: #070A10;
                border: 1px solid #1E293B;
                border-radius: 10px;
            }
        """)
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(35)

    def _tick(self):
        self._pulse = (self._pulse + 0.08) % (math.pi * 2)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        # 1. Tactical Grid Background
        grid_pen = QPen(QColor(22, 32, 48, 130), 1, Qt.PenStyle.SolidLine)
        painter.setPen(grid_pen)
        step = 24
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y)

        # Header Tag
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#64748B"))
        painter.drawText(QRectF(12, 8, 260, 16), Qt.AlignmentFlag.AlignLeft, "LIVE HUD VORSCHAU // ECHTZEIT-SIMULATION")

        opacity = float(self.config.get("overlay_opacity", 0.95))
        painter.setOpacity(max(0.15, min(1.0, opacity)))

        # 2. Simulated MAKCU FOV Circle
        if self.config.get("makcu_enabled", True) and self.config.get("makcu_show_fov", True):
            raw_fov = float(self.config.get("makcu_fov", 160))
            scaled_fov = min(h * 0.44, max(24.0, raw_fov * 0.42))
            fov_c = QColor(0, 255, 204, 70)
            painter.setPen(QPen(fov_c, 1.2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), scaled_fov, scaled_fov)

        # 3. Simulated Targets (1 Closest Target near center-right, 1 Secondary Target on left)
        sim_targets = [
            {
                "x1": cx + 22, "y1": cy - 52, "x2": cx + 78, "y2": cy + 58,
                "is_closest": True, "label": "RAIDER", "conf": 94, "dist": 38
            },
            {
                "x1": cx - 135, "y1": cy - 38, "x2": cx - 90, "y2": cy + 48,
                "is_closest": False, "label": "ENEMY", "conf": 82, "dist": 112
            }
        ]

        # Snaplines
        if self.config.get("show_snaplines", True):
            origin_mode = self.config.get("snapline_origin", "bottom")
            ox, oy = cx, (h if origin_mode == "bottom" else cy)
            for t in sim_targets:
                tx = (t["x1"] + t["x2"]) / 2.0
                ty = t["y2"]
                if t["is_closest"]:
                    c = QColor(self.config.get("closest_color", "#00FFCC"))
                    c.setAlpha(190)
                    painter.setPen(QPen(c, 1.8, Qt.PenStyle.SolidLine))
                else:
                    c = QColor(self.config.get("enemy_color", "#FF3355"))
                    c.setAlpha(80)
                    painter.setPen(QPen(c, 1.0, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(ox, oy), QPointF(tx, ty))

        # Target Boxes
        box_style = self.config.get("box_style", "corners")
        thickness = int(self.config.get("box_thickness", 2))
        show_boxes = self.config.get("show_boxes", True)

        for t in sim_targets:
            x1, y1, x2, y2 = t["x1"], t["y1"], t["x2"], t["y2"]
            bw, bh = x2 - x1, y2 - y1
            tcx = (x1 + x2) / 2.0
            is_closest = t["is_closest"]
            col_hex = self.config.get("closest_color", "#00FFCC") if is_closest else self.config.get("enemy_color", "#FF3355")
            base_c = QColor(col_hex)

            if show_boxes:
                fill_c = QColor(base_c.red(), base_c.green(), base_c.blue(), 28 if is_closest else 16)
                painter.setBrush(QBrush(fill_c))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(QRectF(x1, y1, bw, bh))

                if box_style == "corners":
                    clen = min(int(self.config.get("corner_length", 14)), int(bw // 3), int(bh // 3))
                    painter.setPen(QPen(base_c, thickness))
                    painter.drawLine(QPointF(x1, y1), QPointF(x1 + clen, y1))
                    painter.drawLine(QPointF(x1, y1), QPointF(x1, y1 + clen))
                    painter.drawLine(QPointF(x2, y1), QPointF(x2 - clen, y1))
                    painter.drawLine(QPointF(x2, y1), QPointF(x2, y1 + clen))
                    painter.drawLine(QPointF(x1, y2), QPointF(x1 + clen, y2))
                    painter.drawLine(QPointF(x1, y2), QPointF(x1, y2 - clen))
                    painter.drawLine(QPointF(x2, y2), QPointF(x2 - clen, y2))
                    painter.drawLine(QPointF(x2, y2), QPointF(x2, y2 - clen))
                elif box_style == "glow":
                    glow_c = QColor(base_c.red(), base_c.green(), base_c.blue(), 75)
                    painter.setPen(QPen(glow_c, thickness + 4))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(QRectF(x1, y1, bw, bh), 3, 3)
                    painter.setPen(QPen(base_c, thickness))
                    painter.drawRoundedRect(QRectF(x1, y1, bw, bh), 3, 3)
                else:
                    painter.setPen(QPen(base_c, thickness))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(QRectF(x1, y1, bw, bh))

                if self.config.get("show_labels", True):
                    lbl = t["label"]
                    if self.config.get("show_confidence", True):
                        lbl += f" {t['conf']}%"
                    if self.config.get("show_distance", True):
                        lbl += f" [{t['dist']}px]"
                    painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
                    tw = painter.fontMetrics().horizontalAdvance(lbl) + 10
                    th = 15
                    bx, by = x1, y1 - th - 3
                    painter.setBrush(QBrush(QColor(10, 14, 22, 220)))
                    painter.setPen(QPen(base_c, 1))
                    painter.drawRoundedRect(QRectF(bx, by, tw, th), 2, 2)
                    painter.setPen(base_c if is_closest else QColor("#E2E8F0"))
                    painter.drawText(QRectF(bx, by, tw, th), Qt.AlignmentFlag.AlignCenter, lbl)

            # Headshot Diamond
            if self.config.get("show_head_marker", True):
                hx, hy = tcx, y1 + bh * 0.16
                hr = max(5.0, bw * 0.14)
                hc = QColor(self.config.get("head_marker_color", "#FFE600"))
                painter.setBrush(QBrush(QColor(hc.red(), hc.green(), hc.blue(), 40)))
                painter.setPen(QPen(hc, 1.4))
                poly = QPolygonF([
                    QPointF(hx, hy - hr),
                    QPointF(hx + hr, hy),
                    QPointF(hx, hy + hr),
                    QPointF(hx - hr, hy)
                ])
                painter.drawPolygon(poly)

        # 4. Center Crosshair
        if self.config.get("show_crosshair", True):
            ch_c = QColor(self.config.get("crosshair_color", "#00FFCC"))
            ch_sz = int(self.config.get("crosshair_size", 4))
            glow = QColor(ch_c.red(), ch_c.green(), ch_c.blue(), 80)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QPointF(cx, cy), ch_sz * 2.2, ch_sz * 2.2)
            painter.setBrush(QBrush(ch_c))
            painter.drawEllipse(QPointF(cx, cy), ch_sz / 2.0, ch_sz / 2.0)

        painter.end()


# =====================================================================
# 2.5. LIVE FRAMETIME SPARKLINE GRAPH WIDGET
# =====================================================================

class FrametimeSparklineWidget(QWidget):
    """Real-time frametime sparkline graph embedded in the Telemetry Bar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(115, 28)
        self.setMaximumHeight(32)
        self.history = []

    def set_history(self, hist):
        self.history = list(hist[-50:]) if hist else []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        h = self.height()

        painter.setBrush(QBrush(QColor("#0B0F19")))
        painter.setPen(QPen(QColor("#1E293B"), 1))
        painter.drawRoundedRect(QRectF(0, 0, w, h), 4, 4)

        if len(self.history) < 2:
            painter.end()
            return

        max_v = max(18.0, max(self.history) * 1.15)
        step_x = (w - 6) / max(1, len(self.history) - 1)

        poly = QPolygonF()
        for i, val in enumerate(self.history):
            px = 3.0 + i * step_x
            norm = min(1.0, max(0.0, val / max_v))
            py = (h - 3.0) - norm * (h - 6.0)
            poly.append(QPointF(px, py))

        # Fill under curve
        fill_poly = QPolygonF(poly)
        fill_poly.append(QPointF(poly[-1].x(), h - 2.0))
        fill_poly.append(QPointF(poly[0].x(), h - 2.0))
        grad = QLinearGradient(QPointF(0, 0), QPointF(0, h))
        grad.setColorAt(0.0, QColor(0, 240, 255, 80))
        grad.setColorAt(1.0, QColor(0, 240, 255, 5))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPolygon(fill_poly)

        # Crisp top line
        painter.setPen(QPen(QColor("#00F0FF"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(poly)
        painter.end()


# =====================================================================
# 3. MAIN CYBER-SUITE SETTINGS WINDOW
# =====================================================================

class YOLOSettingsWindow(QWidget):
    def __init__(self, engine, config, overlay_window=None):
        super().__init__()
        self.engine = engine
        self.config = config
        self.overlay_window = overlay_window
        self._searchable_cards = []
        self.drag_position = QPoint()

        self.setWindowTitle("⚡ AURA TACTICAL VISION // CONTROL CENTER v5.0")
        self.resize(1020, 780)
        self.setMinimumSize(920, 680)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.init_style()
        self.init_ui()

        # Timer to update live diagnostic metrics
        self.stat_timer = QTimer(self)
        self.stat_timer.timeout.connect(self.update_live_metrics)
        self.stat_timer.start(200)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def init_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                color: #D0D8E4;
                font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
                font-size: 13px;
            }

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
                font-size: 14px;
                width: 28px;
                height: 28px;
                border-radius: 4px;
            }
            QPushButton#TitleCloseBtn:hover {
                background: #FF2A55;
                color: #ffffff;
            }

            /* Sidebar Navigation */
            #Sidebar {
                background-color: #0d1118;
                border-right: 1px solid #1c2333;
                border-bottom-left-radius: 12px;
                min-width: 215px;
                max-width: 225px;
            }
            QPushButton.nav_btn {
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
                padding: 13px 18px;
                text-align: left;
                color: #8b9bb4;
                font-weight: 600;
                font-size: 12px;
                letter-spacing: 0.6px;
            }
            QPushButton.nav_btn:hover {
                background-color: #151a24;
                color: #ffffff;
            }
            QPushButton.nav_btn:checked {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #102428, stop:1 #0d1118);
                border-left: 3px solid #00FFCC;
                color: #00FFCC;
                font-weight: bold;
            }

            /* Telemetry Top Bar */
            #TelemetryBar {
                background-color: #11151f;
                border-bottom: 1px solid #1c2333;
                border-top-right-radius: 12px;
            }
            .hud_card {
                background-color: #0b0e15;
                border: 1px solid #1c2333;
                border-radius: 8px;
                padding: 8px 14px;
            }
            .hud_card:hover {
                border-color: #2b3850;
            }
            .hud_title {
                color: #8b9bb4;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            .hud_val {
                color: #00FFCC;
                font-family: 'Consolas', monospace;
                font-size: 15px;
                font-weight: bold;
            }
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            .hud_val {
                color: #00F0FF;
                font-family: 'Consolas', monospace;
                font-size: 15px;
                font-weight: bold;
            }

            /* Search Input */
            QLineEdit#SearchInput {
                background-color: #101622;
                border: 1px solid #1E293B;
                border-radius: 7px;
                padding: 7px 12px;
                color: #F8FAFC;
                font-size: 12px;
            }
            QLineEdit#SearchInput:focus {
                border: 1px solid #00F0FF;
                background-color: #131B2B;
            }

            /* Container Cards */
            .section_card {
                background-color: #0E131F;
                border: 1px solid #192234;
                border-radius: 10px;
                padding: 16px;
            }
            .section_card:hover {
                border-color: #24324C;
            }
            .section_header {
                color: #00F0FF;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 1.1px;
            }
            .section_sub {
                color: #6E7E91;
                font-size: 11px;
            }

            /* Value Pill Badge */
            .val_badge {
                background-color: #131C2E;
                border: 1px solid #23324D;
                border-radius: 5px;
                padding: 2px 8px;
                color: #00F0FF;
                font-family: 'Consolas', monospace;
                font-weight: bold;
                font-size: 12px;
            }

            /* Sliders */
            QSlider::groove:horizontal {
                height: 6px;
                background: #161F30;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0077FF, stop:1 #00F0FF);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00F0FF;
                border: 2px solid #FFFFFF;
                width: 16px;
                height: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #FFFFFF;
                border-color: #00F0FF;
            }

            /* Combos & Inputs */
            QComboBox {
                background-color: #131A28;
                border: 1px solid #243047;
                border-radius: 6px;
                padding: 7px 12px;
                color: #F0F6FC;
                font-weight: 500;
            }
            QComboBox:hover {
                border-color: #00F0FF;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #101622;
                border: 1px solid #00F0FF;
                selection-background-color: #00F0FF;
                selection-color: #080B11;
                color: #F0F6FC;
                padding: 4px;
                outline: none;
            }

            /* Standard Action Buttons */
            QPushButton.action_btn {
                background-color: #141C2B;
                border: 1px solid #24314A;
                border-radius: 7px;
                padding: 8px 14px;
                color: #E2E8F0;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton.action_btn:hover {
                background-color: #1A2538;
                border-color: #00F0FF;
                color: #00F0FF;
            }
            QPushButton.step_btn {
                background-color: #141C2B;
                border: 1px solid #222F46;
                border-radius: 5px;
                color: #94A3B8;
                font-weight: bold;
                font-family: 'Consolas', monospace;
                min-width: 24px;
                max-width: 24px;
                min-height: 22px;
                max-height: 22px;
                padding: 0px;
            }
            QPushButton.step_btn:hover {
                background-color: #1D283E;
                border-color: #00F0FF;
                color: #00F0FF;
            }

            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #090D14;
                width: 7px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #1E293B;
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00F0FF;
            }
        """)

    # ==================== HELPER BUILDERS ====================

    def _register_card(self, card: QFrame, search_keywords: str, tab_idx: int):
        self._searchable_cards.append((card, search_keywords.lower(), tab_idx))

    def _create_slider_row(self, parent_layout, label_text: str, min_v: int, max_v: int, cur_v: int, fmt_fn, on_change_fn, step=1):
        """Creates a modern slider row with label, [-] [+] micro-step buttons, and a neon pill value badge."""
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #C8D4E3; font-weight: 500;")
        top_row.addWidget(lbl, stretch=1)

        btn_minus = QPushButton("-")
        btn_minus.setProperty("class", "step_btn")
        btn_minus.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        val_lbl = QLabel(fmt_fn(cur_v))
        val_lbl.setProperty("class", "val_badge")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_plus = QPushButton("+")
        btn_plus.setProperty("class", "step_btn")
        btn_plus.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        top_row.addWidget(btn_minus)
        top_row.addWidget(val_lbl)
        top_row.addWidget(btn_plus)
        parent_layout.addLayout(top_row)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(cur_v)
        slider.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        def _handle_val(v):
            val_lbl.setText(fmt_fn(v))
            on_change_fn(v)

        slider.valueChanged.connect(_handle_val)
        btn_minus.clicked.connect(lambda: slider.setValue(max(min_v, slider.value() - step)))
        btn_plus.clicked.connect(lambda: slider.setValue(min(max_v, slider.value() + step)))

        parent_layout.addWidget(slider)
        return slider, val_lbl

    def _create_color_picker_btn(self, config_key: str, default_hex: str):
        btn = QPushButton()
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFixedSize(78, 26)

        def _update_btn_style(hex_col):
            btn.setText(hex_col.upper())
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_col};
                    border: 1px solid #FFFFFF;
                    border-radius: 5px;
                    color: #05070B;
                    font-family: 'Consolas', monospace;
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    border: 2px solid #00F0FF;
                }}
            """)

        curr_col = self.config.get(config_key, default_hex)
        _update_btn_style(curr_col)

        def _pick():
            initial = QColor(self.config.get(config_key, default_hex))
            c = QColorDialog.getColor(initial, self, "Wähle HUD Farbe")
            if c.isValid():
                hex_str = c.name().upper()
                self.config.set(config_key, hex_str)
                _update_btn_style(hex_str)
                if hasattr(self, "hud_preview"):
                    self.hud_preview.update()

        btn.clicked.connect(_pick)
        return btn

    # ==================== MAIN UI LAYOUT ====================

    def init_ui(self):
        # Outer container with rounded corners and drop shadow
        self.central_container = QFrame(self)
        self.central_container.setObjectName("CentralContainer")
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.addWidget(self.central_container)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 210))
        shadow.setOffset(0, 6)
        self.central_container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.central_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 0. Custom Cyberpunk Title Bar
        title_bar = QFrame()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(46)
        t_lay = QHBoxLayout(title_bar)
        t_lay.setContentsMargins(18, 0, 14, 0)

        lbl_logo = QLabel("⚡ AURA")
        lbl_logo.setObjectName("TitleLogo")
        lbl_title = QLabel("TACTICAL VISION  |  CONTROL CENTER v5.0")
        lbl_title.setObjectName("TitleText")

        t_lay.addWidget(lbl_logo)
        t_lay.addWidget(lbl_title)
        t_lay.addStretch()

        btn_min = QPushButton("—")
        btn_min.setObjectName("TitleBtn")
        btn_min.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_min.clicked.connect(self.showMinimized)
        t_lay.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("TitleCloseBtn")
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.clicked.connect(self.hide)
        t_lay.addWidget(btn_close)

        container_layout.addWidget(title_bar)

        # Body Layout (Sidebar + Content)
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        container_layout.addWidget(body_widget)

        # ---------------- 1. LEFT SIDEBAR NAVIGATION ----------------
        sidebar = QFrame(body_widget)
        sidebar.setObjectName("Sidebar")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 18, 0, 16)
        side_layout.setSpacing(4)

        # Brand Header
        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(18, 0, 16, 12)
        brand_box.setSpacing(2)
        lbl_brand = QLabel("TACTICAL // VISION")
        lbl_brand.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        lbl_brand.setStyleSheet("color: #00F0FF; letter-spacing: 1.5px;")
        lbl_sub = QLabel("CYBER-SUITE v4.0 PRO")
        lbl_sub.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        lbl_sub.setStyleSheet("color: #64748B; letter-spacing: 1px;")
        brand_box.addWidget(lbl_brand)
        brand_box.addWidget(lbl_sub)
        side_layout.addLayout(brand_box)

        self.btn_group_nav = QButtonGroup(self)
        self.btn_group_nav.setExclusive(True)

        nav_items = [
            ("🎮  PROFILES & PRESETS", 0),
            ("🎯  AIM ASSIST (MAKCU)", 1),
            ("⚡  TRIGGERBOT", 2),
            ("👁️  VISUALS & HUD", 3),
            ("🚀  AI & ENGINE", 4),
        ]

        self.nav_buttons = []
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "nav_btn")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, i=idx: self.switch_tab(i))
            self.btn_group_nav.addButton(btn, idx)
            side_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        side_layout.addStretch()

        # Quick Master Status Box in Sidebar
        quick_frame = QFrame()
        quick_frame.setStyleSheet("""
            QFrame {
                background-color: #101624;
                border: 1px solid #1C283E;
                border-radius: 8px;
                margin: 0 12px 8px 12px;
                padding: 8px;
            }
        """)
        qf_lay = QVBoxLayout(quick_frame)
        qf_lay.setContentsMargins(6, 6, 6, 6)
        qf_lay.setSpacing(6)
        self.lbl_sidebar_hk = QLabel()
        self.lbl_sidebar_hk.setStyleSheet("color: #8A99AD; font-family: Consolas; font-size: 11px; border: none;")
        qf_lay.addWidget(self.lbl_sidebar_hk)
        side_layout.addWidget(quick_frame)

        # Master Power On/Off Button on Sidebar
        self.btn_side_power = QPushButton()
        self.btn_side_power.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_side_power.clicked.connect(self.toggle_master_power)
        side_layout.addWidget(self.btn_side_power)

        # Fast Toggle Overlay / Headless Mode button on sidebar bottom
        self.btn_side_overlay = QPushButton("👁️ HUD Overlay (F7)")
        self.btn_side_overlay.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_side_overlay.clicked.connect(self.toggle_overlay)
        side_layout.addWidget(self.btn_side_overlay)
        self._sync_headless_ui()
        self._sync_engine_power_ui()

        body_layout.addWidget(sidebar)

        # ---------------- 2. MAIN CONTENT AREA ----------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top Live Telemetry HUD Bar + Search Bar
        telemetry_bar = QFrame()
        telemetry_bar.setObjectName("TelemetryBar")
        tel_outer = QVBoxLayout(telemetry_bar)
        tel_outer.setContentsMargins(18, 12, 18, 12)
        tel_outer.setSpacing(10)

        tel_layout = QHBoxLayout()
        tel_layout.setSpacing(10)

        # Card 1: Inference FPS
        card_fps = QFrame()
        card_fps.setProperty("class", "hud_card")
        c1_lay = QVBoxLayout(card_fps)
        c1_lay.setContentsMargins(0, 0, 0, 0)
        c1_lay.setSpacing(2)
        lbl_c1_t = QLabel("INFERENCE FPS")
        lbl_c1_t.setProperty("class", "hud_title")
        self.lbl_fps_val = QLabel("0 FPS")
        self.lbl_fps_val.setProperty("class", "hud_val")
        self.lbl_fps_val.setStyleSheet("color: #00FF88;")
        c1_lay.addWidget(lbl_c1_t)
        c1_lay.addWidget(self.lbl_fps_val)
        tel_layout.addWidget(card_fps, stretch=1)

        # Card 2: End-to-End Latency + Live Frametime Sparkline
        card_lat = QFrame()
        card_lat.setProperty("class", "hud_card")
        c2_lay = QHBoxLayout(card_lat)
        c2_lay.setContentsMargins(0, 0, 0, 0)
        c2_lay.setSpacing(8)
        c2_left = QVBoxLayout()
        c2_left.setContentsMargins(0, 0, 0, 0)
        c2_left.setSpacing(2)
        lbl_c2_t = QLabel("FRAME LATENCY")
        lbl_c2_t.setProperty("class", "hud_title")
        self.lbl_lat_val = QLabel("0.0 ms")
        self.lbl_lat_val.setProperty("class", "hud_val")
        self.lbl_lat_val.setStyleSheet("color: #00F0FF;")
        c2_left.addWidget(lbl_c2_t)
        c2_left.addWidget(self.lbl_lat_val)
        c2_lay.addLayout(c2_left)

        self.sparkline_widget = FrametimeSparklineWidget(card_lat)
        c2_lay.addWidget(self.sparkline_widget, stretch=1)
        tel_layout.addWidget(card_lat, stretch=1)

        # Card 3: Active Threats
        card_thr = QFrame()
        card_thr.setProperty("class", "hud_card")
        c3_lay = QVBoxLayout(card_thr)
        c3_lay.setContentsMargins(0, 0, 0, 0)
        c3_lay.setSpacing(2)
        lbl_c3_t = QLabel("ACTIVE THREATS")
        lbl_c3_t.setProperty("class", "hud_title")
        self.lbl_thr_val = QLabel("0")
        self.lbl_thr_val.setProperty("class", "hud_val")
        self.lbl_thr_val.setStyleSheet("color: #FF2A55;")
        c3_lay.addWidget(lbl_c3_t)
        c3_lay.addWidget(self.lbl_thr_val)
        tel_layout.addWidget(card_thr, stretch=1)

        # Card 4: Hardware Bridge Status
        card_hw = QFrame()
        card_hw.setProperty("class", "hud_card")
        c4_lay = QVBoxLayout(card_hw)
        c4_lay.setContentsMargins(0, 0, 0, 0)
        c4_lay.setSpacing(2)
        lbl_c4_t = QLabel("MAKCU HARDWARE")
        lbl_c4_t.setProperty("class", "hud_title")
        self.lbl_hw_val = QLabel("Probing...")
        self.lbl_hw_val.setProperty("class", "hud_val")
        self.lbl_hw_val.setStyleSheet("color: #FFE600;")
        c4_lay.addWidget(lbl_c4_t)
        c4_lay.addWidget(self.lbl_hw_val)
        tel_layout.addWidget(card_hw, stretch=1)

        tel_outer.addLayout(tel_layout)

        # Search & Quick Filter Row + Compact Mini-Mode Toggle
        self._mini_mode_active = False
        self._sidebar_ref = sidebar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("🔍 Einstellungen durchsuchen (z.B. 'FOV', 'Smooth', 'Headshot', 'Farbe', 'TensorRT', 'Keybind')...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.on_search_filter)
        search_row.addWidget(self.search_input, stretch=1)

        self.btn_mini_mode = QPushButton("🗕 Mini-Bar")
        self.btn_mini_mode.setProperty("class", "action_btn")
        self.btn_mini_mode.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_mini_mode.setToolTip("Kompakter Mini-Statusbalken für den 2. Monitor")
        self.btn_mini_mode.clicked.connect(self.toggle_mini_mode)
        search_row.addWidget(self.btn_mini_mode)

        tel_outer.addLayout(search_row)

        right_layout.addWidget(telemetry_bar)

        # Stacked Pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self.create_tab_profiles())
        self.stack.addWidget(self.create_tab_aimbot())
        self.stack.addWidget(self.create_tab_triggerbot())
        self.stack.addWidget(self.create_tab_visuals())
        self.stack.addWidget(self.create_tab_engine())
        right_layout.addWidget(self.stack, stretch=1)

        # Bottom Status & Quick Action Bar
        self.bottom_bar = QFrame()
        self.bottom_bar.setStyleSheet("background-color: #090D15; border-top: 1px solid #161F30; padding: 10px 18px;")
        b_lay = QHBoxLayout(self.bottom_bar)
        b_lay.setContentsMargins(0, 0, 0, 0)
        b_lay.setSpacing(10)

        self.status_bar_lbl = QLabel("Ready // Powered by NVIDIA TensorRT & MAKCU ESP32")
        self.status_bar_lbl.setStyleSheet("color: #7E8E9F; font-family: Consolas; font-size: 11px;")
        b_lay.addWidget(self.status_bar_lbl, stretch=1)

        btn_save_preset = QPushButton("💾 Preset Speichern")
        btn_save_preset.setProperty("class", "action_btn")
        btn_save_preset.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_save_preset.clicked.connect(self.save_custom_preset)
        b_lay.addWidget(btn_save_preset)

        btn_load_preset = QPushButton("📂 Preset Laden")
        btn_load_preset.setProperty("class", "action_btn")
        btn_load_preset.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_load_preset.clicked.connect(self.load_custom_preset)
        b_lay.addWidget(btn_load_preset)

        btn_reset = QPushButton("↺ Defaults")
        btn_reset.setProperty("class", "action_btn")
        btn_reset.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_reset.clicked.connect(self.reset_defaults)
        b_lay.addWidget(btn_reset)

        right_layout.addWidget(self.bottom_bar)
        body_layout.addWidget(right_panel, stretch=1)

    def toggle_mini_mode(self):
        self._mini_mode_active = not getattr(self, "_mini_mode_active", False)
        if self._mini_mode_active:
            self._saved_geom = self.geometry()
            self._sidebar_ref.hide()
            self.stack.hide()
            self.bottom_bar.hide()
            self.search_input.hide()
            self.btn_mini_mode.setText("🗖 Vollbild-Menü")
            self.setMinimumSize(640, 128)
            self.resize(680, 134)
        else:
            self._sidebar_ref.show()
            self.stack.show()
            self.bottom_bar.show()
            self.search_input.show()
            self.btn_mini_mode.setText("🗕 Mini-Bar")
            self.setMinimumSize(860, 640)
            if hasattr(self, "_saved_geom"):
                self.setGeometry(self._saved_geom)
            else:
                self.resize(960, 760)

    def switch_tab(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)

    def on_search_filter(self, query: str):
        q = query.strip().lower()
        if not q:
            for card, _, _ in self._searchable_cards:
                card.setVisible(True)
            return

        first_matched_tab = None
        for card, keywords, tab_idx in self._searchable_cards:
            matched = q in keywords
            card.setVisible(matched)
            if matched and first_matched_tab is None:
                first_matched_tab = tab_idx

        if first_matched_tab is not None and self.stack.currentIndex() != first_matched_tab:
            self.switch_tab(first_matched_tab)

    # ==================== TAB 1: PROFILES & PRESETS ====================
    def create_tab_profiles(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        # Card 1: 1-Click Game Profiles
        card = QFrame()
        card.setProperty("class", "section_card")
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(12)

        lbl_t = QLabel("🎮 1-KLICK GAME-PROFILE PRESETS")
        lbl_t.setProperty("class", "section_header")
        c_lay.addWidget(lbl_t)

        lbl_desc = QLabel("Wähle dein Spiel für sofortige Optimierung von ONNX/TensorRT-Modell, Scan-Zone, Aim-Bone und Farben:")
        lbl_desc.setProperty("class", "section_sub")
        c_lay.addWidget(lbl_desc)

        grid_p = QGridLayout()
        grid_p.setHorizontalSpacing(12)
        grid_p.setVerticalSpacing(12)

        self.btn_prof_bf = QPushButton("💥 BATTLEFIELD 2042\n135+ FPS · ONNX CUDA · 640px ROI\nbattlefield_2042.onnx")
        self.btn_prof_bf.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_prof_bf.clicked.connect(lambda: self.apply_game_profile("battlefield"))
        grid_p.addWidget(self.btn_prof_bf, 0, 0)

        self.btn_prof_val = QPushButton("🎯 VALORANT\n150+ FPS · Neck-Lock · 480px ROI\nvalorant_30k_640.onnx")
        self.btn_prof_val.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_prof_val.clicked.connect(lambda: self.apply_game_profile("valorant"))
        grid_p.addWidget(self.btn_prof_val, 0, 1)

        self.btn_prof_cs2 = QPushButton("🔫 CS2 ESPORTS\n200+ FPS · Head-Diamond · 640px ROI\nGGMCS2.onnx")
        self.btn_prof_cs2.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_prof_cs2.clicked.connect(lambda: self.apply_game_profile("cs2"))
        grid_p.addWidget(self.btn_prof_cs2, 1, 0)

        self.btn_prof_arc = QPushButton("🤖 ARC RAIDERS\n130+ FPS · 13 Klassen · 640px ROI\narc_raiders_yolo11_better.onnx")
        self.btn_prof_arc.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_prof_arc.clicked.connect(lambda: self.apply_game_profile("arc_raiders"))
        grid_p.addWidget(self.btn_prof_arc, 1, 1)

        c_lay.addLayout(grid_p)
        lay.addWidget(card)
        self._register_card(card, "profile battlefield 2042 valorant cs2 arc raiders spiel preset modell onnx", 0)

        # Card 2: Quick Playstyle Tuning (Legit vs Semi-Rage vs Pro)
        card_style = QFrame()
        card_style.setProperty("class", "section_card")
        cs_lay = QVBoxLayout(card_style)
        cs_lay.setSpacing(12)

        lbl_st = QLabel("⚡ PLAYSTYLE SCHNELLWAHL (AIM-DYNAMIK)")
        lbl_st.setProperty("class", "section_header")
        cs_lay.addWidget(lbl_st)

        lbl_st_sub = QLabel("Passt Aim-Smoothness, FOV-Radius, Prediction und Triggerbot mit einem Klick an deinen Spielstil an:")
        lbl_st_sub.setProperty("class", "section_sub")
        cs_lay.addWidget(lbl_st_sub)

        row_st = QHBoxLayout()
        row_st.setSpacing(10)

        btn_legit = QPushButton("🛡️ LEGIT / TOURNAMENT\nSanftes Damping (Smooth 6.5 · FOV 110px)")
        btn_legit.setProperty("class", "action_btn")
        btn_legit.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_legit.clicked.connect(lambda: self.apply_playstyle_preset("legit"))
        row_st.addWidget(btn_legit)

        btn_hybrid = QPushButton("⚔️ COMPETITIVE HYBRID\nPerfekte Balance (Smooth 4.2 · FOV 160px)")
        btn_hybrid.setProperty("class", "action_btn")
        btn_hybrid.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_hybrid.clicked.connect(lambda: self.apply_playstyle_preset("hybrid"))
        row_st.addWidget(btn_hybrid)

        btn_rage = QPushButton("🔥 AGGRESSIVE LOCK\nSchneller Snap + Trigger (Smooth 2.2 · FOV 220px)")
        btn_rage.setProperty("class", "action_btn")
        btn_rage.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_rage.clicked.connect(lambda: self.apply_playstyle_preset("aggressive"))
        row_st.addWidget(btn_rage)

        cs_lay.addLayout(row_st)
        lay.addWidget(card_style)
        self._register_card(card_style, "playstyle legit tournament competitive hybrid aggressive rage smooth fov", 0)

        # Card 2.5: Global Keybinds Configuration
        card_hk = QFrame()
        card_hk.setProperty("class", "section_card")
        chk_lay = QVBoxLayout(card_hk)
        chk_lay.setSpacing(10)

        lbl_hk_title = QLabel("⌨️ HOTKEYS & AN/AUS KEYBINDS")
        lbl_hk_title.setProperty("class", "section_header")
        chk_lay.addWidget(lbl_hk_title)

        lbl_hk_sub = QLabel("Klicke auf einen Keybind-Button und drücke eine beliebige Taste (Standard An/Aus ist 'C'):")
        lbl_hk_sub.setProperty("class", "section_sub")
        chk_lay.addWidget(lbl_hk_sub)

        row_hks = QHBoxLayout()
        row_hks.setSpacing(12)

        self.btn_bind_engine = self._create_keybind_btn("hotkey_toggle_engine", "c", "⚡ System An/Aus")
        self.btn_bind_overlay = self._create_keybind_btn("hotkey_toggle_overlay", "f7", "👁️ Overlay Ein/Aus")
        self.btn_bind_settings = self._create_keybind_btn("hotkey_toggle_settings", "f8", "🖥️ Menü Ein/Aus")

        row_hks.addWidget(self.btn_bind_engine)
        row_hks.addWidget(self.btn_bind_overlay)
        row_hks.addWidget(self.btn_bind_settings)
        chk_lay.addLayout(row_hks)

        self.chk_hk_sound = CyberSwitch("🔊 Akustisches Audio-Feedback (Signalton beim An/Aus-Schalten — ideal für No-Overlay Modus)", accent_color="#00FF88")
        self.chk_hk_sound.setChecked(self.config.get("hotkey_sound", True))
        self.chk_hk_sound.stateChanged.connect(lambda s: self.config.set("hotkey_sound", bool(s)))
        chk_lay.addWidget(self.chk_hk_sound)

        lay.addWidget(card_hk)
        self._register_card(card_hk, "hotkey keybind taste c f7 f8 an aus toggle sound audio beep", 0)

        # Card 3: Live HUD Preview on Dashboard
        card_prev = QFrame()
        card_prev.setProperty("class", "section_card")
        cp_lay = QVBoxLayout(card_prev)
        cp_lay.setSpacing(10)

        lbl_pv = QLabel("👁️ INTERAKTIVE ECHTZEIT-HUD-VORSCHAU")
        lbl_pv.setProperty("class", "section_header")
        cp_lay.addWidget(lbl_pv)

        self.hud_preview = LiveHUDPreviewWidget(self.config, self)
        cp_lay.addWidget(self.hud_preview)
        lay.addWidget(card_prev)
        self._register_card(card_prev, "preview vorschau hud esp live simulation", 0)

        self._highlight_active_profile_button(self.config.get("active_game_profile", "valorant"))
        lay.addStretch()
        scroll.setWidget(content)
        return scroll

    # ==================== TAB 2: AIM ASSIST ====================
    def create_tab_aimbot(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        # Card A: Master Switch & Diagnostics
        card_top = QFrame()
        card_top.setProperty("class", "section_card")
        c_top = QVBoxLayout(card_top)
        c_top.setSpacing(10)

        row_m = QHBoxLayout()
        self.chk_makcu_enable = CyberSwitch("Hardware Aim Assist aktivieren (MAKCU ESP32 Dual-MCU)", accent_color="#00F0FF")
        self.chk_makcu_enable.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.chk_makcu_enable.setChecked(self.config.get("makcu_enabled", True))
        self.chk_makcu_enable.stateChanged.connect(lambda s: self.config.set("makcu_enabled", bool(s)))
        row_m.addWidget(self.chk_makcu_enable, stretch=1)

        self.btn_test_makcu = QPushButton("🎯 Test Move Wiggle")
        self.btn_test_makcu.setProperty("class", "action_btn")
        self.btn_test_makcu.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_test_makcu.clicked.connect(self.test_makcu_move)
        row_m.addWidget(self.btn_test_makcu)
        c_top.addLayout(row_m)

        self.lbl_makcu_status = QLabel("Status: Probing Port COM19...")
        self.lbl_makcu_status.setStyleSheet("color: #00FF88; font-family: Consolas; font-weight: bold; font-size: 11px;")
        c_top.addWidget(self.lbl_makcu_status)
        lay.addWidget(card_top)
        self._register_card(card_top, "makcu hardware aim assist aktivieren test move com port", 1)

        # Card B: Key & Bone Target
        card_kb = QFrame()
        card_kb.setProperty("class", "section_card")
        c_kb = QVBoxLayout(card_kb)
        c_kb.setSpacing(12)

        lbl_kb_t = QLabel("🎯 ZIELKNOCHEN & AKTIVIERUNGSTASTE")
        lbl_kb_t.setProperty("class", "section_header")
        c_kb.addWidget(lbl_kb_t)

        row_sel = QHBoxLayout()
        row_sel.setSpacing(14)
        col_k = QVBoxLayout()
        col_k.addWidget(QLabel("Aim Key (Aktivierungstaste):"))
        self.combo_aim_key = QComboBox()
        for disp, val in AIM_KEY_DISPLAY_NAMES:
            self.combo_aim_key.addItem(disp, val)
        curr_k = self.config.get("makcu_aim_key", "rmb")
        idx_k = self.combo_aim_key.findData(curr_k)
        if idx_k >= 0:
            self.combo_aim_key.setCurrentIndex(idx_k)
        self.combo_aim_key.currentIndexChanged.connect(self.on_makcu_key_changed)
        col_k.addWidget(self.combo_aim_key)
        row_sel.addLayout(col_k, stretch=1)

        col_b = QVBoxLayout()
        col_b.addWidget(QLabel("Target Bone (Zielzone):"))
        self.combo_bone = QComboBox()
        self.combo_bone.addItem("👑 Head (Obere 15% - Instant Headshot)", "head")
        self.combo_bone.addItem("🎯 Neck (Obere 25% - Empfohlen)", "neck")
        self.combo_bone.addItem("🛡️ Chest (Obere 40% - Körpermitte)", "chest")
        self.combo_bone.addItem("⭕ Center of Box (50%)", "center")
        curr_b = self.config.get("makcu_target_bone", "neck")
        idx_b = self.combo_bone.findData(curr_b)
        if idx_b >= 0:
            self.combo_bone.setCurrentIndex(idx_b)
        self.combo_bone.currentIndexChanged.connect(self.on_makcu_bone_changed)
        col_b.addWidget(self.combo_bone)
        row_sel.addLayout(col_b, stretch=1)
        c_kb.addLayout(row_sel)
        lay.addWidget(card_kb)
        self._register_card(card_kb, "aim key bone head neck chest kopf hals zielknochen taste", 1)

        # Card C: Snap Dynamics & FOV
        card_dyn = QFrame()
        card_dyn.setProperty("class", "section_card")
        c_dyn = QVBoxLayout(card_dyn)
        c_dyn.setSpacing(14)

        lbl_dyn_t = QLabel("⚙️ SNAP-DYNAMIK & FOV-KONTROLLE")
        lbl_dyn_t.setProperty("class", "section_header")
        c_dyn.addWidget(lbl_dyn_t)

        curr_smooth = int(float(self.config.get("makcu_smooth", 4.5)) * 10)
        self.slider_smooth, self.lbl_smooth_val = self._create_slider_row(
            c_dyn,
            "Aim Smoothness (S-Curve Damping — niedriger = schnellerer Snap):",
            10, 150, curr_smooth,
            lambda v: f"{v / 10.0:.1f}",
            self.on_makcu_smooth_changed,
            step=2
        )

        curr_fov = int(self.config.get("makcu_fov", 160))
        self.slider_fov, self.lbl_fov_val = self._create_slider_row(
            c_dyn,
            "Aim FOV Radius (Erfassungsbereich ums Fadenkreuz):",
            40, 350, curr_fov,
            lambda v: f"{v} px",
            self.on_makcu_fov_changed,
            step=5
        )

        c_dyn.addSpacing(4)
        self.chk_makcu_lock = CyberSwitch("Lock Mouse on Target (100% Steady Aim - unterdrückt Handzittern)", accent_color="#00FF88")
        self.chk_makcu_lock.setChecked(self.config.get("makcu_lock_on_target", True))
        self.chk_makcu_lock.stateChanged.connect(lambda s: self.config.set("makcu_lock_on_target", bool(s)))
        c_dyn.addWidget(self.chk_makcu_lock)

        self.chk_show_fov = CyberSwitch("Tactical Aim FOV Ring auf dem HUD einblenden", accent_color="#00F0FF")
        self.chk_show_fov.setChecked(self.config.get("makcu_show_fov", True))
        self.chk_show_fov.stateChanged.connect(lambda s: self.config.set("makcu_show_fov", bool(s)))
        c_dyn.addWidget(self.chk_show_fov)

        self.chk_makcu_pred = CyberSwitch("Velocity Lead Prediction (Bewegungskompensation für laufende Ziele)", accent_color="#00F0FF")
        self.chk_makcu_pred.setChecked(self.config.get("makcu_prediction", False))
        self.chk_makcu_pred.stateChanged.connect(lambda s: self.config.set("makcu_prediction", bool(s)))
        c_dyn.addWidget(self.chk_makcu_pred)

        lay.addWidget(card_dyn)
        self._register_card(card_dyn, "smoothness fov radius lock mouse steady aim prediction bewegung", 1)

        lay.addStretch()
        scroll.setWidget(content)
        return scroll

    # ==================== TAB 3: TRIGGERBOT ====================
    def create_tab_triggerbot(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        card = QFrame()
        card.setProperty("class", "section_card")
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(14)

        lbl_t = QLabel("⚡ AUTO-TRIGGERBOT CONFIGURATION")
        lbl_t.setProperty("class", "section_header")
        c_lay.addWidget(lbl_t)

        self.chk_makcu_trig = CyberSwitch("Auto-Triggerbot aktivieren (Feuert automatisch bei Fadenkreuz-Kontakt)", accent_color="#FFE600")
        self.chk_makcu_trig.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.chk_makcu_trig.setChecked(self.config.get("makcu_triggerbot", False))
        self.chk_makcu_trig.stateChanged.connect(lambda s: self.config.set("makcu_triggerbot", bool(s)))
        c_lay.addWidget(self.chk_makcu_trig)

        self.chk_trig_head = CyberSwitch("👑 Headshot Only (Feuert nur exakt auf die anatomische Kopf-Hitbox)", accent_color="#FF2A55")
        self.chk_trig_head.setChecked(self.config.get("makcu_triggerbot_head_only", True))
        self.chk_trig_head.stateChanged.connect(lambda s: self.config.set("makcu_triggerbot_head_only", bool(s)))
        c_lay.addWidget(self.chk_trig_head)

        self.chk_trig_stop = CyberSwitch("🛑 Nur bei Stillstand schießen (Stop-to-Shoot / Counter-Strafe: kein Schuss bei WASD)", accent_color="#00FFAA")
        self.chk_trig_stop.setChecked(self.config.get("makcu_triggerbot_stop_to_shoot", True))
        self.chk_trig_stop.stateChanged.connect(lambda s: self.config.set("makcu_triggerbot_stop_to_shoot", bool(s)))
        c_lay.addWidget(self.chk_trig_stop)

        self.chk_trig_snap = CyberSwitch("🎯 Aim-Stabilisierung (Kein Schuss während schnellen Aimbot-Flicks / Snaps)", accent_color="#38BDF8")
        self.chk_trig_snap.setChecked(self.config.get("makcu_triggerbot_snap_check", True))
        self.chk_trig_snap.stateChanged.connect(lambda s: self.config.set("makcu_triggerbot_snap_check", bool(s)))
        c_lay.addWidget(self.chk_trig_snap)

        c_lay.addSpacing(6)
        row_m = QHBoxLayout()
        row_m.addWidget(QLabel("Trigger Feuermodus:"))
        self.combo_trig_mode = QComboBox()
        self.combo_trig_mode.addItem("🎯 Tap-Fire (1-Tap Reset für Vandal / Sheriff)", "tap")
        self.combo_trig_mode.addItem("💥 Burst-Fire (2-Schuss Salve)", "burst")
        self.combo_trig_mode.addItem("🔥 Full-Auto (Dauerfeuer / Spray)", "auto")
        curr_tm = self.config.get("makcu_triggerbot_mode", "tap")
        idx_tm = self.combo_trig_mode.findData(curr_tm)
        if idx_tm >= 0:
            self.combo_trig_mode.setCurrentIndex(idx_tm)
        self.combo_trig_mode.currentIndexChanged.connect(
            lambda: self.config.set("makcu_triggerbot_mode", self.combo_trig_mode.currentData())
        )
        row_m.addWidget(self.combo_trig_mode, stretch=1)
        c_lay.addLayout(row_m)

        # Reaction Delay Slider
        curr_delay = int(self.config.get("makcu_triggerbot_delay_ms", 35))
        self.slider_trig_delay, self.lbl_trig_delay_val = self._create_slider_row(
            c_lay,
            "Trigger Reaktions-Intervall (Click Delay):",
            10, 150, curr_delay,
            lambda v: f"{v} ms",
            lambda v: self.config.set("makcu_triggerbot_delay_ms", v),
            step=5
        )

        # Recoil Reset Slider
        curr_recoil = int(self.config.get("makcu_triggerbot_recoil_delay_ms", 180))
        self.slider_recoil, self.lbl_recoil_val = self._create_slider_row(
            c_lay,
            "Recoil Reset Pause (Wartezeit zwischen Schüssen für 100% Präzision):",
            80, 400, curr_recoil,
            lambda v: f"{v} ms",
            self.on_recoil_slider_changed,
            step=10
        )

        lay.addWidget(card)
        self._register_card(card, "triggerbot headshot tap burst auto recoil delay schuss vandal", 2)

        lay.addStretch()
        scroll.setWidget(content)
        return scroll

    # ==================== TAB 4: VISUALS & HUD ====================
    def create_tab_visuals(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        # Card 1: Streamer & Box Styling
        card_st = QFrame()
        card_st.setProperty("class", "section_card")
        c_st = QVBoxLayout(card_st)
        c_st.setSpacing(12)

        lbl_s = QLabel("🎥 STREAMER BYPASS & ESP BOX-DESIGN")
        lbl_s.setProperty("class", "section_header")
        c_st.addWidget(lbl_s)

        self.chk_headless = CyberSwitch("👻 Pure No-Overlay Mode (0% HUD Rendering / Komplett unsichtbar)", accent_color="#FFE600")
        self.chk_headless.setChecked(bool(self.config.get("headless_mode", False)))
        def on_headless_toggle(s):
            is_hl = bool(s)
            self.config.set("headless_mode", is_hl)
            if self.overlay_window:
                if is_hl:
                    self.overlay_window.hide()
                else:
                    self.overlay_window.show()
            self._sync_headless_ui()
        self.chk_headless.stateChanged.connect(on_headless_toggle)
        c_st.addWidget(self.chk_headless)

        self.chk_streamer = CyberSwitch("Streamer Mode (Overlay 100% unsichtbar für OBS, Discord & Medal Clips)", accent_color="#00FF88")
        self.chk_streamer.setChecked(self.config.get("streamer_mode", True))
        def on_streamer_toggle(s):
            self.config.set("streamer_mode", bool(s))
            if hasattr(self.overlay_window, "apply_streamer_mode"):
                self.overlay_window.apply_streamer_mode()
        self.chk_streamer.stateChanged.connect(on_streamer_toggle)
        c_st.addWidget(self.chk_streamer)

        self.chk_boxes = CyberSwitch("Detection Boxes anzeigen (ESP Rahmen um Gegner zeichnen)", accent_color="#00F0FF")
        self.chk_boxes.setChecked(self.config.get("show_boxes", True))
        self.chk_boxes.stateChanged.connect(lambda s: self.config.set("show_boxes", bool(s)))
        c_st.addWidget(self.chk_boxes)

        # Box Style & Thickness Row
        row_style = QHBoxLayout()
        row_style.setSpacing(14)
        row_style.addWidget(QLabel("Box-Stil:"))
        self.combo_box_style = QComboBox()
        self.combo_box_style.addItem("📐 Sci-Fi Ecken (Corners)", "corners")
        self.combo_box_style.addItem("🔲 Vollständiger Rahmen (Full Box)", "box")
        self.combo_box_style.addItem("✨ Neon Cyber-Glow Rahmen (Glow)", "glow")
        curr_bs = self.config.get("box_style", "corners")
        idx_bs = self.combo_box_style.findData(curr_bs)
        if idx_bs >= 0:
            self.combo_box_style.setCurrentIndex(idx_bs)
        self.combo_box_style.currentIndexChanged.connect(
            lambda: self.config.set("box_style", self.combo_box_style.currentData())
        )
        row_style.addWidget(self.combo_box_style, stretch=1)
        c_st.addLayout(row_style)

        # Opacity & Thickness Sliders
        curr_op = int(float(self.config.get("overlay_opacity", 0.95)) * 100)
        self.slider_opacity, _ = self._create_slider_row(
            c_st,
            "HUD Gesamt-Deckkraft (Overlay Opacity):",
            20, 100, curr_op,
            lambda v: f"{v}%",
            lambda v: self.config.set("overlay_opacity", v / 100.0),
            step=5
        )

        curr_thick = int(self.config.get("box_thickness", 2))
        self.slider_thick, _ = self._create_slider_row(
            c_st,
            "Linienstärke der Boxen (Thickness):",
            1, 5, curr_thick,
            lambda v: f"{v} px",
            lambda v: self.config.set("box_thickness", v),
            step=1
        )

        lay.addWidget(card_st)
        self._register_card(card_st, "streamer obs discord boxen esp stil corners glow deckkraft opacity thickness", 3)

        # Card 2: Custom Color Theme Picker
        card_col = QFrame()
        card_col.setProperty("class", "section_card")
        c_col = QVBoxLayout(card_col)
        c_col.setSpacing(12)

        lbl_col = QLabel("🎨 FARBPALETTE & NEON-AKZENTE")
        lbl_col.setProperty("class", "section_header")
        c_col.addWidget(lbl_col)

        grid_col = QGridLayout()
        grid_col.setHorizontalSpacing(20)
        grid_col.setVerticalSpacing(10)

        grid_col.addWidget(QLabel("Gegner Standardfarbe:"), 0, 0)
        grid_col.addWidget(self._create_color_picker_btn("enemy_color", "#FF3355"), 0, 1)

        grid_col.addWidget(QLabel("Nächster Gegner (Locked):"), 0, 2)
        grid_col.addWidget(self._create_color_picker_btn("closest_color", "#00FFCC"), 0, 3)

        grid_col.addWidget(QLabel("Headshot Diamant:"), 1, 0)
        grid_col.addWidget(self._create_color_picker_btn("head_marker_color", "#FFE600"), 1, 1)

        grid_col.addWidget(QLabel("Zentrales Fadenkreuz:"), 1, 2)
        grid_col.addWidget(self._create_color_picker_btn("crosshair_color", "#00FFCC"), 1, 3)

        c_col.addLayout(grid_col)
        lay.addWidget(card_col)
        self._register_card(card_col, "farbe color gegner enemy closest headshot fadenkreuz crosshair neon", 3)

        # Card 3: Tactical HUD Elements
        card_el = QFrame()
        card_el.setProperty("class", "section_card")
        c_el = QVBoxLayout(card_el)
        c_el.setSpacing(10)

        lbl_el = QLabel("🎯 TACTICAL HUD RETICLES & TELEMETRIE")
        lbl_el.setProperty("class", "section_header")
        c_el.addWidget(lbl_el)

        row_toggles = QHBoxLayout()
        col1 = QVBoxLayout()
        col1.setSpacing(8)
        col2 = QVBoxLayout()
        col2.setSpacing(8)

        self.chk_closest = CyberSwitch("Nächsten Gegner hervorheben")
        self.chk_closest.setChecked(self.config.get("show_closest_indicator", True))
        self.chk_closest.stateChanged.connect(lambda s: self.config.set("show_closest_indicator", bool(s)))
        col1.addWidget(self.chk_closest)

        self.chk_zone = CyberSwitch("Scan-Zone Rahmen anzeigen")
        self.chk_zone.setChecked(self.config.get("show_scan_zone", True))
        self.chk_zone.stateChanged.connect(lambda s: self.config.set("show_scan_zone", bool(s)))
        col1.addWidget(self.chk_zone)

        self.chk_crosshair = CyberSwitch("Center Crosshair anzeigen")
        self.chk_crosshair.setChecked(self.config.get("show_crosshair", True))
        self.chk_crosshair.stateChanged.connect(lambda s: self.config.set("show_crosshair", bool(s)))
        col1.addWidget(self.chk_crosshair)

        self.chk_ontarget = CyberSwitch("On-Target Crosshair Lock-Shift")
        self.chk_ontarget.setChecked(self.config.get("on_target_crosshair", True))
        self.chk_ontarget.stateChanged.connect(lambda s: self.config.set("on_target_crosshair", bool(s)))
        col1.addWidget(self.chk_ontarget)

        self.chk_head_marker = CyberSwitch("Headshot Diamant-Reticle")
        self.chk_head_marker.setChecked(self.config.get("show_head_marker", True))
        self.chk_head_marker.stateChanged.connect(lambda s: self.config.set("show_head_marker", bool(s)))
        col2.addWidget(self.chk_head_marker)

        self.chk_hud_stats = CyberSwitch("Top-Left Diagnose-Leiste (FPS)")
        self.chk_hud_stats.setChecked(self.config.get("show_hud_stats", True))
        self.chk_hud_stats.stateChanged.connect(lambda s: self.config.set("show_hud_stats", bool(s)))
        col2.addWidget(self.chk_hud_stats)

        self.chk_labels = CyberSwitch("Klassen-Badges & Confidence %")
        self.chk_labels.setChecked(self.config.get("show_labels", True))
        self.chk_labels.stateChanged.connect(lambda s: self.config.set("show_labels", bool(s)))
        col2.addWidget(self.chk_labels)

        self.chk_ghost = CyberSwitch("Ghost Tracking (Hinter Deckung)")
        self.chk_ghost.setChecked(self.config.get("ghost_tracking", False))
        self.chk_ghost.stateChanged.connect(lambda s: self.config.set("ghost_tracking", bool(s)))
        col2.addWidget(self.chk_ghost)

        row_toggles.addLayout(col1)
        row_toggles.addLayout(col2)
        c_el.addLayout(row_toggles)

        # Snaplines Row
        c_el.addSpacing(6)
        row_snap = QHBoxLayout()
        self.chk_snaplines = CyberSwitch("Laser Snaplines (Ziel-Linien)")
        self.chk_snaplines.setChecked(self.config.get("show_snaplines", True))
        self.chk_snaplines.stateChanged.connect(lambda s: self.config.set("show_snaplines", bool(s)))
        row_snap.addWidget(self.chk_snaplines)

        self.combo_snap_origin = QComboBox()
        self.combo_snap_origin.addItems(["Von Bildschirm-Unterkante", "Vom Center-Fadenkreuz"])
        self.combo_snap_origin.setCurrentIndex(0 if self.config.get("snapline_origin", "bottom") == "bottom" else 1)
        self.combo_snap_origin.currentIndexChanged.connect(
            lambda idx: self.config.set("snapline_origin", "bottom" if idx == 0 else "center")
        )
        row_snap.addWidget(self.combo_snap_origin)
        c_el.addLayout(row_snap)

        lay.addWidget(card_el)
        self._register_card(card_el, "reticle crosshair snaplines ghost labels stats diagnose", 3)

        lay.addStretch()
        scroll.setWidget(content)
        return scroll

    # ==================== TAB 5: AI & ENGINE ====================
    def create_tab_engine(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        # Card 1: Models & TensorRT
        card_m = QFrame()
        card_m.setProperty("class", "section_card")
        c_m = QVBoxLayout(card_m)
        c_m.setSpacing(12)

        lbl_m = QLabel("🚀 DETECTION MODEL & TENSORRT ENGINE")
        lbl_m.setProperty("class", "section_header")
        c_m.addWidget(lbl_m)

        row_model = QHBoxLayout()
        self.combo_model = QComboBox()
        self.refresh_available_models()
        self.combo_model.currentIndexChanged.connect(self.on_model_changed)
        row_model.addWidget(self.combo_model, stretch=1)

        btn_browse = QPushButton("📁 Browse...")
        btn_browse.setProperty("class", "action_btn")
        btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse.clicked.connect(self.browse_custom_model)
        row_model.addWidget(btn_browse)

        self.btn_convert_fp16 = QPushButton("⚡ 1-Klick ONNX FP16 Optimizer")
        self.btn_convert_fp16.setProperty("class", "action_btn")
        self.btn_convert_fp16.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_convert_fp16.setStyleSheet("color: #00FF88; border-color: #00FF88; font-weight: bold;")
        self.btn_convert_fp16.clicked.connect(self.convert_current_onnx_to_fp16)
        row_model.addWidget(self.btn_convert_fp16)

        self.btn_convert_trt = QPushButton("🚀 In TensorRT kompilieren")
        self.btn_convert_trt.setProperty("class", "action_btn")
        self.btn_convert_trt.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_convert_trt.setStyleSheet("color: #00F0FF; border-color: #00F0FF; font-weight: bold;")
        self.btn_convert_trt.clicked.connect(self.convert_current_to_tensorrt)
        row_model.addWidget(self.btn_convert_trt)
        c_m.addLayout(row_model)

        lay.addWidget(card_m)
        self._register_card(card_m, "model tensorrt engine onnx pt kompilieren", 4)

        # Card 2: Scan Region & Combat Zoom
        card_r = QFrame()
        card_r.setProperty("class", "section_card")
        c_r = QVBoxLayout(card_r)
        c_r.setSpacing(12)

        lbl_r = QLabel("📐 AUFNAHMEBEREICH & DYNAMIC COMBAT ZOOM")
        lbl_r.setProperty("class", "section_header")
        c_r.addWidget(lbl_r)

        row_reg = QHBoxLayout()
        row_reg.addWidget(QLabel("Base Scan Region:"))
        self.combo_region = QComboBox()
        self.combo_region.addItems([
            "Center 480x480 (Max FPS / Sub-3ms Latency)",
            "Center 640x640 (Ausgewogenes Combat FOV)",
            "Center 960x960 (Weite Distanzen / Großes FOV)",
            "Full Screen (Kompletter Monitor)"
        ])
        reg_map = {"center_480": 0, "center_640": 1, "center_960": 2, "fullscreen": 3}
        curr_r = self.config.get("scan_region_mode", "center_640")
        self.combo_region.setCurrentIndex(reg_map.get(curr_r, 1))
        self.combo_region.currentIndexChanged.connect(self.on_region_changed)
        row_reg.addWidget(self.combo_region, stretch=1)
        c_r.addLayout(row_reg)

        self.chk_combat_zoom = CyberSwitch("⚡ Dynamic Combat Zoom (Schaltet im Gefecht automatisch auf 384px ROI für 200+ FPS)", accent_color="#00FF88")
        self.chk_combat_zoom.setChecked(self.config.get("dynamic_combat_zoom", True))
        self.chk_combat_zoom.stateChanged.connect(lambda s: self.config.set("dynamic_combat_zoom", bool(s)))
        c_r.addWidget(self.chk_combat_zoom)

        lay.addWidget(card_r)
        self._register_card(card_r, "scan region roi combat zoom 480 640 960 fullscreen", 4)

        # Card 3: Confidence & Filtering
        card_c = QFrame()
        card_c.setProperty("class", "section_card")
        c_c = QVBoxLayout(card_c)
        c_c.setSpacing(12)

        lbl_c = QLabel("🛡️ CONFIDENCE & TRACKING-FILTER")
        lbl_c.setProperty("class", "section_header")
        c_c.addWidget(lbl_c)

        curr_conf = int(self.config.get("confidence_threshold", 0.45) * 100)
        self.slider_conf, self.lbl_conf = self._create_slider_row(
            c_c,
            "Confidence Threshold (Mindest-Erkennungssicherheit):",
            10, 95, curr_conf,
            lambda v: f"{v}%",
            self.on_conf_changed,
            step=2
        )

        self.chk_all_classes = CyberSwitch("Alle Zielklassen des Modells erkennen")
        self.chk_all_classes.setChecked(self.config.get("detect_all_classes", True))
        self.chk_all_classes.stateChanged.connect(lambda s: self.config.set("detect_all_classes", bool(s)))
        c_c.addWidget(self.chk_all_classes)

        self.chk_smoothing = CyberSwitch("Anti-Jitter One-Euro / EMA Filter (Stabilisiert Bounding Boxes)")
        self.chk_smoothing.setChecked(self.config.get("box_smoothing", True))
        self.chk_smoothing.stateChanged.connect(lambda s: self.config.set("box_smoothing", bool(s)))
        c_c.addWidget(self.chk_smoothing)

        self.chk_stance = CyberSwitch("Stance Detection (Erkennt Stehen vs. Ducken für exakte Kopfhöhe)")
        self.chk_stance.setChecked(self.config.get("stance_detection", True))
        self.chk_stance.stateChanged.connect(lambda s: self.config.set("stance_detection", bool(s)))
        c_c.addWidget(self.chk_stance)

        lay.addWidget(card_c)
        self._register_card(card_c, "confidence threshold filter anti jitter smoothing stance ducken", 4)

        lay.addStretch()
        scroll.setWidget(content)
        return scroll

    # ==================== CALLBACKS & ACTIONS ====================
    def refresh_available_models(self):
        self.combo_model.clear()
        current = os.path.basename(self.config.get("model_path", "arc_raiders_yolo11n.pt"))
        models = []
        base_dir = os.path.dirname(os.path.abspath(__file__))
        for fname in os.listdir(base_dir):
            if fname.startswith("TensorrtExecutionProvider_"):
                continue
            if (fname.endswith(".pt") or fname.endswith(".engine") or fname.endswith(".onnx")) and fname not in models:
                models.append(fname)
        self.combo_model.addItems(models)
        idx = self.combo_model.findText(current)
        if idx >= 0:
            self.combo_model.setCurrentIndex(idx)
        else:
            self.combo_model.addItem(current)
            self.combo_model.setCurrentText(current)

    def on_model_changed(self, idx):
        model_name = self.combo_model.currentText()
        if model_name:
            self.config.set("model_path", model_name)
            self.engine.load_model(model_name)

    def browse_custom_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select YOLO Model (.pt / .onnx / .engine)", "", "YOLO Models (*.pt *.onnx *.engine);;All Files (*.*)"
        )
        if path:
            self.config.set("model_path", path)
            self.refresh_available_models()
            self.combo_model.setCurrentText(os.path.basename(path))
            self.engine.load_model(path)

    def convert_current_onnx_to_fp16(self):
        model_name = self.combo_model.currentText()
        if not model_name.lower().endswith(".onnx"):
            self.status_bar_lbl.setText("⚠️ Bitte wähle zuerst ein .onnx Modell für die FP16-Konvertierung aus!")
            return
        if model_name.lower().endswith("_fp16.onnx"):
            self.status_bar_lbl.setText("⚡ Modell ist bereits in FP16 Half-Precision optimiert!")
            return

        self.btn_convert_fp16.setEnabled(False)
        self.btn_convert_fp16.setText("⏳ Konvertiere FP16...")

        def _run_fp16():
            try:
                from yolo_engine import convert_onnx_to_fp16
                out_path = convert_onnx_to_fp16(model_name)
                fp16_name = os.path.basename(out_path)
                self.config.set("model_path", fp16_name)
                self.refresh_available_models()
                self.combo_model.setCurrentText(fp16_name)
                self.engine.load_model(fp16_name)
                self.btn_convert_fp16.setText("✅ FP16 Aktiv!")
                self.status_bar_lbl.setText(f"⚡ FP16 Optimizer erfolgreich: {fp16_name} geladen (GPU Preprocessing aktiv)")
            except Exception as e:
                print(f"[Settings] FP16 conversion error: {e}")
                self.btn_convert_fp16.setText("❌ FP16 Fehler")
            finally:
                self.btn_convert_fp16.setEnabled(True)

        threading.Thread(target=_run_fp16, daemon=True).start()

    def convert_current_to_tensorrt(self):
        model_name = self.combo_model.currentText()
        if model_name.endswith(".engine"):
            self.status_bar_lbl.setText("⚡ Modell ist bereits eine kompilierte TensorRT Engine!")
            return

        self.btn_convert_trt.setEnabled(False)
        self.btn_convert_trt.setText("⏳ Kompiliere TensorRT...")

        def run_conversion():
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                script = os.path.join(base_dir, "export_tensorrt.py")
                target = os.path.join(base_dir, model_name)
                subprocess.run(["py", script, target], check=True)

                engine_name = model_name.replace(".pt", ".engine").replace(".onnx", ".engine")
                self.config.set("model_path", engine_name)
                self.refresh_available_models()
                self.combo_model.setCurrentText(engine_name)
                self.engine.load_model(engine_name)
                self.btn_convert_trt.setText("✅ TensorRT Fertig!")
            except Exception as e:
                print(f"[Settings] Error converting to TensorRT: {e}")
                self.btn_convert_trt.setText("❌ Export fehlgeschlagen")
            finally:
                self.btn_convert_trt.setEnabled(True)

        threading.Thread(target=run_conversion, daemon=True).start()

    def on_region_changed(self, idx):
        modes = ["center_480", "center_640", "center_960", "fullscreen"]
        if 0 <= idx < len(modes):
            self.config.set("scan_region_mode", modes[idx])

    def on_conf_changed(self, val):
        conf = val / 100.0
        self.config.set("confidence_threshold", conf)

    def on_makcu_key_changed(self, idx):
        val = self.combo_aim_key.currentData()
        if val:
            self.config.set("makcu_aim_key", val)

    def on_makcu_bone_changed(self, idx):
        val = self.combo_bone.currentData()
        if val:
            self.config.set("makcu_target_bone", val)

    def on_makcu_smooth_changed(self, val):
        smooth = val / 10.0
        self.config.set("makcu_smooth", smooth)

    def on_makcu_fov_changed(self, val):
        self.config.set("makcu_fov", val)

    def on_recoil_slider_changed(self, val):
        self.config.set("makcu_triggerbot_recoil_delay_ms", val)

    def test_makcu_move(self):
        if hasattr(self.engine, "makcu_aimbot") and self.engine.makcu_aimbot:
            res = self.engine.makcu_aimbot.test_move()
            if res:
                self.lbl_makcu_status.setText("Status: Verified Move! 🟢")
            else:
                self.lbl_makcu_status.setText("Status: Move Failed ❌")

    def update_live_metrics(self):
        state = self.engine.get_state()
        fps = state.get("fps", 0.0)
        lat = state.get("latency_ms", 0.0)
        cap_ms = state.get("capture_ms", 0.05)
        ft_hist = state.get("frametime_history", [])
        target_count = len(state.get("targets", []))

        self.lbl_fps_val.setText(f"{fps:.0f} FPS")
        self.lbl_lat_val.setText(f"{lat:.1f} ms (Cap {cap_ms:.2f}ms)")
        self.lbl_thr_val.setText(str(target_count))
        if hasattr(self, "sparkline_widget"):
            self.sparkline_widget.set_history(ft_hist)

        makcu_st = state.get("makcu", {})
        if makcu_st.get("is_connected", False):
            port = makcu_st.get("port", "COM19")
            if makcu_st.get("is_mouse_locked", False):
                self.lbl_hw_val.setText(f"LOCKED 🔒 ({port})")
                self.lbl_hw_val.setStyleSheet("color: #00F0FF;")
            elif makcu_st.get("is_aiming", False):
                self.lbl_hw_val.setText(f"AIMING ⚡ ({port})")
                self.lbl_hw_val.setStyleSheet("color: #FFE600;")
            else:
                self.lbl_hw_val.setText(f"READY 🟢 ({port})")
                self.lbl_hw_val.setStyleSheet("color: #00FF88;")
            self.lbl_makcu_status.setText(f"MAKCU Connected: {port} (4,000,000 Baud High-Speed)")
        else:
            self.lbl_hw_val.setText("OFFLINE ⚪")
            self.lbl_hw_val.setStyleSheet("color: #64748B;")
            self.lbl_makcu_status.setText("MAKCU: Nicht verbunden")

    def _create_keybind_btn(self, config_key: str, default_key: str, label_prefix: str):
        btn = QPushButton()
        btn.setProperty("class", "action_btn")
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cur_k = str(self.config.get(config_key, default_key)).upper()
        btn.setText(f"{label_prefix}: [{cur_k}]")

        def _start_record():
            if getattr(self, "_is_recording_keybind", False):
                return
            self._is_recording_keybind = True
            btn.setText(f"{label_prefix}: [Taste drücken...]")
            btn.setStyleSheet("background-color: #1F1B12; border: 1px solid #FFE600; color: #FFE600; font-weight: bold; padding: 8px 14px; border-radius: 7px;")

            def _capture_key_win32():
                try:
                    import ctypes
                    import time
                    from yolo_main import VK_CODE_MAP
                    u32 = ctypes.windll.user32

                    # Wait briefly until mouse click on the button is released
                    time.sleep(0.18)

                    # Build reverse lookup (ignore LMB/RMB so clicking doesn't overwrite keybind)
                    vk_to_name = {}
                    for k_name, vk_val in VK_CODE_MAP.items():
                        if vk_val in (0x01, 0x02):
                            continue
                        if vk_val not in vk_to_name:
                            vk_to_name[vk_val] = k_name

                    # Snapshot currently held keys
                    initial_down = {vk for vk in vk_to_name if (u32.GetAsyncKeyState(vk) & 0x8000) != 0}
                    chosen_key = None
                    t0 = time.time()

                    while time.time() - t0 < 8.0:
                        for vk, k_name in vk_to_name.items():
                            is_down = (u32.GetAsyncKeyState(vk) & 0x8000) != 0
                            if is_down and vk not in initial_down:
                                chosen_key = k_name
                                break
                            elif not is_down and vk in initial_down:
                                initial_down.discard(vk)
                        if chosen_key is not None:
                            break
                        time.sleep(0.012)

                    if chosen_key and chosen_key not in ("esc", "escape"):
                        self.config.set(config_key, chosen_key)
                        if hasattr(self, "rebind_hotkeys_callback") and callable(self.rebind_hotkeys_callback):
                            self.rebind_hotkeys_callback()
                except Exception as e:
                    print(f"[Keybind] Error recording key via Win32: {e}")
                finally:
                    # Wait until key is released so it doesn't immediately trigger the hotkey
                    time.sleep(0.15)
                    self._is_recording_keybind = False
                    QTimer.singleShot(0, lambda: self._refresh_keybind_buttons())

            threading.Thread(target=_capture_key_win32, daemon=True).start()

        btn.clicked.connect(_start_record)
        return btn

    def _refresh_keybind_buttons(self):
        k_eng = str(self.config.get("hotkey_toggle_engine", "c")).upper()
        k_ov = str(self.config.get("hotkey_toggle_overlay", "f7")).upper()
        k_set = str(self.config.get("hotkey_toggle_settings", "f8")).upper()
        if hasattr(self, "btn_bind_engine"):
            self.btn_bind_engine.setText(f"⚡ System An/Aus: [{k_eng}]")
            self.btn_bind_engine.setStyleSheet("")
        if hasattr(self, "btn_bind_overlay"):
            self.btn_bind_overlay.setText(f"👁️ Overlay Ein/Aus: [{k_ov}]")
            self.btn_bind_overlay.setStyleSheet("")
        if hasattr(self, "btn_bind_settings"):
            self.btn_bind_settings.setText(f"🖥️ Menü Ein/Aus: [{k_set}]")
            self.btn_bind_settings.setStyleSheet("")
        self._sync_engine_power_ui()
        self._sync_headless_ui()

    def toggle_master_power(self):
        new_state = not bool(self.config.get("enabled", True))
        self.config.set("enabled", new_state)
        self.config.set("makcu_enabled", new_state)
        self._sync_engine_power_ui()
        k_eng = str(self.config.get("hotkey_toggle_engine", "c")).upper()
        if new_state:
            self.status_bar_lbl.setText(f"🟢 System & Aim AKTIVIERT (Keybind [{k_eng}])")
        else:
            self.status_bar_lbl.setText(f"🔴 System & Aim PAUSIERT (Keybind [{k_eng}])")

    def _sync_engine_power_ui(self):
        is_on = bool(self.config.get("enabled", True))
        k_eng = str(self.config.get("hotkey_toggle_engine", "c")).upper()
        k_ov = str(self.config.get("hotkey_toggle_overlay", "f7")).upper()
        k_set = str(self.config.get("hotkey_toggle_settings", "f8")).upper()

        if hasattr(self, "lbl_sidebar_hk"):
            self.lbl_sidebar_hk.setText(
                f"HOTKEYS:\n• [{k_eng}] : System An/Aus\n• [{k_ov}] : Overlay Ein/Aus\n• [{k_set}] : Menü Ein/Aus"
            )
        if hasattr(self, "chk_makcu_enable") and self.chk_makcu_enable.isChecked() != is_on:
            self.chk_makcu_enable.blockSignals(True)
            self.chk_makcu_enable.setChecked(is_on)
            self.chk_makcu_enable.blockSignals(False)

        if hasattr(self, "btn_side_power"):
            if is_on:
                self.btn_side_power.setText(f"🟢 SYSTEM AN ({k_eng})")
                self.btn_side_power.setStyleSheet("""
                    QPushButton {
                        background-color: #0D241B;
                        border: 1px solid #00FF88;
                        border-radius: 7px;
                        color: #00FF88;
                        font-weight: bold;
                        padding: 10px;
                        margin: 0 12px 6px 12px;
                    }
                    QPushButton:hover {
                        background-color: #00FF88;
                        color: #080B11;
                    }
                """)
            else:
                self.btn_side_power.setText(f"🔴 SYSTEM AUS ({k_eng})")
                self.btn_side_power.setStyleSheet("""
                    QPushButton {
                        background-color: #261019;
                        border: 1px solid #FF2A55;
                        border-radius: 7px;
                        color: #FF2A55;
                        font-weight: bold;
                        padding: 10px;
                        margin: 0 12px 6px 12px;
                    }
                    QPushButton:hover {
                        background-color: #FF2A55;
                        color: #FFFFFF;
                    }
                """)

    def _sync_headless_ui(self):
        is_hl = bool(self.config.get("headless_mode", False))
        if hasattr(self, "chk_headless") and self.chk_headless.isChecked() != is_hl:
            self.chk_headless.blockSignals(True)
            self.chk_headless.setChecked(is_hl)
            self.chk_headless.blockSignals(False)
        if hasattr(self, "btn_side_overlay"):
            if is_hl:
                self.btn_side_overlay.setText("👻 No-Overlay Aktiv (F7)")
                self.btn_side_overlay.setStyleSheet("""
                    QPushButton {
                        background-color: #241D0B;
                        border: 1px solid #FFE600;
                        border-radius: 7px;
                        color: #FFE600;
                        font-weight: bold;
                        padding: 10px;
                        margin: 0 12px;
                    }
                    QPushButton:hover {
                        background-color: #FFE600;
                        color: #080B11;
                    }
                """)
            else:
                self.btn_side_overlay.setText("👁️ HUD Overlay Aktiv (F7)")
                self.btn_side_overlay.setStyleSheet("""
                    QPushButton {
                        background-color: #111A2B;
                        border: 1px solid #00F0FF;
                        border-radius: 7px;
                        color: #00F0FF;
                        font-weight: bold;
                        padding: 10px;
                        margin: 0 12px;
                    }
                    QPushButton:hover {
                        background-color: #00F0FF;
                        color: #080B11;
                    }
                """)

    def toggle_overlay(self):
        is_hl = not bool(self.config.get("headless_mode", False))
        self.config.set("headless_mode", is_hl)
        if self.overlay_window:
            if is_hl:
                self.overlay_window.hide()
                self.status_bar_lbl.setText("👻 Pure No-Overlay Modus aktiviert (0% HUD-Last, F7 zum Umschalten)")
            else:
                self.overlay_window.show()
                self.status_bar_lbl.setText("👁️ HUD Overlay eingeblendet (F7 zum Umschalten)")
        self._sync_headless_ui()

    def save_custom_preset(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Preset speichern unter...", "my_tactical_preset.json", "JSON Preset (*.json)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.config.data, f, indent=4)
                self.status_bar_lbl.setText(f"💾 Preset erfolgreich gespeichert: {os.path.basename(path)}")
            except Exception as e:
                self.status_bar_lbl.setText(f"❌ Fehler beim Speichern: {e}")

    def load_custom_preset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Preset laden...", "", "JSON Preset (*.json)"
        )
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                for k, v in loaded.items():
                    self.config.set(k, v)
                self._sync_ui_from_config()
                self.status_bar_lbl.setText(f"📂 Preset geladen: {os.path.basename(path)}")
            except Exception as e:
                self.status_bar_lbl.setText(f"❌ Fehler beim Laden: {e}")

    def apply_playstyle_preset(self, style: str):
        if style == "legit":
            self.slider_smooth.setValue(65)
            self.slider_fov.setValue(110)
            self.chk_makcu_pred.setChecked(False)
            self.chk_makcu_trig.setChecked(False)
            self.status_bar_lbl.setText("🛡️ Playstyle aktiviert: LEGIT / TOURNAMENT (Sanftes Aim, 110px FOV)")
        elif style == "hybrid":
            self.slider_smooth.setValue(42)
            self.slider_fov.setValue(160)
            self.chk_makcu_pred.setChecked(True)
            self.chk_makcu_trig.setChecked(False)
            self.status_bar_lbl.setText("⚔️ Playstyle aktiviert: COMPETITIVE HYBRID (Smooth 4.2, 160px FOV)")
        elif style == "aggressive":
            self.slider_smooth.setValue(22)
            self.slider_fov.setValue(220)
            self.chk_makcu_pred.setChecked(True)
            self.chk_makcu_trig.setChecked(True)
            self.status_bar_lbl.setText("🔥 Playstyle aktiviert: AGGRESSIVE LOCK (Smooth 2.2, 220px FOV + Triggerbot)")

    def _sync_ui_from_config(self):
        self.slider_conf.setValue(int(float(self.config.get("confidence_threshold", 0.45)) * 100))
        self.slider_smooth.setValue(int(float(self.config.get("makcu_smooth", 4.5)) * 10))
        self.slider_fov.setValue(int(self.config.get("makcu_fov", 160)))
        self.slider_recoil.setValue(int(self.config.get("makcu_triggerbot_recoil_delay_ms", 180)))
        self.slider_opacity.setValue(int(float(self.config.get("overlay_opacity", 0.95)) * 100))
        self.slider_thick.setValue(int(self.config.get("box_thickness", 2)))
        self.chk_makcu_enable.setChecked(bool(self.config.get("makcu_enabled", True)))
        self.chk_makcu_trig.setChecked(bool(self.config.get("makcu_triggerbot", False)))
        self.chk_makcu_lock.setChecked(bool(self.config.get("makcu_lock_on_target", True)))
        self.chk_trig_head.setChecked(bool(self.config.get("makcu_triggerbot_head_only", True)))
        if hasattr(self, "chk_trig_stop"):
            self.chk_trig_stop.setChecked(bool(self.config.get("makcu_triggerbot_stop_to_shoot", True)))
        if hasattr(self, "chk_trig_snap"):
            self.chk_trig_snap.setChecked(bool(self.config.get("makcu_triggerbot_snap_check", True)))
        self.chk_streamer.setChecked(bool(self.config.get("streamer_mode", True)))
        self.chk_combat_zoom.setChecked(bool(self.config.get("dynamic_combat_zoom", True)))
        self.chk_boxes.setChecked(bool(self.config.get("show_boxes", True)))
        self.chk_snaplines.setChecked(bool(self.config.get("show_snaplines", True)))
        self._sync_headless_ui()
        self._highlight_active_profile_button(self.config.get("active_game_profile", "battlefield"))

    def reset_defaults(self):
        from yolo_config import DEFAULT_YOLO_CONFIG
        for k, v in DEFAULT_YOLO_CONFIG.items():
            self.config.set(k, v)
        self._sync_ui_from_config()
        self.status_bar_lbl.setText("↺ Alle Einstellungen auf Standardwerte zurückgesetzt!")

    def _highlight_active_profile_button(self, active):
        base_css = "padding: 14px; font-weight: bold; border-radius: 9px; text-align: left;"
        if hasattr(self, "btn_prof_bf"):
            if active == "battlefield":
                self.btn_prof_bf.setStyleSheet(f"background-color: #1E1810; border: 2px solid #FF8800; color: #FF8800; {base_css}")
            else:
                self.btn_prof_bf.setStyleSheet(f"background-color: #111724; border: 1px solid #1E293B; color: #FF9933; {base_css}")

        if active == "valorant":
            self.btn_prof_val.setStyleSheet(f"background-color: #1F1220; border: 2px solid #FF2A55; color: #FF2A55; {base_css}")
        else:
            self.btn_prof_val.setStyleSheet(f"background-color: #111724; border: 1px solid #1E293B; color: #FF5577; {base_css}")

        if active == "cs2":
            self.btn_prof_cs2.setStyleSheet(f"background-color: #1F1B12; border: 2px solid #FFE600; color: #FFE600; {base_css}")
        else:
            self.btn_prof_cs2.setStyleSheet(f"background-color: #111724; border: 1px solid #1E293B; color: #E5A93C; {base_css}")

        if active == "arc_raiders":
            self.btn_prof_arc.setStyleSheet(f"background-color: #0E2228; border: 2px solid #00F0FF; color: #00F0FF; {base_css}")
        else:
            self.btn_prof_arc.setStyleSheet(f"background-color: #111724; border: 1px solid #1E293B; color: #00E5FF; {base_css}")

    def apply_game_profile(self, profile_name):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        profiles = {
            "battlefield": {
                "name": "Battlefield 2042 (ONNX CUDA)",
                "onnx_model": "battlefield_2042.onnx",
                "engine_model": "battlefield_2042.engine",
                "pt_model": "battlefield_2042.pt",
                "scan_region": "center_640",
                "region_idx": 1,
                "confidence": 0.42,
                "enemy_color": "#FF3355",
                "closest_color": "#00FFCC",
                "box_style": "corners",
            },
            "valorant": {
                "name": "Valorant (High-Speed)",
                "onnx_model": "valorant_30k_640.onnx",
                "engine_model": "valorant_30k_640.engine",
                "pt_model": "valorant_30k_640.pt",
                "scan_region": "center_480",
                "region_idx": 0,
                "confidence": 0.50,
                "enemy_color": "#FF2A55",
                "closest_color": "#FFE600",
                "box_style": "box",
            },
            "cs2": {
                "name": "Counter-Strike 2",
                "onnx_model": "GGMCS2.onnx",
                "engine_model": "GGMCS2.engine",
                "pt_model": "GGMCS2.pt",
                "scan_region": "center_640",
                "region_idx": 1,
                "confidence": 0.45,
                "enemy_color": "#FF3355",
                "closest_color": "#00FFCC",
                "box_style": "corners",
            },
            "arc_raiders": {
                "name": "ARC Raiders",
                "onnx_model": "arc_raiders_yolo11_better.onnx",
                "engine_model": "arc_raiders_yolo11_better.engine",
                "pt_model": "arc_raiders_yolo11_better.pt",
                "scan_region": "center_640",
                "region_idx": 1,
                "confidence": 0.38,
                "enemy_color": "#FF3355",
                "closest_color": "#00FFCC",
                "box_style": "corners",
            }
        }

        prof = profiles.get(profile_name)
        if not prof:
            return

        # Prefer Direct TensorRT 10 .engine first (200-320+ FPS), then ONNX CUDA, then .pt
        model_name = prof["engine_model"]
        if not os.path.exists(os.path.join(base_dir, model_name)):
            if os.path.exists(os.path.join(base_dir, prof["onnx_model"])):
                model_name = prof["onnx_model"]
            else:
                model_name = prof["pt_model"]

        self.config.set("active_game_profile", profile_name)
        self.config.set("model_path", model_name)
        self.config.set("scan_region_mode", prof["scan_region"])
        self.config.set("confidence_threshold", prof["confidence"])
        self.config.set("enemy_color", prof["enemy_color"])
        self.config.set("closest_color", prof["closest_color"])
        self.config.set("box_style", prof["box_style"])
        self.config.set("show_head_marker", True)
        self.config.set("stance_detection", True)
        self.config.set("box_smoothing", True)
        self.config.set("adaptive_smoothing", True)
        self.config.set("latency_compensation", True)

        self.refresh_available_models()
        self.combo_region.setCurrentIndex(prof["region_idx"])
        self.slider_conf.setValue(int(prof["confidence"] * 100))
        self.chk_head_marker.setChecked(True)
        self.chk_stance.setChecked(True)
        self.chk_smoothing.setChecked(True)
        self._highlight_active_profile_button(profile_name)

        self.engine.load_model(model_name)
        self.status_bar_lbl.setText(f"🎮 Profil aktiviert: {prof['name']} ({model_name}) // Zero-Copy DIB + ONNX CUDA")
