# server/

Thư mục API server (FastAPI) cho app mobile và log sự kiện.

## app.py
- Khởi tạo FastAPI, mount static `/media`.
- Model API:
  - `GET /health` kiểm tra server.
  - `GET /events` trả danh sách sự kiện.
  - `POST /unlock` mở cửa + bật LED.
  - `POST /lock` đóng cửa + tắt LED.
- Ghi log action qua `EventStore`.
- `_force_typing_extensions()` đảm bảo `typing_extensions` đúng bản trong venv.

## event_store.py
- `EventStore`:
  - Lưu ảnh sự kiện vào `media/` và trả URL theo `PUBLIC_BASE_URL`.
  - Ghi log JSONL vào `logs/events.jsonl` nếu bật.
  - `add_event()` cho KNOWN/UNKNOWN.
  - `log_action()` cho UNLOCK/LOCK.
  - `list_events()` trả danh sách sự kiện gần nhất.

## control.py
- Lưu/đọc `DoorController` dùng chung giữa GUI và API.

## __init__.py
- File đánh dấu package `server`.
