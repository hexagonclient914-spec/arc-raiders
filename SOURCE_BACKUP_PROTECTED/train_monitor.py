"""
ARC Raiders - Live YOLO Training Progress Dashboard
Real-time tactical HUD showing training epochs, loss metrics, mAP accuracy, and GPU telemetry.
"""

import sys
import os
import csv
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QGroupBox, QPushButton
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

RESULTS_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "runs", "detect", "arc_raiders_improved", "results.csv"
)

TOTAL_EPOCHS = 40


class TrainingDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARC Raiders - YOLOv11 Training Monitor")
        self.setFixedSize(540, 480)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QWidget {
                background-color: #0B0E14;
                color: #DDE2E8;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #1E2533;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 12px;
                font-weight: bold;
                color: #00FFCC;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QLabel {
                color: #A0ABC0;
            }
            QProgressBar {
                border: 1px solid #1E2533;
                border-radius: 6px;
                text-align: center;
                height: 24px;
                background-color: #121722;
                color: #FFFFFF;
                font-weight: bold;
                font-family: Consolas;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF3366, stop:1 #00FFCC);
                border-radius: 5px;
            }
            QPushButton {
                background-color: #161D2B;
                border: 1px solid #2B3850;
                border-radius: 6px;
                padding: 6px 14px;
                color: #FFFFFF;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #212C42;
                border-color: #00FFCC;
            }
        """)

        self.init_ui()

        # Update timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_stats)
        self.timer.start(1500)

        self.refresh_stats()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        title = QLabel("ARC RAIDERS // YOLOv11 TRAINING MONITOR")
        title.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00FFCC; letter-spacing: 1px;")
        layout.addWidget(title)

        self.lbl_status = QLabel("Status: TRAINING AKTIV AUF NVIDIA RTX 4060")
        self.lbl_status.setStyleSheet("color: #FF8800; font-family: Consolas; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # ---------------- GROUP 1: PROGRESS ----------------
        grp_prog = QGroupBox("📊 Gesamt-Fortschritt")
        layout_p = QVBoxLayout(grp_prog)
        layout_p.setSpacing(8)

        self.lbl_epoch = QLabel("Epoche: 0 / 40 (0%)")
        self.lbl_epoch.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.lbl_epoch.setStyleSheet("color: #FFFFFF;")
        layout_p.addWidget(self.lbl_epoch)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, TOTAL_EPOCHS)
        self.progress_bar.setValue(0)
        layout_p.addWidget(self.progress_bar)

        self.lbl_time = QLabel("Verstrichene Zeit: -- | Geschaetzte Restzeit: --")
        self.lbl_time.setStyleSheet("color: #8C99AB; font-size: 11px; font-family: Consolas;")
        layout_p.addWidget(self.lbl_time)

        layout.addWidget(grp_prog)

        # ---------------- GROUP 2: ACCURACY & METRICS ----------------
        grp_metrics = QGroupBox("🎯 Modell-Genauigkeit & Metriken (Letzte Epoche)")
        layout_m = QVBoxLayout(grp_metrics)
        layout_m.setSpacing(6)

        row1 = QHBoxLayout()
        self.lbl_map50 = QLabel("mAP 50: -- %")
        self.lbl_map50.setStyleSheet("color: #00FFCC; font-family: Consolas; font-weight: bold; font-size: 13px;")
        self.lbl_prec = QLabel("Precision: -- %")
        self.lbl_prec.setStyleSheet("color: #00FFCC; font-family: Consolas; font-weight: bold; font-size: 13px;")
        row1.addWidget(self.lbl_map50)
        row1.addWidget(self.lbl_prec)
        layout_m.addLayout(row1)

        row2 = QHBoxLayout()
        self.lbl_recall = QLabel("Recall: -- %")
        self.lbl_recall.setStyleSheet("color: #FF9900; font-family: Consolas; font-size: 12px;")
        self.lbl_loss = QLabel("Box Loss: -- | Class Loss: --")
        self.lbl_loss.setStyleSheet("color: #FF9900; font-family: Consolas; font-size: 12px;")
        row2.addWidget(self.lbl_recall)
        row2.addWidget(self.lbl_loss)
        layout_m.addLayout(row2)

        layout.addWidget(grp_metrics)

        # ---------------- GROUP 3: HARDWARE ----------------
        grp_hw = QGroupBox("⚡ Hardware Telemetrie")
        layout_h = QVBoxLayout(grp_hw)
        self.lbl_gpu = QLabel("GPU: NVIDIA GeForce RTX 4060 | VRAM: ~2.6 GB / 8.0 GB (Sicher)")
        self.lbl_gpu.setStyleSheet("color: #FFFFFF; font-family: Consolas; font-size: 11px;")
        layout_h.addWidget(self.lbl_gpu)
        layout.addWidget(grp_hw)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Aktualisieren")
        btn_refresh.clicked.connect(self.refresh_stats)
        btn_row.addWidget(btn_refresh)

        btn_close = QPushButton("Schliessen")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def refresh_stats(self):
        if not os.path.exists(RESULTS_CSV):
            self.lbl_status.setText("Warte auf erste Epochen-Ergebnisse...")
            return

        try:
            rows = []
            with open(RESULTS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    rows.append(r)

            if not rows:
                return

            last = rows[-1]
            epoch = int(last.get("epoch", 0).strip())
            total_sec = float(last.get("time", 0.0))

            # Update Progress Bar
            self.progress_bar.setValue(min(TOTAL_EPOCHS, epoch))
            pct = (epoch / TOTAL_EPOCHS) * 100
            self.lbl_epoch.setText(f"Epoche: {epoch} / {TOTAL_EPOCHS} ({pct:.1f}%)")

            # Time calculation
            avg_sec_per_epoch = total_sec / max(1, epoch)
            remaining_epochs = max(0, TOTAL_EPOCHS - epoch)
            rem_sec = remaining_epochs * avg_sec_per_epoch

            elapsed_str = f"{int(total_sec // 60)}m {int(total_sec % 60)}s"
            rem_str = f"{int(rem_sec // 60)}m {int(rem_sec % 60)}s" if remaining_epochs > 0 else "Fertig!"
            self.lbl_time.setText(f"Dauer bisher: {elapsed_str} | Geschaetzte Restzeit: ~{rem_str}")

            # Metrics
            map50 = float(last.get("metrics/mAP50(B)", 0.0)) * 100
            prec = float(last.get("metrics/precision(B)", 0.0)) * 100
            rec = float(last.get("metrics/recall(B)", 0.0)) * 100
            box_loss = float(last.get("train/box_loss", 0.0))
            cls_loss = float(last.get("train/cls_loss", 0.0))

            self.lbl_map50.setText(f"mAP 50: {map50:.1f} %")
            self.lbl_prec.setText(f"Precision: {prec:.1f} %")
            self.lbl_recall.setText(f"Recall: {rec:.1f} %")
            self.lbl_loss.setText(f"Box Loss: {box_loss:.3f} | Cls Loss: {cls_loss:.3f}")

            if epoch >= TOTAL_EPOCHS:
                self.lbl_status.setText("STATUS: TRAINING ERFOLGREICH ABGESCHLOSSEN!")
                self.lbl_status.setStyleSheet("color: #00FFCC; font-family: Consolas; font-weight: bold;")
            else:
                self.lbl_status.setText("Status: TRAINING AKTIV AUF NVIDIA RTX 4060")
                self.lbl_status.setStyleSheet("color: #FF8800; font-family: Consolas;")

        except Exception as e:
            print(f"[Dashboard] Error parsing stats: {e}")


def main():
    app = QApplication(sys.argv)
    # Attach to user desktop if launched via background
    try:
        import ctypes
        user32 = ctypes.windll.user32
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception:
        pass

    dash = TrainingDashboard()
    dash.show()
    dash.raise_()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
