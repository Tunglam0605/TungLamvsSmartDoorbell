# gui/

Thư mục giao diện GUI (PySide6) và điều khiển phần cứng (LED/servo).

## app_window.py
- Cửa sổ chính `AppWindow`:
  - Tạo `DoorbellRuntime` và các tab Live/People/About.
  - Tab About được bảo vệ bằng ID/mật khẩu trong `config.py` (`ABOUT_ACCESS_ID`, `ABOUT_ACCESS_PASSWORD`).
  - Tab People cũng yêu cầu ID/mật khẩu tương tự (cùng cấu hình).
  - Quản lý shutdown an toàn (dừng thread, đóng runtime).

## tab_live.py
- Tab Live: xem camera, chạy nhận diện, hiển thị trạng thái.
- Thành phần chính:
  - `InferenceWorker` chạy nhận diện theo frame.
  - Hiển thị ROI elip, bbox, trạng thái nhận diện/liveness.
  - Quick Actions: `Open door`, `Close door`, `Capture + Recognize`, `Add from current frame`.
  - Tự động chụp event theo interval và gửi vào `server.event_store`.
  - Tích hợp `DoorController` (servo + LED) và `KnownPersonAlert`.
  - Phát âm thanh nhắc “lại gần/ra xa” theo kích thước khuôn mặt.
- Phụ thuộc `config.py` cho ROI, inference, auto-capture, prompt âm thanh.

## tab_people.py
- Tab quản lý người quen (CRUD): Add/Edit/Delete/Refresh.
- `AddPersonWorker`/`UpdatePersonWorker` chạy trong thread.
- Dùng `FaceDB` để đọc/ghi `face_db.json`.
- Hỗ trợ thêm người từ frame hiện tại hoặc từ file ảnh.

## dialogs.py
- `PersonDialog`: thêm người mới (name + nguồn ảnh Live/File).
- `EditPersonDialog`: đổi tên + tùy chọn cập nhật embedding.

## doorbell_button.py
- Lắng nghe nút chuông GPIO (mặc định GPIO23).
- Khi nhấn: phát âm thanh chuông từ `sounds/`.
- Cấu hình qua `config.py` hoặc env `DOORBELL_RING_*`.

## door_control.py
- `DoorController` điều khiển servo cửa bằng `gpiozero.AngularServo`.
- Hỗ trợ:
  - Mở/đóng thủ công hoặc tự động theo nhận diện.
  - Giữ cửa mở khi còn khuôn mặt, đóng sau `DOOR_CLOSE_DELAY_SEC`.
  - Bật/tắt LED theo trạng thái cửa.
  - Phát âm thanh khi mở/đóng cửa.
- Tham số điều khiển từ `config.py` hoặc env `DOORBELL_*`.

## alert.py
- `KnownPersonAlert`: bật LED/sound khi nhận diện người quen.
- `LightController`: wrapper LED GPIO (bật/tắt, hẹn giờ).
- `SoundPlayer`: phát âm thanh bằng lệnh hệ thống.

## tab_about.py
- Tab About: hiển thị tunnel URL, copy nhanh.
- Hiển thị Diagnostics (Liveness/Stability/Inference/API/Capture).
- Hiển thị Automation & Policies (Auto recognition, Auto capture, door policies).

## qt_utils.py
- `bgr_to_qimage()` và `frame_to_pixmap()` chuyển frame OpenCV sang Qt.
- `apply_theme()` thiết lập theme/stylesheet UI.

## __init__.py
- File đánh dấu package `gui`.
