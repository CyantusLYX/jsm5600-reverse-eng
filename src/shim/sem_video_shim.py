#!/usr/bin/env python3
import sys
import zmq
import cv2
import numpy as np
import threading
import json
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QFont


class SEMVideoShim(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JEOL SEM - Linux Video Shim")
        self.resize(800, 640)

        # --- UI Setup ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.video_label = QLabel("Waiting for Video...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.layout.addWidget(self.video_label)

        # --- State ---
        self.current_mag = 1000
        self.current_accv = 15000
        self.scan_speed = 1  # 1 = Fast, >1 = Slow
        self.is_scanning = False
        self.micron_bar_width_px = 0
        self.micron_text = "10um"

        # --- IPC (ZeroMQ SUB) ---
        self.zmq_ctx = zmq.Context()
        self.zmq_sub = self.zmq_ctx.socket(zmq.SUB)
        try:
            self.zmq_sub.connect("tcp://127.0.0.1:5556")
            self.zmq_sub.setsockopt_string(zmq.SUBSCRIBE, "")
            print("[Shim] Connected to IPC (tcp://127.0.0.1:5556)")
        except Exception as e:
            print(f"[Shim] IPC Connection failed: {e}")

        # --- Video Capture ---
        # Open /dev/video0.
        # Note: We prefer YUYV or MJPEG.
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.video_label.setText("Error: No Camera (/dev/video0)")

        # Try to set resolution (standard NTSC/PAL is 720x480 or 640x480)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Buffer for integration (Slow Scan)
        self.accum_buffer = None
        self.alpha = 0.1  # Integration factor

        # --- Timers ---
        # IPC Polling (Check often)
        self.ipc_timer = QTimer()
        self.ipc_timer.timeout.connect(self.check_ipc)
        self.ipc_timer.start(50)

        # Video Refresh (~30 FPS)
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self.update_frame)
        self.video_timer.start(33)

    def check_ipc(self):
        try:
            while True:
                # Non-blocking receive
                msg_bytes = self.zmq_sub.recv(flags=zmq.NOBLOCK)
                msg = json.loads(msg_bytes.decode("utf-8"))

                event = msg.get("event")
                value = msg.get("value")

                if event == "MAG":
                    self.current_mag = value
                    print(f"[Shim] Mag changed: x{value}")
                elif event == "ACCV":
                    self.current_accv = value
                    print(f"[Shim] Accv changed: {value / 1000} kV")
                elif event == "SPEED":
                    self.scan_speed = value
                    print(f"[Shim] Speed changed: {value}")
                elif event == "SCAN_STATUS":
                    self.is_scanning = bool(value)
                    print(f"[Shim] Scan: {self.is_scanning}")

        except zmq.Again:
            pass
        except Exception as e:
            print(f"[Shim] IPC Error: {e}")

    def update_frame(self):
        if not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        # --- 1. Grayscale Conversion (Luma Extraction) ---
        # MS210x sends YUYV usually. OpenCV converts to BGR by default on read()
        # if CAP_PROP_CONVERT_RGB is true (default).
        # So 'frame' is BGR.
        # Convert to Grayscale to simulate SEM signal and remove chroma noise.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # --- 2. Image Processing (Integration) ---
        display_frame = gray

        if self.scan_speed > 1:  # Slow scan logic
            # Simple simulated integration for now
            if self.accum_buffer is None or self.accum_buffer.shape != gray.shape:
                self.accum_buffer = gray.astype(np.float32)
            else:
                cv2.accumulateWeighted(gray, self.accum_buffer, self.alpha)

            display_frame = cv2.convertScaleAbs(self.accum_buffer)
        else:
            self.accum_buffer = None  # Reset on fast scan

        # --- 3. Convert to QImage ---
        h, w = display_frame.shape
        qt_img = QImage(display_frame.data, w, h, w, QImage.Format.Format_Grayscale8)

        # --- 4. Draw Overlay (Micron Bar) ---
        pixmap = QPixmap.fromImage(qt_img)
        painter = QPainter(pixmap)
        self.draw_overlay(painter, w, h)
        painter.end()

        # --- 5. Scale to Window ---
        scaled_pixmap = pixmap.scaled(
            self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        self.video_label.setPixmap(scaled_pixmap)

    def draw_overlay(self, painter, w, h):
        # Setup Font
        font = QFont("Courier New", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 0))  # Yellow

        # 1. Info Text
        info_text = f"MAG: x{self.current_mag}  {self.current_accv / 1000:.1f}kV"
        if self.scan_speed > 1:
            info_text += " (SLOW)"
        else:
            info_text += " (TV)"

        painter.drawText(10, 30, info_text)

        # 2. Micron Bar Calculation
        # Assuming basic calibration:
        # Field of View (FOV) width in microns = Constant / Mag
        # Let's assume at x1000, FOV is 120um (Typical for JEOL 5600?)
        # Base Constant K = 1000 * 120 = 120,000

        if self.current_mag > 0:
            fov_width_um = 120000.0 / self.current_mag
            um_per_pixel = fov_width_um / w

            # Find a nice round number for the bar (e.g. 10um, 50um, 100um)
            target_bar_width_px = w / 5  # Target ~20% of screen width
            target_um = target_bar_width_px * um_per_pixel

            # Round target_um to nearest 1, 10, 100
            scale_steps = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
            bar_um = 10
            for step in scale_steps:
                if target_um >= step:
                    bar_um = step

            bar_px = int(bar_um / um_per_pixel)

            # Draw Bar
            bar_x = w - bar_px - 20
            bar_y = h - 30
            painter.fillRect(bar_x, bar_y, bar_px, 5, QColor(255, 255, 0))

            # Draw Label
            label = f"{bar_um} um"
            painter.drawText(bar_x, bar_y - 10, label)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SEMVideoShim()
    window.show()
    sys.exit(app.exec())
