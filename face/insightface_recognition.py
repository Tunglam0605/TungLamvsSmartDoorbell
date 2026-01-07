import math
import os

import numpy as np
from insightface.model_zoo import get_model
from insightface.utils import face_align

from config import (
    FACE_DETECTION_CONFIDENCE,
    FACE_MIN_RELATIVE_SIZE,
    FACE_ROI_ENABLED,
    FACE_ROI_RELATIVE_W,
    FACE_ROI_RELATIVE_H,
    FACE_ROI_ROTATE_DEG,
    FACE_ROI_MIN_COVERAGE,
    FACE_ROI_CENTER_TOLERANCE_X,
    INSIGHTFACE_DET_MODEL_PATH,
    INSIGHTFACE_REC_MODEL_PATH,
    INSIGHTFACE_DET_SIZE,
    INSIGHTFACE_THRESHOLD,
    INSIGHTFACE_MARGIN,
)
from face.face_db import FaceDB


class _RelativeBBox:
    def __init__(self, xmin, ymin, width, height):
        self.xmin = float(xmin)
        self.ymin = float(ymin)
        self.width = float(width)
        self.height = float(height)


class _RelativeKeypoint:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)


class _LocationData:
    def __init__(self, bbox, keypoints):
        self.relative_bounding_box = bbox
        self.relative_keypoints = keypoints or []


class _Detection:
    def __init__(self, location_data):
        self.location_data = location_data


class _Detections:
    def __init__(self, detections):
        self.detections = detections


class InsightFaceRecognition:
    def __init__(self):
        self.det_model_path = INSIGHTFACE_DET_MODEL_PATH
        self.rec_model_path = INSIGHTFACE_REC_MODEL_PATH
        self.det_size = int(INSIGHTFACE_DET_SIZE)
        self.threshold = float(INSIGHTFACE_THRESHOLD)
        self.margin = float(INSIGHTFACE_MARGIN)

        if not os.path.isfile(self.det_model_path):
            raise FileNotFoundError(f"det model not found: {self.det_model_path}")
        if not os.path.isfile(self.rec_model_path):
            raise FileNotFoundError(f"rec model not found: {self.rec_model_path}")

        self.detector = get_model(self.det_model_path)
        self.detector.prepare(ctx_id=0, input_size=(self.det_size, self.det_size))
        self.recognizer = get_model(self.rec_model_path)
        self.recognizer.prepare(ctx_id=0)

        self.db = FaceDB()
        self.DB = self.db.get_all_embeddings()

        self._roi_enabled = bool(FACE_ROI_ENABLED)
        self._roi_w = float(FACE_ROI_RELATIVE_W)
        self._roi_h = float(FACE_ROI_RELATIVE_H)
        self._roi_angle = float(FACE_ROI_ROTATE_DEG)
        self._roi_min_coverage = max(0.0, min(1.0, float(FACE_ROI_MIN_COVERAGE)))
        self._roi_center_tol = max(0.0, min(0.5, float(FACE_ROI_CENTER_TOLERANCE_X)))

        self.last_face = None
        self.last_embedding = None
        self.last_bbox = None

    def reload_db(self):
        self.DB = self.db.get_all_embeddings()

    def _normalize(self, emb):
        if emb is None:
            return None
        vec = np.array(emb, dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec

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

    def _roi_coverage(self, bbox, samples=7):
        try:
            x0 = max(0.0, float(bbox.xmin))
            y0 = max(0.0, float(bbox.ymin))
            x1 = min(1.0, x0 + max(0.0, float(bbox.width)))
            y1 = min(1.0, y0 + max(0.0, float(bbox.height)))
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

    def _roi_center_ok(self, bbox):
        try:
            cx = float(bbox.xmin) + float(bbox.width) / 2.0
        except Exception:
            return False
        roi_w = max(0.1, min(1.0, float(self._roi_w)))
        max_offset = roi_w * self._roi_center_tol
        return abs(cx - 0.5) <= max_offset

    def detect_faces(self, frame):
        if frame is None:
            return _Detections([])
        h, w = frame.shape[:2]
        if h <= 0 or w <= 0:
            return _Detections([])

        bboxes, kpss = self.detector.detect(frame, max_num=0, metric="default")
        if bboxes is None or len(bboxes) == 0:
            return _Detections([])

        detections = []
        for idx, bbox in enumerate(bboxes):
            if bbox is None or len(bbox) < 4:
                continue
            score = float(bbox[4]) if len(bbox) > 4 else 1.0
            if score < float(FACE_DETECTION_CONFIDENCE):
                continue

            x1, y1, x2, y2 = bbox[:4]
            x1 = max(0.0, min(float(x1), w - 1.0))
            y1 = max(0.0, min(float(y1), h - 1.0))
            x2 = max(0.0, min(float(x2), w))
            y2 = max(0.0, min(float(y2), h))
            if x2 <= x1 or y2 <= y1:
                continue

            rel_box = _RelativeBBox(
                x1 / w,
                y1 / h,
                (x2 - x1) / w,
                (y2 - y1) / h,
            )

            if self._roi_enabled:
                if self._roi_min_coverage > 0 and self._roi_coverage(rel_box) < self._roi_min_coverage:
                    continue
                if not self._roi_center_ok(rel_box):
                    continue

            keypoints = []
            if kpss is not None and idx < len(kpss) and kpss[idx] is not None:
                for pt in kpss[idx]:
                    if pt is None or len(pt) < 2:
                        continue
                    keypoints.append(_RelativeKeypoint(pt[0] / w, pt[1] / h))

            detections.append(_Detection(_LocationData(rel_box, keypoints)))

        return _Detections(detections)

    def update_last_face(self, frame, detection):
        bbox = detection.location_data.relative_bounding_box
        h, w = frame.shape[:2]

        if FACE_MIN_RELATIVE_SIZE > 0:
            if bbox.width < FACE_MIN_RELATIVE_SIZE or bbox.height < FACE_MIN_RELATIVE_SIZE:
                raise ValueError("Face too small")

        x1 = max(0, int(bbox.xmin * w))
        y1 = max(0, int(bbox.ymin * h))
        x2 = min(w, x1 + int(bbox.width * w))
        y2 = min(h, y1 + int(bbox.height * h))

        face_crop = frame[y1:y2, x1:x2].copy()

        keypoints = detection.location_data.relative_keypoints
        if not keypoints:
            raise ValueError("No keypoints for alignment")
        kps = np.array([[kp.x * w, kp.y * h] for kp in keypoints], dtype=np.float32)
        aligned = face_align.norm_crop(frame, landmark=kps, image_size=self.recognizer.input_size[0])
        feat = self.recognizer.get_feat(aligned)
        embedding = self._normalize(feat[0] if isinstance(feat, np.ndarray) else feat)

        self.last_face = face_crop
        self.last_embedding = embedding
        self.last_bbox = (x1, y1, x2, y2)

        return face_crop, embedding, self.last_bbox

    def extract_embedding(self, face_crop):
        if face_crop is None:
            return None
        detections = self.detect_faces(face_crop)
        if not detections or not detections.detections:
            return None
        best = max(
            detections.detections,
            key=lambda d: d.location_data.relative_bounding_box.width
            * d.location_data.relative_bounding_box.height,
        )
        _, emb, _ = self.update_last_face(face_crop, best)
        return emb

    def recognize_embedding(self, embedding):
        if embedding is None:
            return None, None, -1
        emb = self._normalize(embedding)
        if emb is None:
            return None, None, -1

        best_id, best_name, best_score = None, None, -1.0
        second_score = -1.0
        for pid, person_info in self.DB.items():
            stored = person_info[1]
            if stored is None:
                continue
            stored = self._normalize(stored)
            if stored is None or stored.shape != emb.shape:
                continue
            score = float(np.dot(emb, stored))
            if score > best_score:
                second_score = best_score
                best_score = score
                best_id, best_name = pid, person_info[0]
            elif score > second_score:
                second_score = score

        if best_score >= self.threshold:
            if self.margin <= 0:
                return best_id, best_name, best_score
            if second_score < 0 or (best_score - second_score) >= self.margin:
                return best_id, best_name, best_score

        return None, None, best_score

    def add_new_person(self, name, embedding, id_detected=None):
        if id_detected:
            for p in self.db.data:
                if p["id"] == id_detected:
                    old_emb = np.array(p["embedding"], dtype=np.float32)
                    old_emb = self._normalize(old_emb)
                    new_emb = self._normalize(embedding)
                    if old_emb is None or new_emb is None:
                        break
                    merged = self._normalize((old_emb + new_emb) / 2.0)
                    p["embedding"] = merged.tolist()
                    self.db.save()
                    self.reload_db()
                    return (id_detected, p["name"], "updated")

        pid = self.db.add_person(name, self._normalize(embedding))
        self.reload_db()
        return (pid, name, "new")
