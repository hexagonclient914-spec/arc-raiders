"""
ARC Raiders YOLO Tactical Vision HUD - Overlay Window
Ultra-smooth, click-through transparent HUD rendering tactical bounding boxes,
target badges, snaplines, and lock-on indicators.
"""

import math
import ctypes
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QFont, QPolygonF
)


# ARC Raiders class tactical color mapping
ARC_CLASS_COLORS = {
    # Flying Drones & Airborne Probes (Electric Aqua / Cyan)
    "SNITCH": "#00E5FF",
    "HORNET": "#00D4FF",
    "WASP": "#00FFFF",
    "PROBE": "#38E1FF",

    # Heavy Combat Machines & Artillery (Tactical Amber / High Alert Orange)
    "BASTION": "#FF7700",
    "BOMBARDIER": "#FF5500",
    "ROCKETEER": "#FF4400",
    "TURRET": "#FF8800",

    # Fast Ground Threats & Jumpers (Neon Violet / Hot Pink)
    "LEAPER": "#E040FB",
    "POP": "#FF0077",
    "FIREBALL": "#FF1744",

    # Human Combatants (Raiders) (Cyber Crimson)
    "RAIDER": "#FF2A55",
    "RAIDER-DOWN": "#8899A6",
    "ENEMY": "#FF2A55",

    # Counter-Strike & Tactical Shooter Classes
    "T_HEAD": "#FFE600",           # Terrorist Head (Neon Gold)
    "CT_HEAD": "#FFE600",          # Counter-Terrorist Head (Neon Gold)
    "T_BODY": "#FF7700",           # Terrorist Torso (Orange)
    "CT_BODY": "#00D4FF",          # Counter-Terrorist Torso (Cyan)
    "T": "#FF7700",                # Terrorist
    "CT": "#00D4FF",               # Counter-Terrorist

    # Valorant / Tactical Shooter Classes
    "HEAD": "#FFE600",           # Critical Headshot Zone (Neon Gold)
    "PLAYER": "#FF2A55",         # Enemy Body (Neon Crimson)
    "BOT": "#FF9900",            # Practice Bot (Amber)
    "OUTLINE": "#00E5FF",        # Enemy Outline (Aqua Cyan)
    "WEAPON": "#90A4AE",         # Dropped Weapon
    "DEAD_BODY": "#455A64",      # Downed/Dead
    "SMOKE": "#B388FF",          # Smoke Screen (Lavender)
    "FIRE": "#FF3D00",           # Incendiary/Molly
    "HIDEOUT_TARGET_HUMAN": "#FF5252",
    "HIDEOUT_TARGET_BALLS": "#FFD740",
    "THIRD_PERSION": "#E040FB",
}


class YOLOOverlayWindow(QWidget):
    def __init__(self, yolo_engine, config):
        super().__init__()
        self.engine = yolo_engine
        self.config = config

        # Configure transparent, topmost, click-through window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.latest_state = {
            "fps": 0.0,
            "latency_ms": 0.0,
            "targets": [],
            "scan_region": {"left": 0, "top": 0, "width": 1920, "height": 1080},
            "model_name": "",
            "is_ready": False,
        }

        # Ultra-smooth 144Hz animation timer (~7ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(7)

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_clickthrough()
        self.apply_streamer_mode()

    def apply_streamer_mode(self):
        """
        Bypass OBS, Discord Screenshare, Medal, Shadowplay, and Windows Capture.
        Uses native Windows DWM SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE).
        """
        try:
            hwnd = int(self.winId())
            enable_streamer = bool(self.config.get("streamer_mode", True))
            WDA_EXCLUDEFROMCAPTURE = 0x00000011
            WDA_NONE = 0x00000000
            affinity = WDA_EXCLUDEFROMCAPTURE if enable_streamer else WDA_NONE
            res = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, affinity)
            if not res and enable_streamer:
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 1)
        except Exception as e:
            print(f"[YOLOOverlay] Error applying streamer mode: {e}")

    def apply_clickthrough(self):
        """Ensure clicks pass completely through to ARC Raiders without interference."""
        try:
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            WS_EX_NOACTIVATE = 0x08000000

            styles = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd,
                GWL_EXSTYLE,
                styles | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
            )
        except Exception as e:
            print(f"[YOLOOverlay] Error applying click-through: {e}")

    def update_frame(self):
        if bool(self.config.get("headless_mode", False)) or not self.isVisible():
            return
        self.latest_state = self.engine.get_state()
        self.update()

    def paintEvent(self, event):
        try:
            # Headless / No-Overlay Mode: render nothing at all on screen
            if bool(self.config.get("headless_mode", False)):
                return

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            # Respect global overlay opacity
            opacity = float(self.config.get("overlay_opacity", 0.95))
            painter.setOpacity(max(0.1, min(1.0, opacity)))

            w = self.width()
            h = self.height()
            cx = w / 2.0
            cy = h / 2.0

            targets = self.latest_state.get("targets", [])
            scan_reg = self.latest_state.get("scan_region", {})
            fps = self.latest_state.get("fps", 0.0)
            latency = self.latest_state.get("latency_ms", 0.0)
            ft_hist = self.latest_state.get("frametime_history", [])
            makcu_st = self.latest_state.get("makcu", {})

            # Check if crosshair is on any active target or locked onto head (Anatomical Ellipse)
            is_on_target = False
            is_head_locked = False
            if self.config.get("on_target_crosshair", True):
                for t in targets:
                    if t.get("x1", 0) <= cx <= t.get("x2", 0) and t.get("y1", 0) <= cy <= t.get("y2", 0):
                        is_on_target = True
                        head_x = t.get("head_cx", cx)
                        head_y = t.get("head_cy", cy)
                        hw_rad = max(4.0, t.get("head_w", 12.0) / 2.0)
                        hh_rad = max(4.0, t.get("head_h", 14.0) / 2.0)
                        norm_sq = ((cx - head_x) / hw_rad) ** 2 + ((cy - head_y) / hh_rad) ** 2
                        if norm_sq <= 1.25:
                            is_head_locked = True
                        break

            # 1. Scan Zone Boundary
            if self.config.get("show_scan_zone", True) and scan_reg:
                self.draw_scan_zone(painter, scan_reg)

            # 1.5. MAKCU Aim FOV Circle
            if self.config.get("makcu_enabled", True) and self.config.get("makcu_show_fov", True):
                self.draw_makcu_fov(painter, cx, cy, makcu_st)

            # 2. Draw Crosshair (Dynamic On-Target state shift & Headshot Lock)
            if self.config.get("show_crosshair", True):
                self.draw_crosshair(painter, cx, cy, is_on_target, is_head_locked)

            # 3. Draw Snaplines (Tracers)
            if self.config.get("show_snaplines", True):
                self.draw_snaplines(painter, targets, cx, cy, h)

            # 4. Draw Detection Boxes & Badges
            for target in targets:
                self.draw_target_box(painter, target)

            # 5. Draw Tactical HUD Diagnostics
            if self.config.get("show_hud_stats", True):
                self.draw_hud_stats(painter, fps, latency, len(targets), makcu_st, ft_hist)
        except Exception:
            pass

    def draw_scan_zone(self, painter, reg):
        """Draw a tactical scanning perimeter with subtle corner ticks."""
        x = reg.get("left", 0)
        y = reg.get("top", 0)
        rw = reg.get("width", 640)
        rh = reg.get("height", 640)

        color_hex = self.config.get("scan_zone_color", "#00FFCC")
        c = QColor(color_hex)
        c.setAlpha(35)

        pen = QPen(c, 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(x, y, rw, rh))

        # Corner accents for scan zone
        corner_len = 18
        accent_color = QColor(color_hex)
        accent_color.setAlpha(135)
        accent_pen = QPen(accent_color, 2)
        painter.setPen(accent_pen)

        # Top-Left
        painter.drawLine(int(x), int(y), int(x + corner_len), int(y))
        painter.drawLine(int(x), int(y), int(x), int(y + corner_len))
        # Top-Right
        painter.drawLine(int(x + rw), int(y), int(x + rw - corner_len), int(y))
        painter.drawLine(int(x + rw), int(y), int(x + rw), int(y + corner_len))
        # Bottom-Left
        painter.drawLine(int(x), int(y + rh), int(x + corner_len), int(y + rh))
        painter.drawLine(int(x), int(y + rh), int(x), int(y + rh - corner_len))
        # Bottom-Right
        painter.drawLine(int(x + rw), int(y + rh), int(x + rw - corner_len), int(y + rh))
        painter.drawLine(int(x + rw), int(y + rh), int(x + rw), int(y + rh - corner_len))

    def draw_crosshair(self, painter, cx, cy, is_on_target=False, is_head_locked=False):
        """Tactical center crosshair dot with dynamic on-target & headshot lock state shift."""
        if is_head_locked:
            color_hex = "#FF0055"  # Crimson / Neon Rose for headshot lock
            dot_size = self.config.get("crosshair_size", 4) + 3
        elif is_on_target:
            color_hex = self.config.get("on_target_color", "#FFE600")
            dot_size = self.config.get("crosshair_size", 4) + 2
        else:
            color_hex = self.config.get("crosshair_color", "#00FFCC")
            dot_size = self.config.get("crosshair_size", 4)

        c = QColor(color_hex)
        glow_alpha = 135 if is_head_locked else (105 if is_on_target else 65)

        # Radial glow around center
        rad_grad = QRadialGradient(QPointF(cx, cy), dot_size * 2.8)
        rad_grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), glow_alpha))
        rad_grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(rad_grad))
        painter.drawEllipse(QPointF(cx, cy), dot_size * 2.8, dot_size * 2.8)

        # Crisp center dot
        painter.setBrush(QBrush(c))
        painter.drawEllipse(QPointF(cx, cy), dot_size / 2.0, dot_size / 2.0)

        # Active On-Target Lock Reticle
        if is_on_target or is_head_locked:
            reticle_pen = QPen(c, 2.0 if is_head_locked else 1.5)
            painter.setPen(reticle_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = dot_size * (3.5 if is_head_locked else 3.2)
            painter.drawEllipse(QPointF(cx, cy), r, r)
            # 4 lock ticks
            tick = 5 if is_head_locked else 4
            painter.drawLine(QPointF(cx, cy - r - tick), QPointF(cx, cy - r + 1))
            painter.drawLine(QPointF(cx, cy + r - 1), QPointF(cx, cy + r + tick))
            painter.drawLine(QPointF(cx - r - tick, cy), QPointF(cx - r + 1, cy))
            painter.drawLine(QPointF(cx + r - 1, cy), QPointF(cx + r + tick, cy))

            # Status badge
            font = QFont("Consolas", 8, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(c)
            badge_text = "[CRITICAL HEAD LOCK]" if is_head_locked else "[TARGET ACQUIRED]"
            painter.drawText(QRectF(cx - 80, cy + r + 4, 160, 16), Qt.AlignmentFlag.AlignCenter, badge_text)

    def draw_snaplines(self, painter, targets, cx, cy, screen_h):
        """Draw laser snapline to targets with gradient fade."""
        origin_mode = self.config.get("snapline_origin", "bottom")
        ox = cx
        oy = screen_h if origin_mode == "bottom" else cy

        closest_color_hex = self.config.get("closest_color", "#00FFCC")
        enemy_color_hex = self.config.get("enemy_color", "#FF3355")

        for t in targets:
            is_closest = t.get("is_closest", False)
            tx = t["cx"]
            ty = t["y2"]  # Bottom of bounding box

            if is_closest:
                line_color = QColor(closest_color_hex)
                grad = QLinearGradient(QPointF(ox, oy), QPointF(tx, ty))
                c_start = QColor(line_color.red(), line_color.green(), line_color.blue(), 60)
                c_end = QColor(line_color.red(), line_color.green(), line_color.blue(), 220)
                grad.setColorAt(0.0, c_start)
                grad.setColorAt(1.0, c_end)
                pen = QPen(QBrush(grad), 2.0, Qt.PenStyle.SolidLine)
            else:
                line_color = QColor(enemy_color_hex)
                line_color.setAlpha(65)
                pen = QPen(line_color, 1.0, Qt.PenStyle.DashLine)

            painter.setPen(pen)
            painter.drawLine(QPointF(ox, oy), QPointF(tx, ty))

    def draw_target_box(self, painter, target):
        """Draw sci-fi tactical bounding box and informative badge."""
        x1 = target["x1"]
        y1 = target["y1"]
        x2 = target["x2"]
        y2 = target["y2"]
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        is_closest = target.get("is_closest", False)
        is_ghost = target.get("is_ghost", False)

        # Color & Style selection
        if is_ghost:
            alpha = int(220 * target.get("ghost_alpha", 0.6))
            base_color = QColor(179, 136, 255, alpha)  # Ghost Neon Lilac
            box_style = "corners"
            pen_style = Qt.PenStyle.DashLine
        else:
            cls_key = target.get("class_name", "").upper()
            if is_closest:
                box_hex = self.config.get("closest_color", "#00FFCC")
            elif cls_key in ARC_CLASS_COLORS:
                box_hex = ARC_CLASS_COLORS[cls_key]
            else:
                box_hex = self.config.get("enemy_color", "#FF3355")
            base_color = QColor(box_hex)
            box_style = self.config.get("box_style", "corners")
            pen_style = Qt.PenStyle.SolidLine

        thickness = int(self.config.get("box_thickness", 2))
        show_boxes = self.config.get("show_boxes", True)

        if show_boxes:
            # 1. Subtle gradient fill inside target area
            fill_alpha_top = 12 if is_ghost else (18 if not is_closest else 32)
            fill_alpha_bot = 25 if is_ghost else (34 if not is_closest else 55)
            grad_fill = QLinearGradient(QPointF(x1, y1), QPointF(x1, y2))
            grad_fill.setColorAt(0.0, QColor(base_color.red(), base_color.green(), base_color.blue(), fill_alpha_top))
            grad_fill.setColorAt(1.0, QColor(base_color.red(), base_color.green(), base_color.blue(), fill_alpha_bot))
            painter.setBrush(QBrush(grad_fill))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(x1, y1, w, h))

            # 2. Draw Box Outline, Sci-Fi Corners, or Neon Glow
            if box_style == "corners":
                corner_len = min(self.config.get("corner_length", 14), w // 3, h // 3)
                # Outer soft glow for closest target
                if is_closest and not is_ghost:
                    glow_c = QColor(base_color.red(), base_color.green(), base_color.blue(), 60)
                    painter.setPen(QPen(glow_c, thickness + 3, Qt.PenStyle.SolidLine))
                    painter.drawLine(QPointF(x1, y1), QPointF(x1 + corner_len, y1))
                    painter.drawLine(QPointF(x1, y1), QPointF(x1, y1 + corner_len))
                    painter.drawLine(QPointF(x2, y1), QPointF(x2 - corner_len, y1))
                    painter.drawLine(QPointF(x2, y1), QPointF(x2, y1 + corner_len))
                    painter.drawLine(QPointF(x1, y2), QPointF(x1 + corner_len, y2))
                    painter.drawLine(QPointF(x1, y2), QPointF(x1, y2 - corner_len))
                    painter.drawLine(QPointF(x2, y2), QPointF(x2 - corner_len, y2))
                    painter.drawLine(QPointF(x2, y2), QPointF(x2, y2 - corner_len))

                pen = QPen(base_color, thickness, pen_style)
                painter.setPen(pen)

                # Top-Left
                painter.drawLine(QPointF(x1, y1), QPointF(x1 + corner_len, y1))
                painter.drawLine(QPointF(x1, y1), QPointF(x1, y1 + corner_len))
                # Top-Right
                painter.drawLine(QPointF(x2, y1), QPointF(x2 - corner_len, y1))
                painter.drawLine(QPointF(x2, y1), QPointF(x2, y1 + corner_len))
                # Bottom-Left
                painter.drawLine(QPointF(x1, y2), QPointF(x1 + corner_len, y2))
                painter.drawLine(QPointF(x1, y2), QPointF(x1, y2 - corner_len))
                # Bottom-Right
                painter.drawLine(QPointF(x2, y2), QPointF(x2 - corner_len, y2))
                painter.drawLine(QPointF(x2, y2), QPointF(x2, y2 - corner_len))

                # Center pip on target
                if is_closest and not is_ghost:
                    pip_pen = QPen(base_color, 2)
                    painter.setPen(pip_pen)
                    painter.drawEllipse(QPointF(target["cx"], target["cy"]), 3, 3)

            elif box_style == "glow":
                # Neon Outer Halo + Crisp Inner Border
                glow_c = QColor(base_color.red(), base_color.green(), base_color.blue(), 75)
                painter.setPen(QPen(glow_c, thickness + 4, Qt.PenStyle.SolidLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(QRectF(x1, y1, w, h), 3, 3)

                pen = QPen(base_color, thickness, pen_style)
                painter.setPen(pen)
                painter.drawRoundedRect(QRectF(x1, y1, w, h), 3, 3)
            else:
                # Full Box
                pen = QPen(base_color, thickness, pen_style)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(x1, y1, w, h))

            # 3. Draw Target Badge & Confidence Bar
            show_labels = self.config.get("show_labels", True)
            if show_labels:
                cls_name = target.get("class_name", "TARGET")
                conf_float = float(target.get("conf", 0.0))
                conf = int(conf_float * 100)
                dist_px = int(target.get("dist", 0))

                if is_ghost:
                    dt_loss = target.get("dt_loss", 0.0)
                    badge_text = f"👻 GHOST {cls_name} [{dt_loss:.1f}s]"
                else:
                    badge_text = cls_name
                    if self.config.get("show_confidence", True):
                        badge_text += f" {conf}%"
                    if self.config.get("show_distance", True):
                        badge_text += f" · {dist_px}px"

                font = QFont("Consolas", 9, QFont.Weight.Bold)
                font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
                painter.setFont(font)

                metrics = painter.fontMetrics()
                tw = metrics.horizontalAdvance(badge_text) + 14
                th = metrics.height() + 6

                badge_x = x1
                badge_y = y1 - th - 4
                if badge_y < 10:
                    badge_y = y1 + 4

                # Badge background with left accent bar
                bg_brush = QBrush(QColor(10, 13, 20, 225))
                badge_border_pen = QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 160), 1)
                painter.setBrush(bg_brush)
                painter.setPen(badge_border_pen)
                painter.drawRoundedRect(QRectF(badge_x, badge_y, tw, th), 3, 3)

                # Accent stripe on left of badge
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(base_color))
                painter.drawRoundedRect(QRectF(badge_x, badge_y, 3, th), 1.5, 1.5)

                # Badge text
                painter.setPen(base_color if (is_closest or is_ghost) else QColor(240, 244, 248))
                painter.drawText(
                    QRectF(badge_x + 3, badge_y, tw - 3, th),
                    Qt.AlignmentFlag.AlignCenter,
                    badge_text
                )

            # 4. Velocity Vector on Ghost Target (shows movement behind cover)
            if is_ghost:
                vx = target.get("vx", 0.0)
                vy = target.get("vy", 0.0)
                speed = math.hypot(vx, vy)
                if speed > 20:
                    norm_vx = (vx / speed) * min(35, speed * 0.05)
                    norm_vy = (vy / speed) * min(35, speed * 0.05)
                    arrow_pen = QPen(base_color, 1.5, Qt.PenStyle.DashLine)
                    painter.setPen(arrow_pen)
                    tcx, tcy = target["cx"], target["cy"]
                    painter.drawLine(QPointF(tcx, tcy), QPointF(tcx + norm_vx, tcy + norm_vy))

        # 5. Lock indicator on closest threat
        if is_closest and not is_ghost and self.config.get("show_closest_indicator", True):
            reticle_pen = QPen(base_color, 1.8)
            painter.setPen(reticle_pen)
            pad = 6
            poly_top = QPolygonF([
                QPointF(target["cx"] - 6, y1 - pad - 6),
                QPointF(target["cx"], y1 - pad),
                QPointF(target["cx"] + 6, y1 - pad - 6)
            ])
            painter.drawPolyline(poly_top)

        # 6. Precision Headshot Marker (Golden Diamond Reticle with Anatomical Sizing)
        if self.config.get("show_head_marker", True) and not is_ghost:
            head_x = target.get("head_cx", (x1 + x2) / 2.0)
            head_y = target.get("head_cy", y1 + h * 0.16)
            hw = target.get("head_w", max(8.0, w * 0.25))
            hh = target.get("head_h", max(10.0, h * 0.18))
            hw_rad = max(4.0, hw / 2.0)
            hh_rad = max(4.0, hh / 2.0)

            screen_cx = self.width() / 2.0
            screen_cy = self.height() / 2.0
            norm_dist_sq = ((screen_cx - head_x) / hw_rad) ** 2 + ((screen_cy - head_y) / hh_rad) ** 2
            is_head_locked = (norm_dist_sq <= 1.25)

            if is_head_locked:
                head_hex = "#FF0055"
                rx = hw_rad * 1.15
                ry = hh_rad * 1.15
                line_w = 2.0
            else:
                head_hex = self.config.get("head_marker_color", "#FFE600")
                rx = hw_rad
                ry = hh_rad
                line_w = 1.5

            head_c = QColor(head_hex)
            fill_alpha = 70 if is_head_locked else 28
            painter.setBrush(QBrush(QColor(head_c.red(), head_c.green(), head_c.blue(), fill_alpha)))
            painter.setPen(QPen(head_c, line_w))

            # Diamond Shape accurately scaled to head geometry
            poly_diamond = QPolygonF([
                QPointF(head_x, head_y - ry),
                QPointF(head_x + rx, head_y),
                QPointF(head_x, head_y + ry),
                QPointF(head_x - rx, head_y)
            ])
            painter.drawPolygon(poly_diamond)

            # Precision Center Pip
            painter.setBrush(QBrush(head_c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(head_x, head_y), 1.8, 1.8)

            # Stance Indicator badge next to diamond
            stance = target.get("stance", "STAND")
            if stance == "CROUCH":
                st_font = QFont("Consolas", 7, QFont.Weight.Bold)
                painter.setFont(st_font)
                painter.setPen(QColor(255, 170, 0, 195))
                painter.drawText(QRectF(head_x + rx + 3, head_y - 6, 45, 12), Qt.AlignmentFlag.AlignLeft, "CROUCH")

            # Cross-ticks if locked
            if is_head_locked:
                painter.setPen(QPen(head_c, 1.5))
                tick = 4.0
                painter.drawLine(QPointF(head_x, head_y - ry - tick), QPointF(head_x, head_y - ry))
                painter.drawLine(QPointF(head_x, head_y + ry), QPointF(head_x, head_y + ry + tick))
                painter.drawLine(QPointF(head_x - rx - tick, head_y), QPointF(head_x - rx, head_y))
                painter.drawLine(QPointF(head_x + rx, head_y), QPointF(head_x + rx + tick, head_y))

    def draw_makcu_fov(self, painter, cx, cy, makcu_st):
        """Draw circular tactical FOV ring for MAKCU hardware aim assist."""
        radius = float(self.config.get("makcu_fov", 160))
        is_aiming = makcu_st.get("is_aiming", False)
        has_lock = makcu_st.get("has_lock", False)

        if is_aiming and has_lock:
            # Active lock color: Neon Gold / Amber with pulse
            ring_color = QColor(255, 230, 0, 185)
            pen = QPen(ring_color, 1.6, Qt.PenStyle.SolidLine)
        else:
            # Passive FOV boundary: Cyber Cyan with subtle dash
            ring_color = QColor(0, 255, 204, 55)
            pen = QPen(ring_color, 1.0, Qt.PenStyle.DashLine)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Draw subtle crosshair tick marks on FOV boundary
        tick_len = 6
        tick_pen = QPen(ring_color, 1.2)
        painter.setPen(tick_pen)
        painter.drawLine(QPointF(cx - radius, cy), QPointF(cx - radius + tick_len, cy))
        painter.drawLine(QPointF(cx + radius, cy), QPointF(cx + radius - tick_len, cy))
        painter.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy - radius + tick_len))
        painter.drawLine(QPointF(cx, cy + radius), QPointF(cx, cy + radius - tick_len))

    def draw_hud_stats(self, painter, fps, latency, target_count, makcu_st=None, ft_hist=None):
        """Top-left cyber-pill tactical HUD diagnostic bar with Live Frametime Sparkline."""
        font = QFont("Consolas", 9, QFont.Weight.Bold)
        painter.setFont(font)

        makcu_st = makcu_st or {}
        is_conn = makcu_st.get("is_connected", False)
        is_aim = makcu_st.get("is_aiming", False)
        port = makcu_st.get("port", "OFF")

        is_mouse_locked = makcu_st.get("is_mouse_locked", False)
        if is_mouse_locked:
            makcu_label = "MAKCU: [STEADY LOCK] 🔒"
        elif is_aim:
            makcu_label = "MAKCU: [AIMING] ⚡"
        elif is_conn:
            makcu_label = f"MAKCU: ON ({port})"
        else:
            makcu_label = "MAKCU: OFF"

        prof = self.config.get("active_game_profile", "custom").upper()
        sys_on = bool(self.config.get("enabled", True))
        hk_c = str(self.config.get("hotkey_toggle_engine", "c")).upper()
        if not sys_on:
            status_text = f"TACTICAL VISION [{prof}] // 🔴 SYSTEM PAUSIERT (Drücke [{hk_c}] zum Aktivieren)"
        else:
            status_text = f"TACTICAL VISION [{prof}] // {fps:.0f} FPS · {latency:.1f}ms · THREATS: {target_count} · {makcu_label} · [{hk_c}] ON"

        metrics = painter.fontMetrics()
        spark_w = 68 if (ft_hist and len(ft_hist) > 2) else 0
        tw = metrics.horizontalAdvance(status_text) + 32 + (spark_w + 12 if spark_w else 0)
        th = metrics.height() + 12

        rx, ry = 20, 20
        # Dark cyber glass background
        painter.setBrush(QBrush(QColor(8, 12, 20, 220)))
        border_pen = QPen(QColor(0, 240, 255, 140), 1)
        painter.setPen(border_pen)
        painter.drawRoundedRect(QRectF(rx, ry, tw, th), 5, 5)

        # Left neon accent bar
        if not sys_on:
            dot_color = QColor(255, 42, 85)
        elif is_aim:
            dot_color = QColor(255, 230, 0)
        elif target_count == 0:
            dot_color = QColor(0, 255, 136)
        else:
            dot_color = QColor(255, 42, 85)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(dot_color))
        painter.drawRoundedRect(QRectF(rx, ry, 4, th), 2, 2)
        painter.drawEllipse(QPointF(rx + 14, ry + th / 2.0), 3.5, 3.5)

        # Status text
        painter.setPen(QColor(235, 242, 250))
        painter.drawText(QRectF(rx + 25, ry, tw - 25 - spark_w, th), Qt.AlignmentFlag.AlignVCenter, status_text)

        # Live Frametime Sparkline inside Top-Left Pill
        if spark_w > 0:
            sx = rx + tw - spark_w - 10
            sy = ry + 5
            sh = th - 10
            painter.setBrush(QBrush(QColor(14, 20, 32, 200)))
            painter.setPen(QPen(QColor(30, 45, 68, 180), 1))
            painter.drawRoundedRect(QRectF(sx, sy, spark_w, sh), 3, 3)

            pts = ft_hist[-30:]
            max_v = max(20.0, max(pts) * 1.1)
            min_v = 0.0
            step_x = (spark_w - 4) / max(1, len(pts) - 1)
            poly = QPolygonF()
            for i, val in enumerate(pts):
                px = sx + 2 + i * step_x
                norm = min(1.0, max(0.0, (val - min_v) / (max_v - min_v)))
                py = sy + sh - 2 - norm * (sh - 4)
                poly.append(QPointF(px, py))

            painter.setPen(QPen(QColor(0, 240, 255, 230), 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(poly)
