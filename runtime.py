import threading
import time

import cv2
import numpy as np

from config import (
    FRAME_WIDTH,
    FRAME_HEIGHT,
    LIVENESS_MODEL_PATH,
    RECOGNITION_SMOOTH_WINDOW,
    RECOGNITION_STABLE_COUNT,
    RECOGNITION_STABLE_HOLD_SEC,
    RECOGNITION_STABLE_MIN_SCORE,
    FACE_SIZE_MIN_RELATIVE_AREA,
    FACE_SIZE_MAX_RELATIVE_AREA,
)
from utils.utils import normalize_face_crop


def _estimate_yaw_from_detection(detection):
    try:
        keypoints = detection.location_data.relative_keypoints
    except Exception:
        return None
    if not keypoints or len(keypoints) < 3:
        return None
    try:
        eye1 = keypoints[0]
        eye2 = keypoints[1]
        nose = keypoints[2]
        if float(eye1.x) <= float(eye2.x):
            left_eye, right_eye = eye1, eye2
        else:
            left_eye, right_eye = eye2, eye1
        dx_left = abs(float(nose.x) - float(left_eye.x))
        dx_right = abs(float(nose.x) - float(right_eye.x))
        denom = dx_left + dx_right
        if denom <= 1e-6:
            return None
        return (dx_right - dx_left) / denom
    except Exception:
        return None


class OpenCVCamera:
    def __init__(self, index=0, width=None, height=None):
        self.cap = cv2.VideoCapture(index)
        if width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def get_frame(self):
        if not self.cap.isOpened():
            return None
        ok, frame = self.cap.read()
        if not ok:
            return None
        return frame

    def close(self):
        if self.cap:
            self.cap.release()


class DoorbellRuntime:
    def __init__(self, camera_index=0, enable_liveness=False, enable_face=True):
        self.lock = threading.Lock()
        self.infer_lock = threading.Lock()
        self.enable_face = enable_face
        self.enable_liveness = bool(enable_liveness and enable_face)
        self._camera_import_error = None
        self._camera_is_rgb = False
        self._face_import_error = "not initialized"
        self._liveness_import_error = "not initialized"

        self.camera = self._init_camera(camera_index)
        self.face = self._init_face()
        self.liveness = self._init_liveness(self.enable_liveness)

        self._smooth_window = max(1, int(RECOGNITION_SMOOTH_WINDOW))
        self._stable_count = max(1, int(RECOGNITION_STABLE_COUNT))
        self._stable_hold_sec = max(0.0, float(RECOGNITION_STABLE_HOLD_SEC))
        self._stable_min_score = float(RECOGNITION_STABLE_MIN_SCORE)
        self._face_min_area = max(0.0, float(FACE_SIZE_MIN_RELATIVE_AREA))
        self._face_max_area = max(0.0, float(FACE_SIZE_MAX_RELATIVE_AREA))
        self._recent_ids = []
        self._stable_id = None
        self._stable_name = None
        self._stable_score = None
        self._stable_ts = 0.0

        self.last_frame = None
        self.last_face_crop = None
        self.last_embedding = None
        self.last_bbox = None
        self.last_result = None
        self.last_infer_ts = 0.0

    def _init_camera(self, camera_index):
        try:
            from camera.camera_manager import CameraManager as PiCameraManager
        except Exception as exc:
            PiCameraManager = None
            self._camera_import_error = exc

        if PiCameraManager is not None:
            try:
                cam = PiCameraManager()
                self._camera_is_rgb = True
                return cam
            except Exception as exc:
                self._camera_import_error = exc

        self._camera_is_rgb = False
        return OpenCVCamera(camera_index, FRAME_WIDTH, FRAME_HEIGHT)

    def _init_face(self):
        if not self.enable_face:
            self._face_import_error = "disabled"
            return None
        try:
            from face.face_factory import create_face_recognition
        except Exception as exc:
            self._face_import_error = exc
            return None
        try:
            face = create_face_recognition()
            self._face_import_error = None
            return face
        except Exception as exc:
            self._face_import_error = exc
            return None

    def _init_liveness(self, enable_liveness):
        if not enable_liveness:
            self._liveness_import_error = "disabled"
            return None
        try:
            from face.anti_spoof import LivenessChecker
        except Exception as exc:
            self._liveness_import_error = exc
            return None
        try:
            liveness = LivenessChecker(LIVENESS_MODEL_PATH)
            self._liveness_import_error = None
            return liveness
        except Exception as exc:
            self._liveness_import_error = exc
            return None

    def _smooth_recognition(self, rid, name, score):
        if self._smooth_window <= 1 or self._stable_count <= 1:
            return rid, name, score, False

        now = time.time()
        candidate_id = None
        candidate_name = None
        if rid and name and score is not None and score >= self._stable_min_score:
            candidate_id = rid
            candidate_name = name

        self._recent_ids.append((candidate_id, candidate_name, score, now))
        if len(self._recent_ids) > self._smooth_window:
            self._recent_ids = self._recent_ids[-self._smooth_window :]

        if candidate_id is not None:
            match_count = sum(
                1 for item in self._recent_ids if item[0] == candidate_id
            )
            if match_count >= self._stable_count:
                self._stable_id = candidate_id
                self._stable_name = candidate_name
                self._stable_score = score
                self._stable_ts = now
                return candidate_id, candidate_name, score, False

        if self._stable_id and self._stable_hold_sec > 0:
            if now - self._stable_ts <= self._stable_hold_sec:
                return (
                    self._stable_id,
                    self._stable_name,
                    self._stable_score,
                    True,
                )

        self._stable_id = None
        self._stable_name = None
        self._stable_score = None
        return None, None, score, True


    def read_frame(self):
        frame = self.camera.get_frame() if self.camera else None
        if frame is None:
            return None
        if self._camera_is_rgb:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        with self.lock:
            self.last_frame = frame
        return frame

    def infer_frame(self, frame):
        result = {
            "has_face": False,
            "bbox": None,
            "face_crop": None,
            "embedding": None,
            "is_real": None,
            "id": None,
            "name": None,
            "score": None,
            "yaw": None,
            "error": None,
        }

        if not self.enable_face:
            result["error"] = "Face module disabled"
            return result

        if self.face is None:
            result["error"] = f"Face module unavailable: {self._face_import_error}"
            return result

        with self.infer_lock:
            try:
                detections = self.face.detect_faces(frame)
            except Exception as exc:
                result["error"] = f"detect_faces failed: {exc}"
                return result

            if not detections or not detections.detections:
                return result

            try:
                best = max(
                    detections.detections,
                    key=lambda d: d.location_data.relative_bounding_box.width
                    * d.location_data.relative_bounding_box.height,
                )
            except Exception as exc:
                result["error"] = f"select best detection failed: {exc}"
                return result

            result["yaw"] = _estimate_yaw_from_detection(best)

            bbox_rel = best.location_data.relative_bounding_box
            rel_area = float(bbox_rel.width) * float(bbox_rel.height)
            h, w = frame.shape[:2]
            x1 = max(0, int(bbox_rel.xmin * w))
            y1 = max(0, int(bbox_rel.ymin * h))
            x2 = min(w, x1 + int(bbox_rel.width * w))
            y2 = min(h, y1 + int(bbox_rel.height * h))
            bbox = (x1, y1, x2, y2)

            result["has_face"] = True
            result["bbox"] = bbox
            result["size_area"] = rel_area

            if self._face_min_area and rel_area < self._face_min_area:
                result["size_status"] = "too_small"
                with self.lock:
                    self.last_bbox = bbox
                    self.last_result = result
                    self.last_infer_ts = time.time()
                return result

            if self._face_max_area and rel_area > self._face_max_area:
                result["size_status"] = "too_large"
                with self.lock:
                    self.last_bbox = bbox
                    self.last_result = result
                    self.last_infer_ts = time.time()
                return result

            try:
                face_crop, embedding, bbox = self.face.update_last_face(frame, best)
            except Exception as exc:
                result["error"] = f"update_last_face failed: {exc}"
                return result

            result["has_face"] = True
            result["face_crop"] = face_crop
            result["embedding"] = embedding
            result["bbox"] = bbox

            if self.liveness is not None:
                try:
                    normalized = normalize_face_crop(face_crop)
                    result["is_real"] = self.liveness.is_real(normalized, bbox)
                except Exception as exc:
                    result["error"] = f"liveness failed: {exc}"

            try:
                rid, name, score = self.face.recognize_embedding(embedding)
                rid, name, score, stabilizing = self._smooth_recognition(
                    rid, name, score
                )
                result["id"] = rid
                result["name"] = name
                result["score"] = score
                result["stabilizing"] = stabilizing
            except Exception as exc:
                result["error"] = f"recognize failed: {exc}"

        with self.lock:
            self.last_face_crop = face_crop
            self.last_embedding = embedding
            self.last_bbox = bbox
            self.last_result = result
            self.last_infer_ts = time.time()

        return result

    def force_recognize(self, frame):
        return self.infer_frame(frame)

    def extract_embedding(self, frame=None, face_crop=None):
        if not self.enable_face:
            return {"ok": False, "error": "Face module disabled"}
        if self.face is None:
            return {
                "ok": False,
                "error": f"Face module unavailable: {self._face_import_error}",
            }

        if face_crop is not None:
            emb = self.face.extract_embedding(face_crop)
            return {"ok": True, "embedding": emb, "bbox": None}

        if frame is None:
            return {"ok": False, "error": "No input image available"}

        detections = self.face.detect_faces(frame)
        if not detections or not detections.detections:
            return {"ok": False, "error": "No face detected in image"}
        best = max(
            detections.detections,
            key=lambda d: d.location_data.relative_bounding_box.width
            * d.location_data.relative_bounding_box.height,
        )
        _, emb, bbox = self.face.update_last_face(frame, best)
        return {"ok": True, "embedding": emb, "bbox": bbox}

    def add_person(self, name, embedding):
        if not name:
            return {"ok": False, "error": "Name is required"}
        if self.face is None:
            return {
                "ok": False,
                "error": f"Face module unavailable: {self._face_import_error}",
            }
        if embedding is None:
            return {"ok": False, "error": "Embedding missing"}
        emb = (
            embedding
            if isinstance(embedding, np.ndarray)
            else np.array(embedding, dtype=np.float32)
        )
        pid, pname, state = self.face.add_new_person(name, emb)
        return {"ok": True, "id": pid, "name": pname, "state": state}

    def reload_db(self):
        if self.face is not None:
            self.face.reload_db()

    def close(self):
        if hasattr(self.camera, "close"):
            try:
                self.camera.close()
            except Exception:
                pass
        if getattr(self.camera, "picam", None) is not None:
            try:
                self.camera.picam.stop()
            except Exception:
                pass
