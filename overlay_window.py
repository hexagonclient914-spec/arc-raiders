"""
ARC Raiders Sound Overlay - High Performance Tactical HUD (v3.5)
Crystal clear 4-Quadrant Directional Arcs & Badges (LINKS, RECHTS, VORNE, HINTEN).
"""

import math
import ctypes
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QFont
)

class SoundOverlayWindow(QWidget):
    def __init__(self, audio_engine, config):
        super().__init__()
        self.audio_engine = audio_engine
        self.config = config

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.cur_level_l = 0.0
        self.cur_level_r = 0.0
        self.active_threats = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_clickthrough()

    def apply_clickthrough(self):
        try:
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            WS_EX_NOACTIVATE = 0x08000000

            styles = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, styles | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
        except Exception as e:
            print(f"Error setting clickthrough style: {e}")

    def update_frame(self):
        state = self.audio_engine.get_state()
        self.active_threats = state.get("threats", [])
        
        lerp_speed = 0.35
        self.cur_level_l += (state.get("level_l", 0.0) - self.cur_level_l) * lerp_speed
        self.cur_level_r += (state.get("level_r", 0.0) - self.cur_level_r) * lerp_speed

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = (h / 2.0) + self.config.get("y_offset", 0)

        mode = self.config.get("overlay_mode", "radar")
        global_opacity = self.config.get("overlay_opacity", 0.90)

        if self.config.get("show_crosshair", True):
            self.draw_crosshair(painter, cx, cy)

        if mode in ("radar", "all"):
            self.draw_tactical_radar(painter, cx, cy, global_opacity)
        if mode in ("edge", "all"):
            self.draw_edge_glow(painter, w, h, global_opacity)
        if mode == "bar":
            self.draw_tactical_bar(painter, cx, cy + 300, global_opacity)

        painter.end()

    def draw_crosshair(self, painter, cx, cy):
        color_hex = self.config.get("crosshair_color", "#00FFCC")
        dot_size = self.config.get("crosshair_size", 4)
        c = QColor(color_hex)

        glow = QColor(c.red(), c.green(), c.blue(), 75)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(cx, cy), dot_size * 2, dot_size * 2)

        painter.setBrush(QBrush(c))
        painter.drawEllipse(QPointF(cx, cy), dot_size / 2.0, dot_size / 2.0)

    def draw_tactical_radar(self, painter, cx, cy, opacity):
        base_radius = self.config.get("overlay_size", 220) / 2.0
        c_foot = QColor(self.config.get("footstep_color", "#FF8800"))
        c_gun = QColor(self.config.get("gunshot_color", "#00E5FF"))

        # Reference Compass Ring
        pen_ring = QPen(QColor(255, 255, 255, int(26 * opacity)), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen_ring)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), base_radius, base_radius)

        # Inner ring (<10m proximity boundary)
        inner_r = base_radius * 0.62
        painter.setPen(QPen(QColor(255, 255, 255, int(16 * opacity)), 1.0, Qt.PenStyle.DotLine))
        painter.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        # Cardinal Direction Ticks (N, S, W, E)
        pen_ticks = QPen(QColor(255, 255, 255, int(45 * opacity)), 1.2)
        painter.setPen(pen_ticks)
        for angle_deg in [0, 45, 90, 135, 180, 225, 270, 315]:
            rad = math.radians(angle_deg)
            r1 = base_radius - 6
            r2 = base_radius + 6
            x1 = cx + r1 * math.sin(rad)
            y1 = cy - r1 * math.cos(rad)
            x2 = cx + r2 * math.sin(rad)
            y2 = cy - r2 * math.cos(rad)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # RENDER EACH DETECTED THREAT
        for threat in self.active_threats:
            t_angle = threat["angle"] # -90 to +90 or 180
            t_kind = threat["kind"]
            t_opac = threat["opacity"] * opacity
            t_dist = threat.get("distance", "medium")
            t_pwr = threat.get("power", 0.5)

            is_rear = abs(t_angle) > 115.0

            # Color scheme
            if is_rear:
                base_col = QColor(255, 45, 45) # Bright Red for rear threat
                icon_str = "⚠️"
                dir_txt = "⬇️ HINTEN"
            elif t_kind == "footstep":
                base_col = c_foot
                icon_str = "👣"
                dir_txt = "⬅️ LINKS" if t_angle < -20.0 else ("RECHTS ➡️" if t_angle > 20.0 else "⬆️ VORNE")
            elif t_kind == "gunshot":
                base_col = c_gun
                icon_str = "💥"
                dir_txt = "⬅️ LINKS" if t_angle < -20.0 else ("RECHTS ➡️" if t_angle > 20.0 else "⬆️ VORNE")
            else:
                base_col = QColor(255, 220, 50)
                icon_str = "⚠️"
                dir_txt = "⬅️ LINKS" if t_angle < -20.0 else ("RECHTS ➡️" if t_angle > 20.0 else "⬆️ VORNE")

            # 1. High-Contrast Directional Arc Wedge
            center_qt_deg = 90.0 - t_angle
            span_deg = 42.0
            start_qt_deg = center_qt_deg - (span_deg / 2.0)

            arc_th = 6.5 + (t_pwr * 11.0)
            arc_r = base_radius + (t_pwr * 12.0)
            rect_arc = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)

            alpha_arc = int(min(255, (120 + t_opac * 135) * t_opac))
            arc_col = QColor(base_col.red(), base_col.green(), base_col.blue(), alpha_arc)

            pen_wedge = QPen(arc_col, arc_th, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_wedge)
            painter.drawArc(rect_arc, int(start_qt_deg * 16), int(span_deg * 16))

            # Outer glow
            if t_opac > 0.35:
                glow_col = QColor(base_col.red(), base_col.green(), base_col.blue(), int(alpha_arc * 0.4))
                painter.setPen(QPen(glow_col, arc_th + 14.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawArc(rect_arc, int((start_qt_deg + 3) * 16), int((span_deg - 6) * 16))

            # 2. Outer Icon & Direction Text
            rad = math.radians(t_angle)
            icon_r = base_radius + 24
            ix = cx + icon_r * math.sin(rad)
            iy = cy - icon_r * math.cos(rad)

            # Draw Emoji Icon
            font_emoji = QFont("Segoe UI Emoji", 11)
            painter.setFont(font_emoji)
            painter.setPen(QColor(255, 255, 255, int(255 * t_opac)))
            painter.drawText(QRectF(ix - 14, iy - 14, 28, 28), Qt.AlignmentFlag.AlignCenter, icon_str)

            # Draw Direction Badge Text
            font_dir = QFont("Consolas", 8, QFont.Weight.Bold)
            painter.setFont(font_dir)
            painter.setPen(QColor(base_col.red(), base_col.green(), base_col.blue(), int(255 * t_opac)))
            
            tag_r = base_radius + 42
            tx = cx + tag_r * math.sin(rad)
            ty = cy - tag_r * math.cos(rad)
            painter.drawText(QRectF(tx - 36, ty - 9, 72, 18), Qt.AlignmentFlag.AlignCenter, dir_txt)

            # Connecting pointer line to crosshair
            beam_col = QColor(base_col.red(), base_col.green(), base_col.blue(), int(110 * t_opac))
            painter.setPen(QPen(beam_col, 1.4, Qt.PenStyle.DashDotLine))
            inner_px = cx + (base_radius - 8) * math.sin(rad)
            inner_py = cy - (base_radius - 8) * math.cos(rad)
            painter.drawLine(QPointF(cx, cy), QPointF(inner_px, inner_py))

    def draw_edge_glow(self, painter, w, h, opacity):
        has_left_threat = False
        has_right_threat = False
        left_power = 0.0
        right_power = 0.0
        left_kind = "footstep"
        right_kind = "footstep"

        for t in self.active_threats:
            if t["angle"] < -18.0:
                has_left_threat = True
                if t["power"] * t["opacity"] > left_power:
                    left_power = t["power"] * t["opacity"]
                    left_kind = t["kind"]
            elif t["angle"] > 18.0:
                has_right_threat = True
                if t["power"] * t["opacity"] > right_power:
                    right_power = t["power"] * t["opacity"]
                    right_kind = t["kind"]

        c_foot = QColor(self.config.get("footstep_color", "#FF8800"))
        c_gun = QColor(self.config.get("gunshot_color", "#00E5FF"))

        # LEFT SCREEN GLOW
        if has_left_threat or self.cur_level_l > 0.05:
            val = max(left_power, self.cur_level_l)
            alpha = int(min(220, (60 + val * 165) * opacity))
            color = c_foot if left_kind == "footstep" else c_gun
            glow_w = 45 + int(val * 110)

            grad_l = QLinearGradient(0, h / 2.0, glow_w, h / 2.0)
            grad_l.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
            grad_l.setColorAt(0.2, QColor(color.red(), color.green(), color.blue(), int(alpha * 0.4)))
            grad_l.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad_l))
            painter.drawRect(0, 0, glow_w, h)

            bracket_h = 160 + int(val * 240)
            by = (h - bracket_h) / 2.0
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), min(255, alpha + 35)), 3.0))
            painter.drawLine(QPointF(6, by), QPointF(6, by + bracket_h))

        # RIGHT SCREEN GLOW
        if has_right_threat or self.cur_level_r > 0.05:
            val = max(right_power, self.cur_level_r)
            alpha = int(min(220, (60 + val * 165) * opacity))
            color = c_foot if right_kind == "footstep" else c_gun
            glow_w = 45 + int(val * 110)

            grad_r = QLinearGradient(w, h / 2.0, w - glow_w, h / 2.0)
            grad_r.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
            grad_r.setColorAt(0.2, QColor(color.red(), color.green(), color.blue(), int(alpha * 0.4)))
            grad_r.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad_r))
            painter.drawRect(w - glow_w, 0, glow_w, h)

            bracket_h = 160 + int(val * 240)
            by = (h - bracket_h) / 2.0
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), min(255, alpha + 35)), 3.0))
            painter.drawLine(QPointF(w - 6, by), QPointF(w - 6, by + bracket_h))

    def draw_tactical_bar(self, painter, cx, cy, opacity):
        bar_w = 380
        bar_h = 14
        half_w = bar_w / 2.0

        bg_rect = QRectF(cx - half_w, cy - bar_h / 2.0, bar_w, bar_h)
        painter.setPen(QPen(QColor(255, 255, 255, int(40 * opacity)), 1.0))
        painter.setBrush(QBrush(QColor(10, 15, 20, int(150 * opacity))))
        painter.drawRoundedRect(bg_rect, 4.0, 4.0)

        painter.setPen(QPen(QColor(255, 255, 255, int(120 * opacity)), 1.5))
        painter.drawLine(QPointF(cx, cy - bar_h / 2.0), QPointF(cx, cy + bar_h / 2.0))

        c_foot = QColor(self.config.get("footstep_color", "#FF8800"))
        c_gun = QColor(self.config.get("gunshot_color", "#00E5FF"))

        l_len = half_w * min(1.0, self.cur_level_l)
        if l_len > 2:
            col_l = c_foot
            col_l.setAlpha(int(min(255, 200 * opacity)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col_l))
            painter.drawRect(QRectF(cx - l_len, cy - (bar_h - 4) / 2.0, l_len, bar_h - 4))

        r_len = half_w * min(1.0, self.cur_level_r)
        if r_len > 2:
            col_r = c_gun
            col_r.setAlpha(int(min(255, 200 * opacity)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col_r))
            painter.drawRect(QRectF(cx, cy - (bar_h - 4) / 2.0, r_len, bar_h - 4))
