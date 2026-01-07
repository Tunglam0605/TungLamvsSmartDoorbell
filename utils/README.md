# 🧰 utils/

Thư mục tiện ích xử lý ảnh đơn giản.

## 🛠️ utils.py
- `draw_face_label(frame_bgr, bbox, id, name, score)`:
  - Vẽ bbox + label nhận diện.
  - Có logic đảo trục X vì frame preview bị flip.
- `normalize_face_crop(face_crop, target_ratio=0.45)`:
  - Chuẩn hóa kích thước crop khuôn mặt theo tỉ lệ khung.

## 📦 __init__.py
- File đánh dấu package `utils`.

## 🧾 lcd_i2c.py
- Điều khiển LCD I2C 16x2 (PCF8574 hoặc RPLCD nếu có).
- `get_lcd_display()` trả singleton LCD để cập nhật trạng thái cửa/khuôn mặt.
- Tự vô hiệu nếu thiếu thư viện I2C hoặc không tìm thấy thiết bị.
