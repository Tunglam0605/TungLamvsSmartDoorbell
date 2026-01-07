import math

import cv2
import numpy as np
from PySide6 import QtCore, QtWidgets

from gui.qt_utils import frame_to_pixmap

try:
    from config import (
        FACE_ROI_RELATIVE_W,
        FACE_ROI_RELATIVE_H,
        FACE_ROI_ROTATE_DEG,
        FACE_ROI_MIN_COVERAGE,
    )
except Exception:
    FACE_ROI_RELATIVE_W = 0.5
    FACE_ROI_RELATIVE_H = 0.8
    FACE_ROI_ROTATE_DEG = 90.0
    FACE_ROI_MIN_COVERAGE = 0.5


class PersonDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Person")

        self.name_input = QtWidgets.QLineEdit()

        self.source_live_radio = QtWidgets.QRadioButton("Use guided live scan")
        self.source_file_radio = QtWidgets.QRadioButton("Use image file")
        self.source_group = QtWidgets.QButtonGroup(self)
        self.source_group.addButton(self.source_live_radio)
        self.source_group.addButton(self.source_file_radio)
        self.source_live_radio.setChecked(True)

        self.file_path_input = QtWidgets.QLineEdit()
        self.file_path_input.setReadOnly(True)
        self.file_browse_btn = QtWidgets.QPushButton("Browse...")
        self.file_browse_btn.clicked.connect(self._browse_file)

        self.source_live_radio.toggled.connect(self._sync_source_state)
        self.source_file_radio.toggled.connect(self._sync_source_state)

        form = QtWidgets.QFormLayout()
        form.addRow("Name*", self.name_input)

        source_box = QtWidgets.QVBoxLayout()
        source_box.addWidget(self.source_live_radio)
        source_box.addWidget(self.source_file_radio)

        file_row = QtWidgets.QHBoxLayout()
        file_row.addWidget(self.file_path_input)
        file_row.addWidget(self.file_browse_btn)

        source_widget = QtWidgets.QWidget()
        source_layout = QtWidgets.QVBoxLayout(source_widget)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addLayout(source_box)
        source_layout.addLayout(file_row)

        form.addRow("Source", source_widget)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._sync_source_state()

    def _sync_source_state(self):
        use_file = self.source_file_radio.isChecked()
        self.file_path_input.setEnabled(use_file)
        self.file_browse_btn.setEnabled(use_file)

    def _browse_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)",
        )
        if path:
            self.file_path_input.setText(path)
            self.source_file_radio.setChecked(True)

    def set_source_mode(self, mode):
        if mode == "file":
            self.source_file_radio.setChecked(True)
        else:
            self.source_live_radio.setChecked(True)

    def get_data(self):
        source = "file" if self.source_file_radio.isChecked() else "live"
        return {
            "name": self.name_input.text().strip(),
            "source": source,
            "file_path": self.file_path_input.text().strip(),
        }


class EditPersonDialog(QtWidgets.QDialog):
    def __init__(self, current_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Person")

        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setText(current_name or "")

        self.update_face_checkbox = QtWidgets.QCheckBox("Update face embedding")

        self.source_live_radio = QtWidgets.QRadioButton("Use guided live scan")
        self.source_file_radio = QtWidgets.QRadioButton("Use image file")
        self.source_group = QtWidgets.QButtonGroup(self)
        self.source_group.addButton(self.source_live_radio)
        self.source_group.addButton(self.source_file_radio)
        self.source_live_radio.setChecked(True)

        self.file_path_input = QtWidgets.QLineEdit()
        self.file_path_input.setReadOnly(True)
        self.file_browse_btn = QtWidgets.QPushButton("Browse...")
        self.file_browse_btn.clicked.connect(self._browse_file)

        self.update_face_checkbox.toggled.connect(self._sync_source_state)
        self.source_live_radio.toggled.connect(self._sync_source_state)
        self.source_file_radio.toggled.connect(self._sync_source_state)

        form = QtWidgets.QFormLayout()
        form.addRow("Name*", self.name_input)

        source_box = QtWidgets.QVBoxLayout()
        source_box.addWidget(self.update_face_checkbox)
        source_box.addWidget(self.source_live_radio)
        source_box.addWidget(self.source_file_radio)

        file_row = QtWidgets.QHBoxLayout()
        file_row.addWidget(self.file_path_input)
        file_row.addWidget(self.file_browse_btn)

        source_widget = QtWidgets.QWidget()
        source_layout = QtWidgets.QVBoxLayout(source_widget)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addLayout(source_box)
        source_layout.addLayout(file_row)

        form.addRow("Face", source_widget)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._sync_source_state()

    def _sync_source_state(self):
        enabled = self.update_face_checkbox.isChecked()
        self.source_live_radio.setEnabled(enabled)
        self.source_file_radio.setEnabled(enabled)
        use_file = enabled and self.source_file_radio.isChecked()
        self.file_path_input.setEnabled(use_file)
        self.file_browse_btn.setEnabled(use_file)

    def _browse_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)",
        )
        if path:
            self.file_path_input.setText(path)
            self.source_file_radio.setChecked(True)

    def get_data(self):
        source = "file" if self.source_file_radio.isChecked() else "live"
        return {
            "name": self.name_input.text().strip(),
            "update_embedding": self.update_face_checkbox.isChecked(),
            "source": source,
            "file_path": self.file_path_input.text().strip(),
        }


class EnrollmentDialog(QtWidgets.QDialog):
    def __init__(self, runtime, live_tab=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Face Enrollment")
        self.setMinimumWidth(720)

        self._runtime = runtime
        self._live_tab = live_tab
        self._timer = None
        self._final_embedding = None
        self._embeddings = {}
        self._pose_hold = 0

        self._pose_threshold = 0.18
        self._hold_target = 3
        self._poses = [
            ("front", "Look straight"),
            ("left", "Turn your head left"),
            ("right", "Turn your head right"),
        ]
        self._pose_index = 0

        self._roi_w = float(FACE_ROI_RELATIVE_W)
        self._roi_h = float(FACE_ROI_RELATIVE_H)
        self._roi_angle = float(FACE_ROI_ROTATE_DEG)
        self._roi_min_coverage = max(0.0, min(1.0, float(FACE_ROI_MIN_COVERAGE)))

        self.preview_label = QtWidgets.QLabel("No frame")
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setMinimumSize(520, 360)
        self.preview_label.setProperty("role", "preview")

        self.step_label = QtWidgets.QLabel("")
        self.step_label.setProperty("role", "section")
        self.status_label = QtWidgets.QLabel("Align your face inside the ROI")
        self.status_label.setProperty("role", "muted")
        self._update_step_text()

        self.front_value = QtWidgets.QLabel("Pending")
        self.left_value = QtWidgets.QLabel("Pending")
        self.right_value = QtWidgets.QLabel("Pending")
        for label in (self.front_value, self.left_value, self.right_value):
            label.setProperty("chip", True)

        progress_card = QtWidgets.QFrame()
        progress_card.setProperty("card", True)
        progress_layout = QtWidgets.QGridLayout(progress_card)
        progress_layout.setContentsMargins(12, 12, 12, 12)
        progress_layout.setHorizontalSpacing(12)
        progress_layout.setVerticalSpacing(6)

        def add_row(row, label, value):
            key = QtWidgets.QLabel(label)
            key.setProperty("role", "muted")
            progress_layout.addWidget(key, row, 0)
            progress_layout.addWidget(value, row, 1)

        add_row(0, "Front", self.front_value)
        add_row(1, "Left", self.left_value)
        add_row(2, "Right", self.right_value)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.step_label)
        layout.addWidget(self.status_label)
        layout.addSpacing(6)
        layout.addWidget(self.preview_label, 1)
        layout.addSpacing(6)
        layout.addWidget(progress_card)
        layout.addWidget(buttons)

        self._start_timer()

    def _start_timer(self):
        if self._timer is None:
            self._timer = QtCore.QTimer(self)
            self._timer.setInterval(200)
            self._timer.timeout.connect(self._on_tick)
            self._timer.start()

    def _stop_timer(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _update_step_text(self):
        if self._pose_index >= len(self._poses):
            return
        _, prompt = self._poses[self._pose_index]
        self.step_label.setText(
            f"Step {self._pose_index + 1}/{len(self._poses)}: {prompt}"
        )

    def _set_status(self, text):
        if text:
            self.status_label.setText(text)

    def _get_latest_frame(self):
        if self._live_tab is not None:
            frame = getattr(self._live_tab, "latest_frame", None)
            if frame is not None:
                return frame.copy()
        if self._runtime is not None:
            try:
                return self._runtime.read_frame()
            except Exception:
                return None
        return None

    def _draw_roi(self, frame, in_roi):
        if frame is None:
            return None
        h, w = frame.shape[:2]
        roi_w = max(0.1, min(1.0, float(self._roi_w)))
        roi_h = max(0.1, min(1.0, float(self._roi_h)))
        ax = max(2, int((roi_w * w) / 2))
        ay = max(2, int((roi_h * h) / 2))
        cx = int(w / 2)
        cy = int(h / 2)
        color = (60, 200, 80) if in_roi else (255, 120, 0)
        overlay = frame.copy()
        cv2.ellipse(overlay, (cx, cy), (ax, ay), self._roi_angle, 0, 360, color, 2)
        return overlay

    def _roi_contains(self, cx, cy):
        roi_w = max(0.1, min(1.0, float(self._roi_w)))
        roi_h = max(0.1, min(1.0, float(self._roi_h)))
        ax = roi_w / 2.0
        ay = roi_h / 2.0
        dx = cx - 0.5
        dy = cy - 0.5
        angle = math.radians(float(self._roi_angle) % 360.0)
        cos_a = math.cos(-angle)
        sin_a = math.sin(-angle)
        rx = dx * cos_a - dy * sin_a
        ry = dx * sin_a + dy * cos_a
        if ax <= 0 or ay <= 0:
            return False
        return (rx / ax) ** 2 + (ry / ay) ** 2 <= 1.0

    def _roi_coverage(self, bbox_rel, samples=7):
        try:
            x0 = max(0.0, float(bbox_rel["xmin"]))
            y0 = max(0.0, float(bbox_rel["ymin"]))
            x1 = min(1.0, x0 + max(0.0, float(bbox_rel["width"])))
            y1 = min(1.0, y0 + max(0.0, float(bbox_rel["height"])))
        except Exception:
            return 0.0
        w = x1 - x0
        h = y1 - y0
        if w <= 0 or h <= 0:
            return 0.0
        samples = max(3, int(samples))
        inside = 0
        total = samples * samples
        for ix in range(samples):
            px = x0 + (ix + 0.5) / samples * w
            for iy in range(samples):
                py = y0 + (iy + 0.5) / samples * h
                if self._roi_contains(px, py):
                    inside += 1
        return inside / float(total)

    def _classify_pose(self, yaw):
        if yaw is None:
            return None
        if yaw <= -self._pose_threshold:
            return "left"
        if yaw >= self._pose_threshold:
            return "right"
        return "front"

    def _update_progress(self, pose):
        if pose == "front":
            self.front_value.setText("OK")
        elif pose == "left":
            self.left_value.setText("OK")
        elif pose == "right":
            self.right_value.setText("OK")

    def _combine_embeddings(self):
        embs = []
        for pose, _ in self._poses:
            if pose in self._embeddings:
                embs.append(self._embeddings[pose])
        if not embs:
            return None
        stacked = np.stack(embs, axis=0)
        avg = np.mean(stacked, axis=0)
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg = avg / norm
        return avg

    def _capture_embedding(self, pose, embedding):
        emb = np.array(embedding, dtype=np.float32).copy()
        self._embeddings[pose] = emb
        self._update_progress(pose)

    def _finish(self):
        self._final_embedding = self._combine_embeddings()
        self._stop_timer()
        self.accept()

    def _on_tick(self):
        frame = self._get_latest_frame()
        if frame is None:
            self._set_status("Camera unavailable")
            return

        result = None
        if self._runtime is not None:
            try:
                result = self._runtime.infer_frame(frame)
            except Exception as exc:
                result = {"error": f"infer failed: {exc}"}

        bbox = result.get("bbox") if isinstance(result, dict) else None
        in_roi = False
        if bbox and frame is not None:
            h, w = frame.shape[:2]
            if h > 0 and w > 0:
                x1, y1, x2, y2 = bbox
                bbox_rel = {
                    "xmin": float(x1) / w,
                    "ymin": float(y1) / h,
                    "width": float(x2 - x1) / w,
                    "height": float(y2 - y1) / h,
                }
                coverage = self._roi_coverage(bbox_rel)
                in_roi = coverage >= self._roi_min_coverage

        preview = self._draw_roi(frame, in_roi)
        pixmap = frame_to_pixmap(preview, self.preview_label.size())
        if pixmap is not None:
            self.preview_label.setPixmap(pixmap)

        if not isinstance(result, dict) or result.get("error"):
            self._pose_hold = 0
            self._set_status("No face detected")
            return

        if not result.get("has_face"):
            self._pose_hold = 0
            self._set_status("No face. Keep your face inside the ROI.")
            return

        size_status = result.get("size_status")
        if size_status == "too_small":
            self._pose_hold = 0
            self._set_status("Move closer")
            return
        if size_status == "too_large":
            self._pose_hold = 0
            self._set_status("Move farther")
            return

        if not in_roi:
            self._pose_hold = 0
            self._set_status("Keep your face inside the ROI")
            return

        if result.get("is_real") is False:
            self._pose_hold = 0
            self._set_status("Liveness check failed")
            return

        expected_pose, prompt = self._poses[self._pose_index]
        current_pose = self._classify_pose(result.get("yaw"))
        if current_pose != expected_pose:
            self._pose_hold = 0
            self._set_status(prompt)
            return

        self._pose_hold += 1
        remaining = self._hold_target - self._pose_hold
        if remaining > 0:
            self._set_status(f"Hold still ({self._pose_hold}/{self._hold_target})")
            return

        embedding = result.get("embedding")
        if embedding is None:
            self._pose_hold = 0
            self._set_status("Embedding unavailable")
            return

        self._capture_embedding(expected_pose, embedding)
        self._pose_index += 1
        self._pose_hold = 0
        if self._pose_index >= len(self._poses):
            self._finish()
            return
        self._update_step_text()
        self._set_status("Align your face inside the ROI")

    def get_embedding(self):
        return self._final_embedding

    def reject(self):
        self._stop_timer()
        super().reject()

    def closeEvent(self, event):
        self._stop_timer()
        super().closeEvent(event)
