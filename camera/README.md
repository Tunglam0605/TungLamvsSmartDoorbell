# camera/

Thư mục quản lý truy xuất camera (Picamera2) cho Raspberry Pi.

## camera_manager.py
- Class `CameraManager` khởi tạo `Picamera2`, cấu hình preview `RGB888` với kích thước từ `FRAME_WIDTH/FRAME_HEIGHT` trong `config.py`.
- `get_frame()` trả về frame dạng `numpy.ndarray` (RGB888) để các module khác xử lý.
- Phụ thuộc: `picamera2` và `config.py`.

## __init__.py
- File đánh dấu package `camera`.
