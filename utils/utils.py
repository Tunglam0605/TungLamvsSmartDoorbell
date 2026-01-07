# utils.py
import cv2

def draw_face_label(frame_bgr, bbox, id, name, score):
    """
    Vẽ bounding box + label lên frame
    bbox: (x1, y1, x2, y2) theo frame gốc
    """
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = bbox

    # Do frame đã flip ngang khi hiển thị
    x1_new = w - x2
    x2_new = w - x1

    label = f"{id} - {name}: ({score:.2f})" if id else f"Unknown ({score:.2f})"

    cv2.rectangle(
        frame_bgr,
        (x1_new, y1),
        (x2_new, y2),
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame_bgr,
        label,
        (x1_new, y1 - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

def normalize_face_crop(face_crop, target_ratio=0.45):
    """
    target_ratio: tỉ lệ tối đa mặt / frame
    """
    h, w = face_crop.shape[:2]
    max_size = int(min(h, w) * target_ratio)

    if h > max_size or w > max_size:
        scale = max_size / max(h, w)
        face_crop = cv2.resize(
            face_crop,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_AREA
        )
    return face_crop

