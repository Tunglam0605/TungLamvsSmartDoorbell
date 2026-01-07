from config import FACE_BACKEND, FACE_BACKEND_STRICT


def create_face_recognition():
    backend = str(FACE_BACKEND or "").strip().lower()
    if backend in ("insightface", "arcface", "onnx"):
        try:
            from face.insightface_recognition import InsightFaceRecognition

            return InsightFaceRecognition()
        except Exception as exc:
            if FACE_BACKEND_STRICT:
                raise RuntimeError(f"InsightFace init failed: {exc}") from exc
            print(f"[Face] InsightFace init failed: {exc}. Falling back to TFLite.")

    from face.face_recognition import FaceRecognition

    return FaceRecognition()
