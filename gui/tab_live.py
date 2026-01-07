import os
import time
import json

import cv2
import math
import shlex
import shutil
import subprocess
from PySide6 import QtCore, QtWidgets

from gui.alert import KnownPersonAlert
from gui.door_control import DoorController
from gui.doorbell_button import DoorbellRingButton
from gui.qt_utils import frame_to_pixmap
from utils.lcd_i2c import get_lcd_display
from runtime import DoorbellRuntime

try:
    from config import N_DETECTION_FRAMES
except Exception:
    N_DETECTION_FRAMES = 3

try:
    from config import EVENT_CAPTURE_INTERVAL_SEC, EVENT_CAPTURE_ENABLED
except Exception:
    EVENT_CAPTURE_INTERVAL_SEC = 5.0
    EVENT_CAPTURE_ENABLED = False

try:
    from config import API_HOST, API_PORT
except Exception:
    API_HOST = "0.0.0.0"
    API_PORT = 8000


try:
    from config import (
        FACE_ROI_ENABLED,
        FACE_ROI_RELATIVE_W,
        FACE_ROI_RELATIVE_H,
        FACE_ROI_ROTATE_DEG,
        FACE_DISTANCE_PROMPT_NEAR_MP3,
        FACE_DISTANCE_PROMPT_FAR_MP3,
        FACE_DISTANCE_PROMPT_PLAYER,
        FACE_DISTANCE_PROMPT_ENABLED,
        FACE_DISTANCE_PROMPT_COOLDOWN_SEC,
        FACE_DISTANCE_PROMPT_CMD,
        GUI_AUTO_INFER,
        GUI_THREAD_INFER,
        GUI_INFER_TIMEOUT_SEC,
        DOOR_REQUIRE_KNOWN,
    )
except Exception:
    FACE_ROI_ENABLED = False
    FACE_ROI_RELATIVE_W = 0.5
    FACE_ROI_RELATIVE_H = 0.5
    FACE_ROI_ROTATE_DEG = 90.0
    FACE_DISTANCE_PROMPT_NEAR_MP3 = ""
    FACE_DISTANCE_PROMPT_FAR_MP3 = ""
    FACE_DISTANCE_PROMPT_PLAYER = ""
    FACE_DISTANCE_PROMPT_ENABLED = True
    FACE_DISTANCE_PROMPT_COOLDOWN_SEC = 3.0
    FACE_DISTANCE_PROMPT_CMD = ""
    GUI_AUTO_INFER = True
    GUI_THREAD_INFER = False
    GUI_INFER_TIMEOUT_SEC = 8.0
    DOOR_REQUIRE_KNOWN = False


class InferenceWorker(QtCore.QObject):
    finished = QtCore.Signal(dict)

    def __init__(self, runtime, frame, token):
        super().__init__()
        self.runtime = runtime
        self.frame = frame
        self.token = token

    @QtCore.Slot()
    def run(self):
        start = time.perf_counter()
        try:
            result = self.runtime.infer_frame(self.frame)
        except Exception as exc:
            result = {
                "has_face": False,
                "bbox": None,
                "embedding": None,
                "is_real": None,
                "id": None,
                "name": None,
                "score": None,
                "error": f"infer failed: {exc}",
            }
        result["_token"] = self.token
        result["latency_ms"] = int((time.perf_counter() - start) * 1000)
        self.finished.emit(result)


class LiveTab(QtWidgets.QWidget):
    request_add_from_frame = QtCore.Signal()

    def __init__(self, runtime: DoorbellRuntime, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.latest_frame = None
        self.latest_result = None
        self._alert = KnownPersonAlert()
        self._door = DoorController()
        self._ring_button = DoorbellRingButton(on_press=self._on_ring_pressed)
        self.auto_infer = bool(GUI_AUTO_INFER)
        self.thread_infer = bool(GUI_THREAD_INFER)
        try:
            self._infer_timeout_sec = max(2.0, float(GUI_INFER_TIMEOUT_SEC))
        except (TypeError, ValueError):
            self._infer_timeout_sec = 8.0

        self._closing = False
        self._frame_counter = 0
        self._inference_running = False
        self._active_thread = None
        self._active_worker = None
        self._shown_live_status = False
        self._infer_token = 0
        self._infer_start_ts = 0.0
        self._timeout_count = 0
        self._event_interval = float(EVENT_CAPTURE_INTERVAL_SEC)
        self._last_event_ts = 0.0
        self._last_event_sync_ts = 0.0
        self._last_event_sync_id = None
        self._event_capture_enabled = bool(EVENT_CAPTURE_ENABLED)
        self._known_event_id = None
        self._known_event_active = False
        self._door_open_state = False

        self._prompt_enabled = bool(FACE_DISTANCE_PROMPT_ENABLED)
        try:
            self._prompt_cooldown_sec = max(0.5, float(FACE_DISTANCE_PROMPT_COOLDOWN_SEC))
        except (TypeError, ValueError):
            self._prompt_cooldown_sec = 3.0
        self._prompt_last_ts = 0.0
        self._prompt_cmd = str(FACE_DISTANCE_PROMPT_CMD).strip()
        self._prompt_near_mp3 = str(FACE_DISTANCE_PROMPT_NEAR_MP3).strip()
        self._prompt_far_mp3 = str(FACE_DISTANCE_PROMPT_FAR_MP3).strip()
        self._prompt_player = str(FACE_DISTANCE_PROMPT_PLAYER).strip()

        self.roi_rotate_deg = float(FACE_ROI_ROTATE_DEG)
        self._lcd = get_lcd_display()

        self.preview_label = QtWidgets.QLabel("No frame")
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setMinimumSize(640, 480)
        self.preview_label.setProperty("role", "preview")

        self.title_label = QtWidgets.QLabel("Smart Doorbell")
        self.title_label.setObjectName("Title")
        self.subtitle_label = QtWidgets.QLabel("Commercial access control console")
        self.subtitle_label.setObjectName("Subtitle")

        self.status_label = QtWidgets.QLabel("Status: idle")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)

        self.system_value = QtWidgets.QLabel("Idle")
        self.face_value = QtWidgets.QLabel("No")
        self.liveness_value = QtWidgets.QLabel("n/a")
        self.recog_value = QtWidgets.QLabel("n/a")
        self.score_value = QtWidgets.QLabel("n/a")
        self.stability_value = QtWidgets.QLabel("Stable")
        self.latency_value = QtWidgets.QLabel("n/a")
        self.door_state_value = QtWidgets.QLabel("Closed")
        self.api_value = QtWidgets.QLabel(f"{API_HOST}:{API_PORT}")
        self.capture_value = QtWidgets.QLabel("")
        self.last_event_value = QtWidgets.QLabel("None")

        self.status_card = QtWidgets.QFrame()
        self.status_card.setProperty("card", True)
        status_layout = QtWidgets.QGridLayout(self.status_card)
        status_layout.setContentsMargins(12, 12, 12, 12)
        status_layout.setHorizontalSpacing(12)
        status_layout.setVerticalSpacing(6)

        def add_row(row, label, value):
            key = QtWidgets.QLabel(label)
            key.setProperty("role", "muted")
            value.setProperty("chip", True)
            status_layout.addWidget(key, row, 0)
            status_layout.addWidget(value, row, 1)

        add_row(0, "System", self.system_value)
        add_row(1, "Face", self.face_value)
        add_row(2, "Identity", self.recog_value)
        add_row(3, "Score", self.score_value)
        add_row(4, "Door", self.door_state_value)
        add_row(5, "Last event", self.last_event_value)

        self.btn_force = QtWidgets.QPushButton("Capture + Recognize")
        self.btn_force.setProperty("kind", "secondary")
        self.btn_force.clicked.connect(self.on_force_recognize)

        self.btn_add = QtWidgets.QPushButton("Add from current frame")
        self.btn_add.setProperty("kind", "secondary")
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self._on_add_clicked)

        self.btn_open = QtWidgets.QPushButton("Open door")
        self.btn_open.clicked.connect(self.on_open_door)

        self.btn_close = QtWidgets.QPushButton("Close door")
        self.btn_close.setProperty("kind", "secondary")
        self.btn_close.clicked.connect(self.on_close_door)

        self.toggle_auto_infer = QtWidgets.QCheckBox("Auto recognition")
        self.toggle_auto_infer.setChecked(self.auto_infer)
        self.toggle_auto_infer.toggled.connect(self._on_auto_infer_toggled)

        self.toggle_event_capture = QtWidgets.QCheckBox("Auto capture")
        self.toggle_event_capture.setChecked(self._event_capture_enabled)
        self.toggle_event_capture.setEnabled(bool(EVENT_CAPTURE_ENABLED))
        self.toggle_event_capture.toggled.connect(self._on_capture_toggled)

        self.toggle_hold_on_face = QtWidgets.QCheckBox("Hold door while face present")
        self.toggle_require_known = QtWidgets.QCheckBox("Require known identity")
        self.toggle_require_real = QtWidgets.QCheckBox("Require live face")
        self.toggle_hold_on_face.toggled.connect(self._on_policy_toggled)
        self.toggle_require_known.toggled.connect(self._on_policy_toggled)
        self.toggle_require_real.toggled.connect(self._on_policy_toggled)

        door_available = bool(getattr(self._door, "available", False))
        self.toggle_hold_on_face.setChecked(bool(getattr(self._door, "hold_on_face", False)))
        self.toggle_require_known.setChecked(bool(getattr(self._door, "require_known", False)))
        self.toggle_require_real.setChecked(bool(getattr(self._door, "require_real", False)))

        self.toggle_hold_on_face.setEnabled(door_available)
        self.toggle_require_known.setEnabled(door_available and not bool(DOOR_REQUIRE_KNOWN))
        self.toggle_require_real.setEnabled(door_available)
        if door_available and bool(DOOR_REQUIRE_KNOWN):
            self.toggle_require_known.setChecked(True)

        action_card = QtWidgets.QFrame()
        action_card.setProperty("card", True)
        action_layout = QtWidgets.QVBoxLayout(action_card)
        action_layout.setContentsMargins(12, 12, 12, 12)
        action_layout.setSpacing(8)

        action_title = QtWidgets.QLabel("Quick Actions")
        action_title.setProperty("role", "section")
        action_layout.addWidget(action_title)

        door_row = QtWidgets.QHBoxLayout()
        door_row.addWidget(self.btn_open)
        door_row.addWidget(self.btn_close)

        capture_row = QtWidgets.QHBoxLayout()
        capture_row.addWidget(self.btn_force)
        capture_row.addWidget(self.btn_add)

        action_layout.addLayout(door_row)
        action_layout.addLayout(capture_row)

        right_panel = QtWidgets.QVBoxLayout()
        right_panel.addWidget(self.title_label)
        right_panel.addWidget(self.subtitle_label)
        right_panel.addSpacing(6)
        right_panel.addWidget(self.status_card)
        right_panel.addWidget(action_card)
        right_panel.addWidget(self.status_label)
        right_panel.addStretch()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(self.preview_label, 3)
        layout.addLayout(right_panel, 2)

        self._update_capture_label()
        self._refresh_door_state()

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start()

    def _play_prompt_mp3(self, path):
        if not self._prompt_enabled or not path:
            return False
        if not os.path.isfile(path):
            return False
        now = time.time()
        if now - self._prompt_last_ts < self._prompt_cooldown_sec:
            return False

        cmd = self._prompt_player
        args = None
        if cmd:
            try:
                args = shlex.split(cmd.format(path=path))
            except Exception:
                args = shlex.split(cmd) + [path]
        else:
            if shutil.which("mpg123"):
                args = ["mpg123", "-q", path]
            elif shutil.which("ffplay"):
                args = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
            elif shutil.which("omxplayer"):
                args = ["omxplayer", "-o", "local", path]
            elif shutil.which("mpv"):
                args = ["mpv", "--no-video", "--really-quiet", path]
            elif shutil.which("cvlc"):
                args = ["cvlc", "--play-and-exit", "--quiet", path]

        if not args:
            return False

        try:
            subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._prompt_last_ts = now
            return True
        except Exception:
            return False

    def _speak_prompt(self, text):
        if not self._prompt_enabled or not text:
            return False
        now = time.time()
        if now - self._prompt_last_ts < self._prompt_cooldown_sec:
            return False

        cmd = self._prompt_cmd
        if cmd:
            try:
                args = shlex.split(cmd.format(text=text))
            except Exception:
                args = shlex.split(cmd) + [text]
        else:
            args = None
            if shutil.which("espeak-ng"):
                args = ["espeak-ng", "-v", "vi", text]
            elif shutil.which("espeak"):
                args = ["espeak", "-v", "vi", text]

        if not args:
            return False

        try:
            subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._prompt_last_ts = now
            return True
        except Exception:
            return False

    def _maybe_prompt_distance(self, size_status):
        if size_status == "too_small":
            if self._play_prompt_mp3(self._prompt_near_mp3):
                return True
            return self._speak_prompt("dua khuon mat gan hon")
        if size_status == "too_large":
            if self._play_prompt_mp3(self._prompt_far_mp3):
                return True
            return self._speak_prompt("dua khuon mat ra xa")
        return False

    def _roi_bounds_px(self, shape):
        if not FACE_ROI_ENABLED:
            return None
        h, w = shape[:2]
        roi_w = max(0.1, min(1.0, float(FACE_ROI_RELATIVE_W)))
        roi_h = max(0.1, min(1.0, float(FACE_ROI_RELATIVE_H)))
        x0 = int((0.5 - roi_w / 2) * w)
        x1 = int((0.5 + roi_w / 2) * w)
        y0 = int((0.5 - roi_h / 2) * h)
        y1 = int((0.5 + roi_h / 2) * h)
        x0 = max(0, min(w - 1, x0))
        x1 = max(0, min(w - 1, x1))
        y0 = max(0, min(h - 1, y0))
        y1 = max(0, min(h - 1, y1))
        return x0, y0, x1, y1

    def _draw_ellipse_roi(
        self,
        img,
        x0,
        y0,
        x1,
        y1,
        color,
        thickness=2,
        fill_alpha=0.12,
        angle_deg=0.0,
    ):
        if img is None:
            return
        if x1 <= x0 or y1 <= y0:
            return
        cx = int((x0 + x1) / 2)
        cy = int((y0 + y1) / 2)
        ax = max(2, int((x1 - x0) / 2))
        ay = max(2, int((y1 - y0) / 2))

        if fill_alpha and fill_alpha > 0:
            overlay = img.copy()
            cv2.ellipse(overlay, (cx, cy), (ax, ay), float(angle_deg), 0, 360, color, -1)
            cv2.addWeighted(
                overlay,
                float(fill_alpha),
                img,
                1.0 - float(fill_alpha),
                0,
                img,
            )

        cv2.ellipse(img, (cx, cy), (ax, ay), float(angle_deg), 0, 360, color, thickness)

    def _draw_overlays(self, frame):
        if frame is None:
            return None
        overlay = frame.copy()

        roi = self._roi_bounds_px(overlay.shape)
        bbox = None
        if self.latest_result and self.latest_result.get("has_face"):
            if self.latest_result.get("bbox") is not None:
                bbox = self.latest_result.get("bbox")

        in_roi = False
        angle_deg = float(self.roi_rotate_deg) % 360.0
        if roi and bbox:
            x0, y0, x1, y1 = roi
            fx1, fy1, fx2, fy2 = bbox
            roi_cx = (x0 + x1) / 2.0
            roi_cy = (y0 + y1) / 2.0
            ax = max(1.0, (x1 - x0) / 2.0)
            ay = max(1.0, (y1 - y0) / 2.0)
            face_cx = (fx1 + fx2) / 2.0
            face_cy = (fy1 + fy2) / 2.0
            dx = face_cx - roi_cx
            dy = face_cy - roi_cy
            angle = math.radians(-angle_deg)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            rx = dx * cos_a - dy * sin_a
            ry = dx * sin_a + dy * cos_a
            norm = (rx / ax) ** 2 + (ry / ay) ** 2
            in_roi = norm <= 1.0

        if roi:
            x0, y0, x1, y1 = roi
            normal_color = (60, 200, 80)
            active_color = (255, 120, 0)
            roi_color = active_color if in_roi else normal_color
            fill_alpha = 0.18 if in_roi else 0.10
            self._draw_ellipse_roi(
                overlay,
                x0,
                y0,
                x1,
                y1,
                roi_color,
                thickness=2,
                fill_alpha=fill_alpha,
                angle_deg=angle_deg,
            )

        if bbox:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (46, 204, 113), 2)
        return overlay

    def _update_capture_label(self):
        if self._event_capture_enabled:
            self.capture_value.setText(f"On ({self._event_interval:.1f}s)")
        else:
            self.capture_value.setText("Off")

    def _sync_last_event_label(self):
        now = time.time()
        if now - self._last_event_sync_ts < 1.0:
            return
        self._last_event_sync_ts = now
        event = None
        try:
            from server.event_store import get_event_store
            store = get_event_store()
            events = store.list_events() if store is not None else []
            if events:
                event = events[0]
        except Exception:
            event = None

        if event is None:
            log_path = None
            try:
                from config import EVENT_LOG_PATH
                log_path = EVENT_LOG_PATH
            except Exception:
                log_path = None
            if log_path and os.path.isfile(log_path):
                try:
                    with open(log_path, "rb") as f:
                        f.seek(0, os.SEEK_END)
                        size = f.tell()
                        if size > 0:
                            offset = min(size, 4096)
                            f.seek(-offset, os.SEEK_END)
                            data = f.read().decode("utf-8", errors="ignore")
                            lines = [ln for ln in data.splitlines() if ln.strip()]
                            if lines:
                                event = json.loads(lines[-1])
                except Exception:
                    event = None

        if not event:
            return
        event_id = event.get("eventId")
        if event_id and event_id == self._last_event_sync_id:
            return
        self._last_event_sync_id = event_id
        self.last_event_value.setText(
            f"{event.get('type')} {event.get('eventId')} @ {event.get('timestamp')}"
        )

    def _update_lcd_status(self, result):
        lcd = getattr(self, "_lcd", None)
        if lcd is None:
            return
        door = getattr(self, "_door", None)
        door_open = bool(door and getattr(door, "_is_open", False))

        person_type = "NONE"
        person_name = ""
        if result and result.get("has_face"):
            size_status = result.get("size_status")
            if size_status == "too_small":
                person_type = "MOVE_CLOSE"
            elif size_status == "too_large":
                person_type = "MOVE_FAR"
            else:
                is_real = result.get("is_real")
                if is_real is False:
                    person_type = "SPOOF"
                else:
                    rid = result.get("id")
                    name = result.get("name")
                    score = result.get("score")
                    if rid and name and score is not None:
                        person_type = "KNOWN"
                        person_name = str(name)
                    else:
                        person_type = "UNKNOWN"
        try:
            lcd.set_status(door_open=door_open, person_type=person_type, person_name=person_name)
        except Exception:
            return

    def _refresh_door_state(self):
        door = getattr(self, "_door", None)
        available = bool(door and getattr(door, "available", False))
        is_open = bool(door and getattr(door, "_is_open", False))
        self.door_state_value.setText("Open" if is_open else "Closed")
        self.btn_open.setEnabled(available and not is_open)
        self.btn_close.setEnabled(available and is_open)
        self.btn_open.setVisible(True)
        self.btn_close.setVisible(True)
        self.toggle_hold_on_face.setEnabled(available)
        self.toggle_require_known.setEnabled(available)
        self.toggle_require_real.setEnabled(available)
        if getattr(self, "_lcd", None) is not None:
            try:
                self._lcd.set_status(door_open=is_open)
            except Exception:
                pass

    def _on_auto_infer_toggled(self, checked):
        self.auto_infer = bool(checked)
        if self.auto_infer:
            self.status_label.setText("Status: auto recognition enabled")
        else:
            self.status_label.setText("Status: auto recognition disabled")

    def _on_capture_toggled(self, checked):
        self._event_capture_enabled = bool(checked)
        self._update_capture_label()
        if self._event_capture_enabled:
            self.status_label.setText("Status: auto capture enabled")
        else:
            self.status_label.setText("Status: auto capture disabled")

    def _on_policy_toggled(self, checked):
        door = getattr(self, "_door", None)
        if door is None:
            return
        door.hold_on_face = bool(self.toggle_hold_on_face.isChecked())
        if bool(DOOR_REQUIRE_KNOWN):
            door.require_known = True
            if not self.toggle_require_known.isChecked():
                self.toggle_require_known.setChecked(True)
        else:
            door.require_known = bool(self.toggle_require_known.isChecked())
        door.require_real = bool(self.toggle_require_real.isChecked())
        self.status_label.setText("Status: door policies updated")

    def _on_timer(self):
        if self._closing:
            return
        frame = self.runtime.read_frame()
        if frame is None:
            self.status_label.setText("Status: camera unavailable")
            self.system_value.setText("Camera offline")
            self._refresh_door_state()
            self._update_lcd_status(None)
            self._sync_last_event_label()
            return

        self.latest_frame = frame
        render_frame = self._draw_overlays(frame)
        pixmap = frame_to_pixmap(render_frame if render_frame is not None else frame, self.preview_label.size())
        if pixmap is not None:
            self.preview_label.setPixmap(pixmap)

        if (
            not self._shown_live_status
            and not self._inference_running
            and self.latest_result is None
        ):
            if self.auto_infer:
                self.status_label.setText("Status: live (auto infer on)")
                self.system_value.setText("Live")
            else:
                self.status_label.setText(
                    "Status: live (auto infer off - press Capture + Recognize)"
                )
                self.system_value.setText("Live")
            self._shown_live_status = True

        if self.auto_infer:
            if self._frame_counter % max(1, int(N_DETECTION_FRAMES)) == 0:
                self._start_inference(frame, reason="auto")

        self._frame_counter += 1

        if self.thread_infer and self._inference_running:
            now = time.time()
            if self._infer_start_ts and now - self._infer_start_ts > self._infer_timeout_sec:
                self._on_infer_timeout(self._infer_token)

        self._refresh_door_state()

    def _start_inference(self, frame, reason="auto"):
        if self._closing or self._inference_running or frame is None:
            return

        self._inference_running = True
        self.status_label.setText("Status: inferring...")
        self.system_value.setText("Inferring")
        self._shown_live_status = False

        if not self.thread_infer:
            start = time.perf_counter()
            try:
                result = self.runtime.infer_frame(frame)
            except Exception as exc:
                result = {
                    "has_face": False,
                    "bbox": None,
                    "embedding": None,
                    "is_real": None,
                    "id": None,
                    "name": None,
                    "score": None,
                    "error": f"infer failed: {exc}",
                }
            result["latency_ms"] = int((time.perf_counter() - start) * 1000)
            self._inference_running = False
            self._infer_start_ts = 0.0
            self._timeout_count = 0
            self.latest_result = result
            self._update_status_text(result)
            self.btn_add.setEnabled(bool(result and result.get("has_face")))
            return

        self._infer_token += 1
        token = self._infer_token
        self._infer_start_ts = time.time()

        worker = InferenceWorker(self.runtime, frame.copy(), token)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_inference_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._active_thread = thread
        self._active_worker = worker
        thread.start()

    def _on_inference_done(self, result):
        if self._closing:
            return
        if not self.thread_infer:
            return
        token = result.get("_token")
        if token != self._infer_token:
            return
        self._inference_running = False
        self._infer_start_ts = 0.0
        self._timeout_count = 0
        self.latest_result = result
        self._update_status_text(result)
        self.btn_add.setEnabled(bool(result and result.get("has_face")))
        self._active_worker = None
        if self._active_thread is not None and not self._active_thread.isRunning():
            self._active_thread = None

    def _on_thread_finished(self):
        self._active_thread = None

    def _on_infer_timeout(self, token):
        if self._closing:
            return
        if not self.thread_infer:
            return
        if not self._inference_running or token != self._infer_token:
            return
        self._inference_running = False
        self._active_worker = None
        self._infer_start_ts = 0.0
        self._timeout_count += 1
        self.system_value.setText("Timeout")
        if self._timeout_count >= 3:
            self.auto_infer = False
            self.toggle_auto_infer.setChecked(False)
            self.status_label.setText(
                "Status: inference timeout (auto infer disabled)"
            )
        else:
            self.status_label.setText("Status: inference timeout")

        thread = self._active_thread
        if thread is not None and thread.isRunning():
            thread.terminate()
            thread.wait(1000)
        self._active_thread = None

    def _update_status_text(self, result):
        if not result:
            self.status_label.setText("Status: no result")
            self.system_value.setText("Idle")
            return

        error = result.get("error")
        if error:
            self.status_label.setText(f"Status: {error}")
            self.system_value.setText("Error")
        else:
            self.status_label.setText("Status: live")
            self.system_value.setText("Live")

        has_face = bool(result.get("has_face"))
        self.face_value.setText("Yes" if has_face else "No")

        is_real = result.get("is_real")
        if is_real is None:
            self.liveness_value.setText("n/a")
        else:
            self.liveness_value.setText("Real" if is_real else "Spoof")

        size_status = result.get("size_status")
        if size_status == "too_small":
            self.status_label.setText("Status: move closer")
            self.system_value.setText("Move closer")
            self._maybe_prompt_distance(size_status)
        elif size_status == "too_large":
            self.status_label.setText("Status: move farther")
            self.system_value.setText("Move farther")
            self._maybe_prompt_distance(size_status)

        rid = result.get("id")
        name = result.get("name")
        score = result.get("score")
        stabilizing = bool(result.get("stabilizing"))

        if score is None:
            self.recog_value.setText("n/a")
            self.score_value.setText("n/a")
        elif rid and name:
            self.recog_value.setText(f"{name} ({rid})")
            self.score_value.setText(f"{score:.2f}")
        else:
            self.recog_value.setText("Unknown")
            self.score_value.setText(f"{score:.2f}")

        self.stability_value.setText("Stabilizing" if stabilizing else "Stable")

        latency_ms = result.get("latency_ms")
        if latency_ms is None:
            self.latency_value.setText("n/a")
        else:
            self.latency_value.setText(f"{latency_ms} ms")

        size_status = result.get("size_status")
        if size_status not in ("too_small", "too_large"):
            door = getattr(self, "_door", None)
            door_open_before = bool(door and getattr(door, "_is_open", False))
            if self._alert is not None:
                self._alert.handle_result(result)
            if door is not None:
                db_empty = True
                face = getattr(self.runtime, "face", None)
                if face is not None:
                    try:
                        db_empty = len(getattr(face, "DB", {}) or {}) == 0
                    except Exception:
                        db_empty = True
                original_require_known = getattr(door, "require_known", False)
                if db_empty:
                    door.require_known = True
                door.handle_result(result)
                if db_empty:
                    door.require_known = original_require_known
            door_open_after = bool(door and getattr(door, "_is_open", False))
            force_event = bool(door_open_after and not door_open_before)
            self._maybe_capture_event(result, door_open=door_open_after, force=force_event)
            if self._door_open_state and not door_open_after:
                self._known_event_active = False
                self._known_event_id = None
            self._door_open_state = door_open_after
        self._refresh_door_state()
        self._update_lcd_status(result)
        self._sync_last_event_label()


    def _on_ring_pressed(self):
        frame = None
        if self.latest_frame is not None:
            frame = self.latest_frame.copy()
        elif getattr(self.runtime, "last_frame", None) is not None:
            frame = self.runtime.last_frame.copy()
        if frame is None:
            try:
                frame = self.runtime.read_frame()
            except Exception:
                frame = None
        if frame is None:
            return

        result = self.latest_result
        if result is None:
            result = getattr(self.runtime, "last_result", None)

        if result is None or result.get("size_status") is None:
            try:
                result = self.runtime.infer_frame(frame)
            except Exception:
                result = result or {}

        event_type = "RING"
        person_name = None
        meta = {"type": "doorbell"}
        if result and result.get("has_face"):
            rid = result.get("id")
            name = result.get("name")
            score = result.get("score")
            if rid and name and score is not None:
                event_type = "KNOWN"
                person_name = name
            else:
                event_type = "UNKNOWN"
            meta.update({
                "id": rid,
                "name": name,
                "score": score,
                "is_real": result.get("is_real"),
                "bbox": result.get("bbox"),
            })

        try:
            from server.event_store import get_event_store
            store = get_event_store()
            event = store.add_event(
                event_type,
                frame,
                person_name=person_name,
                source="button",
                meta=meta,
            )
        except Exception:
            return
        if not event:
            return
        def _update():
            self.last_event_value.setText(
                f"{event.get('type')} {event.get('eventId')} @ {event.get('timestamp')}"
            )
            self.status_label.setText("Status: doorbell pressed")
            self.system_value.setText("Ring")
        QtCore.QTimer.singleShot(0, _update)

    def _maybe_capture_event(self, result, door_open=None, force=False):
        if not result or not result.get("has_face"):
            return
        if result.get("size_status") in ("too_small", "too_large"):
            return
        rid = result.get("id")
        name = result.get("name")
        score = result.get("score")
        event_type = "KNOWN" if rid and name and score is not None else "UNKNOWN"
        if event_type != "KNOWN":
            return

        if door_open is None:
            door = getattr(self, "_door", None)
            door_open = bool(door and getattr(door, "_is_open", False))

        if not door_open:
            self._known_event_active = False
            self._known_event_id = None
            if not force:
                return

        if door_open and self._known_event_active and not force:
            return

        if not force and not self._event_capture_enabled:
            return

        now = time.time()
        if not force and now - self._last_event_ts < self._event_interval:
            return
        frame = None
        if self.latest_frame is not None:
            frame = self.latest_frame.copy()
        elif getattr(self.runtime, "last_frame", None) is not None:
            frame = self.runtime.last_frame.copy()
        if frame is None:
            try:
                frame = self.runtime.read_frame()
            except Exception:
                frame = None
        if frame is None:
            return
        person_name = name if event_type == "KNOWN" else None
        meta = {
            "id": rid,
            "name": name,
            "score": score,
            "is_real": result.get("is_real"),
            "bbox": result.get("bbox"),
        }
        try:
            from server.event_store import get_event_store
            store = get_event_store()
            event = store.add_event(
                event_type,
                frame,
                person_name=person_name,
                source="gui",
                meta=meta,
            )
            if event:
                self.last_event_value.setText(
                    f"{event.get('type')} {event.get('eventId')} @ {event.get('timestamp')}"
                )
                self._last_event_ts = now
                self._known_event_active = True
                self._known_event_id = rid
        except Exception:
            return

    def on_force_recognize(self):
        frame = self.runtime.read_frame()
        if frame is None:
            self.status_label.setText("Status: camera unavailable")
            self.system_value.setText("Camera offline")
            return
        self._start_inference(frame, reason="manual")

    def on_open_door(self):
        door = getattr(self, "_door", None)
        if door is None or not getattr(door, "available", False):
            self.status_label.setText("Status: door control unavailable")
            return
        ok, message = door.open_and_close()
        light_ok = False
        try:
            light_ok = door.set_light_state(True)
        except Exception:
            light_ok = False
        if ok:
            status = "Status: door opened"
            self.system_value.setText("Door action")
        else:
            status = f"Status: door error: {message}"
            self.system_value.setText("Door error")
        if not light_ok:
            status += " (light unavailable)"
        self.status_label.setText(status)
        self._refresh_door_state()

    def on_close_door(self):
        door = getattr(self, "_door", None)
        if door is None or not getattr(door, "available", False):
            self.status_label.setText("Status: door control unavailable")
            return
        door.close()
        light_ok = False
        try:
            light_ok = door.set_light_state(False)
        except Exception:
            light_ok = False
        status = "Status: door closed"
        self.system_value.setText("Door action")
        if not light_ok:
            status += " (light unavailable)"
        self.status_label.setText(status)
        self._refresh_door_state()

    def _on_add_clicked(self):
        self.request_add_from_frame.emit()

    def shutdown(self):
        self._closing = True
        if self.timer is not None:
            self.timer.stop()
        if self._alert is not None:
            self._alert.close()
        if getattr(self, "_door", None) is not None:
            self._door.shutdown()
        if getattr(self, "_ring_button", None) is not None:
            self._ring_button.close()
        thread = self._active_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(5000)
            if thread.isRunning():
                thread.terminate()
                thread.wait(1000)
        self._active_thread = None
        self._active_worker = None
