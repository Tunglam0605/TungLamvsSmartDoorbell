import cv2
import math
import numpy as np
import mediapipe as mp
import tflite_runtime.interpreter as tflite
from scipy.spatial.distance import cosine

from config import MODEL_PATH, IMG_SIZE, RECOGNITION_THRESHOLD, RECOGNITION_MARGIN, FACE_DETECTION_CONFIDENCE, FACE_MIN_RELATIVE_SIZE, FACE_ROI_ENABLED, FACE_ROI_RELATIVE_W, FACE_ROI_RELATIVE_H, FACE_ROI_ROTATE_DEG, FACE_ROI_MIN_COVERAGE, FACE_ROI_CENTER_TOLERANCE_X
from face.face_db import FaceDB

class FaceRecognition:
    def __init__(self):
        self.img_size = IMG_SIZE
        self.threshold = RECOGNITION_THRESHOLD

        self.db = FaceDB()
        self.DB = self.db.get_all_embeddings()

        self.interpreter = tflite.Interpreter(
            model_path=MODEL_PATH,
            num_threads=4
        )
        self.interpreter.allocate_tensors()

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        self.detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=FACE_DETECTION_CONFIDENCE
        )

        self.last_face = None          # face_crop
        self.last_embedding = None
        self.last_bbox = None

    def reload_db(self):
        self.DB = self.db.get_all_embeddings()


    def _roi_coverage(self, bbox, samples=7):
        if not FACE_ROI_ENABLED:
            return 1.0
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

    def _roi_contains(self, cx, cy):
        if not FACE_ROI_ENABLED:
            return True
        roi_w = max(0.1, min(1.0, float(FACE_ROI_RELATIVE_W)))
        roi_h = max(0.1, min(1.0, float(FACE_ROI_RELATIVE_H)))
        ax = roi_w / 2.0
        ay = roi_h / 2.0
        dx = cx - 0.5
        dy = cy - 0.5
        angle = math.radians(float(FACE_ROI_ROTATE_DEG) % 360.0)
        cos_a = math.cos(-angle)
        sin_a = math.sin(-angle)
        rx = dx * cos_a - dy * sin_a
        ry = dx * sin_a + dy * cos_a
        if ax <= 0 or ay <= 0:
            return False
        return (rx / ax) ** 2 + (ry / ay) ** 2 <= 1.0

    def _roi_center_ok(self, bbox):
        if not FACE_ROI_ENABLED:
            return True
        try:
            cx = float(bbox.xmin) + float(bbox.width) / 2.0
        except Exception:
            return False
        roi_w = max(0.1, min(1.0, float(FACE_ROI_RELATIVE_W)))
        tol = max(0.0, min(0.5, float(FACE_ROI_CENTER_TOLERANCE_X)))
        max_offset = roi_w * tol
        return abs(cx - 0.5) <= max_offset


    def _roi_bounds(self):
        if not FACE_ROI_ENABLED:
            return None
        roi_w = max(0.1, min(1.0, float(FACE_ROI_RELATIVE_W)))
        roi_h = max(0.1, min(1.0, float(FACE_ROI_RELATIVE_H)))
        cx = 0.5
        cy = 0.5
        x0 = max(0.0, cx - roi_w / 2)
        x1 = min(1.0, cx + roi_w / 2)
        y0 = max(0.0, cy - roi_h / 2)
        y1 = min(1.0, cy + roi_h / 2)
        return x0, y0, x1, y1

    def preprocess_face(self, face_bgr):
        face = cv2.resize(face_bgr, self.img_size, interpolation=cv2.INTER_CUBIC)
        face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        face = face.astype(np.float32)
        face = (face - 127.5) / 128.0
        return np.expand_dims(face, axis=0)  # [1,H,W,3]

    def get_embedding(self, face_crop):
        inp = self.preprocess_face(face_crop)
        self.interpreter.set_tensor(self.input_details[0]['index'], inp)
        self.interpreter.invoke()
        emb = self.interpreter.get_tensor(self.output_details[0]['index'])[0]
        return emb / np.linalg.norm(emb)

    def recognize_embedding(self, embedding):
        best_id, best_name, best_score = None, None, -1
        second_score = -1
        for id, person_info in self.DB.items(): # person_info: (id, emb)
            emb = person_info[1]
            if emb is None or getattr(emb, "shape", None) != getattr(embedding, "shape", None):
                continue
            score = 1 - cosine(embedding, emb)
            if score > best_score:
                second_score = best_score
                best_id, best_name, best_score = id, person_info[0], score
            elif score > second_score:
                second_score = score
        if best_score >= self.threshold:
            margin = float(RECOGNITION_MARGIN)
            if margin <= 0 or second_score < 0 or (best_score - second_score) >= margin:
                return best_id, best_name, best_score
        return None, None, best_score

    def detect_faces(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb)
        if not results or not results.detections:
            return results
        if not FACE_ROI_ENABLED:
            return results
        min_cov = max(0.0, min(1.0, float(FACE_ROI_MIN_COVERAGE)))
        filtered = []
        for det in results.detections:
            bbox = det.location_data.relative_bounding_box
            if min_cov > 0:
                coverage = self._roi_coverage(bbox)
                if coverage < min_cov:
                    continue
            if not self._roi_center_ok(bbox):
                continue

            filtered.append(det)
        results.detections = filtered
        return results

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
        embedding = self.get_embedding(face_crop)

        self.last_face = face_crop
        self.last_embedding = embedding
        self.last_bbox = (x1, y1, x2, y2)

        return face_crop, embedding, self.last_bbox

    def extract_embedding(self, face_crop):
        emb = self.get_embedding(face_crop)
        return emb

    def add_new_person(self, name, embedding, id_detected=None):
        """
        Thêm người mới hoặc cập nhật embedding nếu đã có ID.

        Nếu id_detected được cung cấp → update embedding theo ID.
        Nếu không có id_detected → thêm mới.

        Trả về: (id, name, status) với status = "new" hoặc "updated"
        """

        if id_detected:
            # Cập nhật theo ID
            for p in self.db.data:
                if p["id"] == id_detected:
                    old_emb = np.array(p["embedding"], dtype=np.float32)
                    new_emb = (old_emb + embedding) / 2
                    new_emb /= np.linalg.norm(new_emb)
                    p["embedding"] = new_emb.tolist()
                    self.db.save()
                    self.reload_db()
                    return (id_detected, p["name"], "updated")

        # Thêm mới
        pid = self.db.add_person(name, embedding)
        self.reload_db()
        return (pid, name, "new")
