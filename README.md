# 🚪 Pi5 Smart Doorbell

Hệ thống chuông cửa thông minh chạy trên Raspberry Pi 5: nhận diện khuôn mặt, điều khiển cửa, lưu sự kiện, và cung cấp API cho app điện thoại.

## ✨ Điểm nổi bật
- 📷 Live camera + nhận diện khuôn mặt (InsightFace mặc định).
- 🧠 ROI + liveness (tùy chọn) để giảm nhận nhầm.
- 🔒 Điều khiển cửa/LED/LCD qua GPIO.
- 🌐 FastAPI cho mobile app (events, lock/unlock).
- 🚀 Cloudflare tunnel + tự cập nhật URL lên Firebase RTDB.

## ✅ Yêu cầu cơ bản
- Raspberry Pi 5 + camera (hoặc webcam USB).
- Python 3.9+ (khuyến nghị 3.11).
- Nếu dùng Pi camera: bật camera trong `raspi-config`.
- (Tuỳ chọn) `cloudflared` nếu muốn tunnel.

## 🧱 Cài đặt trên máy mới (bắt buộc)
### 1) Clone code
```bash
git clone git@github.com:Tunglam0605/TungLamvsSmartDoorbell.git
cd TungLamvsSmartDoorbell
```

### 2) Tạo môi trường ảo + cài package
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Cài models (bắt buộc)
Models **không được đưa vào Git** (đã bỏ qua `models/`). Sau khi clone, bạn cần tự tải/copy vào thư mục `models/`.

```bash
mkdir -p models
```

**Các file cần có:**
- `scrfd_10g_bnkps.onnx` (InsightFace detector)
- `w600k_r50.onnx` (InsightFace recognizer)
- `MobileNet-v2_float.tflite` (fallback TFLite, chỉ cần nếu dùng `DOORBELL_FACE_BACKEND=tflite` hoặc tắt strict)
- `modelrgb.onnx` (liveness, chỉ cần nếu bật `GUI_ENABLE_LIVENESS`)

**Tải InsightFace model tự động (tuỳ chọn):**
```bash
python - <<'PY'
from insightface.model_zoo import get_model
get_model("scrfd_10g_bnkps", download=True)
get_model("w600k_r50", download=True)
print("Downloaded to ~/.insightface/models")
PY
cp ~/.insightface/models/scrfd_10g_bnkps.onnx models/
cp ~/.insightface/models/w600k_r50.onnx models/
```

## ▶️ Chạy hệ thống
### Cách 1: chạy đầy đủ (GUI + API + Tunnel)
```bash
./.venv/bin/python run_all.py
```
Hoặc:
```bash
source .venv/bin/activate
python run_all.py
```

### Cách 2: chỉ chạy GUI (không API, không tunnel)
```bash
python run_gui.py
```

### Tự chạy khi khởi động (systemd user service)
Hiện **đang tắt** để tránh lỗi khi chưa có màn hình đăng nhập.
Nếu cần bật lại, dùng phần hướng dẫn trong lịch sử chỉnh sửa hoặc yêu cầu mình thêm lại.

## 🌐 API cho mobile app
**Base URL:** `http://<API_HOST>:<API_PORT>` hoặc URL tunnel `https://<id>.trycloudflare.com`

### GET `/health`
```json
{ "ok": true }
```

### GET `/events`
Trả về danh sách event mới nhất (tối đa `EVENT_MAX_ITEMS`).

```json
[
  {
    "eventId": "evt_001",
    "timestamp": "2025-12-31 06:10:34",
    "type": "UNKNOWN",
    "imageUrl": "https://<public>/media/evt_001_20251231_061034.jpg",
    "personName": null
  },
  {
    "eventId": "evt_002",
    "timestamp": "2025-12-31 06:10:40",
    "type": "KNOWN",
    "imageUrl": "https://<public>/media/evt_002_20251231_061040.jpg",
    "personName": "Anh Tuan"
  }
]
```

### POST `/unlock` / `/lock`
```json
{ "eventId": "evt_002", "source": "app" }
```

### POST `/events/clear`
Xoá toàn bộ event trên Pi5 (RAM + ảnh + log).
```json
{ "removeMedia": true, "removeLog": true }
```
Nếu không gửi body, mặc định vẫn xoá cả ảnh và log.

## ⚙️ Biến môi trường quan trọng
- `API_HOST`, `API_PORT`
- `DOORBELL_TUNNEL_ENABLE` (0 để tắt tunnel)
- `DOORBELL_TUNNEL_CMD`, `DOORBELL_TUNNEL_TARGET`
- `PUBLIC_BASE_URL`, `DOORBELL_TUNNEL_URL`
- `DOORBELL_FACE_BACKEND` (`insightface` | `tflite`)
- `DOORBELL_FACE_STRICT` (1 = bắt buộc InsightFace)
- `DOORBELL_INSIGHTFACE_DET_SIZE` (mặc định 640)
- `DOORBELL_DOOR_CLOSE_DELAY_SEC` (thời gian tự đóng cửa khi mất mặt)
- `DOORBELL_FIREBASE_URL`, `DOORBELL_FIREBASE_KEY`, `DOORBELL_FIREBASE_AUTH`, `DOORBELL_FIREBASE_ENABLE`

## 🧠 Cách hoạt động (tóm tắt sâu)
1) Camera đọc frame → nhận diện khuôn mặt (detector + embedding).
2) So khớp embedding với DB (`face/known_faces/face_db.json`).
3) Nếu bật liveness, kiểm tra thật/giả trước khi mở cửa.
4) GUI hiển thị trạng thái, door control và lưu event.
5) FastAPI phục vụ app, trả event mới nhất và điều khiển cửa.

## 📁 Dữ liệu & thư mục
- `media/`: ảnh sự kiện
- `logs/events.jsonl`: log JSONL
- `face/known_faces/face_db.json`: DB người quen

## 🛠️ Lỗi thường gặp
- **Thiếu model**: báo `FileNotFoundError` → kiểm tra `models/`.
- **Không có cloudflared**: đặt `DOORBELL_TUNNEL_ENABLE=0`.
- **Không mở được GUI**: cần màn hình/VNC hoặc cấu hình X11.
- **Lỗi SciPy trên Pi**: cài nhanh `sudo apt install -y python3-scipy`.
- **Picamera2 không chạy**: cài `python3-picamera2` và bật camera trong `raspi-config`.

## 📚 Tài liệu chi tiết
- Xem `PROJECT_DOC.md` để hiểu kiến trúc và luồng xử lý sâu hơn.
- Thư mục `face/` và `utils/` có README riêng.
