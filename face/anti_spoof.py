import cv2
import numpy as np
import onnxruntime as ort

from config import (
    LIVENESS_LAPLACIAN_THRESH,
    MIN_FACE_MOVEMENT_RATIO,
    MULTI_FRAME_COUNT,
)

# ================================================================
# Sharpness (anti print / screen)
# ================================================================
def compute_laplacian_blur(gray):
    return cv2.Laplacian(gray, cv2.CV_64F).var()


# ================================================================
# LivenessChecker — modelrgb.onnx backend
# ================================================================
class LivenessChecker:
    def __init__(self, model_path):
        self.session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

        self.scores = []
        self.last_center = None

    # ------------------------------------------------------------
    # modelrgb preprocess
    # ------------------------------------------------------------
    def preprocess(self, face_img):
        """
        modelrgb.onnx:
        - input: RGB
        - range: [0,1]
        - shape: (1,3,112,112)
        """
        img = cv2.resize(face_img, (112, 112))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = img.transpose(2, 0, 1)
        return img[None, ...]

    # ------------------------------------------------------------
    # modelrgb inference
    # ------------------------------------------------------------
    def predict_real_prob(self, face_img):
        inp = self.preprocess(face_img)
        out = self.session.run(None, {self.input_name: inp})[0]

        # modelrgb output: (1,1) → prob real
        return float(out[0][0])

    # ------------------------------------------------------------
    # Micro-movement
    # ------------------------------------------------------------
    def detect_face_movement(self, box):
        x1, y1, x2, y2 = box
        cx = (x1 + x2) * 0.5
        cy = (y1 + y2) * 0.5

        if self.last_center is None:
            self.last_center = (cx, cy)
            return True

        px, py = self.last_center
        movement_px = np.hypot(cx - px, cy - py)
        self.last_center = (cx, cy)

        bbox_width = x2 - x1
        bbox_height = y2 - y1
        movement_ratio = movement_px / max(bbox_width, bbox_height)

        return movement_ratio >= MIN_FACE_MOVEMENT_RATIO

    # ------------------------------------------------------------
    def reset(self):
        self.scores.clear()
        self.last_center = None

    # ------------------------------------------------------------
    # MAIN API — GIỮ NGUYÊN
    # ------------------------------------------------------------
    def is_real(self, face_img, bbox):

        # 1) Sharpness
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        lap_thresh = LIVENESS_LAPLACIAN_THRESH + min(20, face_img.shape[0] / 10)
        if compute_laplacian_blur(gray) < lap_thresh:
            return False

        # 2) modelrgb inference
        real_prob = self.predict_real_prob(face_img)

        self.scores.append(real_prob)
        if len(self.scores) > MULTI_FRAME_COUNT:
            self.scores.pop(0)

        avg_prob = float(np.mean(self.scores))

        # 3) Movement
        movement_ok = self.detect_face_movement(bbox)

        # --------------------------------------------------------
        # FINAL RULE
        # --------------------------------------------------------
        return (avg_prob >= 0.25) or (movement_ok and avg_prob >= 0.18)
