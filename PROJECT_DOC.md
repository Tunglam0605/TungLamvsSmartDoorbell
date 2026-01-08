# Smart Doorbell Project Documentation

This document describes the current project structure, runtime flow, and configuration.

## 🎯 Purpose
- Provide a local GUI for live camera preview, face recognition, and door control.
- Expose a FastAPI server for mobile app integration (events, lock/unlock).
- Optionally expose the API via a Cloudflare Tunnel from a single launcher.

## 🧭 High-level architecture

```
Camera -> DoorbellRuntime -> GUI (Live/People/About)
   |                           |        |
   |                           |        +-- DoorController (servo, LED, sound)
   |                           |        +-- DoorbellRingButton (GPIO)
   |                           |        +-- Event capture -> EventStore -> media/*.jpg + logs/events.jsonl
   |                           |
   +-- FaceDetection + Embedding + Liveness

FastAPI (/health, /events, /unlock, /lock)
   |
   +-- shares DoorController (from GUI) and EventStore
   +-- serves /media/* from media/
```

## 🚀 Entry points
- `run_all.py`
  - Starts FastAPI, GUI, and Cloudflare Tunnel.
  - Updates `PUBLIC_BASE_URL` and `DOORBELL_TUNNEL_URL` when tunnel is ready.
  - Pushes the tunnel/public URL to Firebase RTDB when enabled.
  - Shares GUI DoorController with the API (via `server.control`).
- `run_gui.py`
  - Starts GUI only (no API, no tunnel).

## 🗂️ Directory layout
- `camera/` - Picamera2 integration for Raspberry Pi camera.
- `face/` - Face detection, embedding, liveness, and face DB.
- `gui/` - PySide6 GUI tabs, dialogs, and hardware control.
- `server/` - FastAPI app and event store.
- `utils/` - Image utilities and LCD I2C handling.
- `models/` - TFLite, ONNX, and task files used by inference.
- `sounds/` - MP3 audio assets for ring and prompts.
- `media/` - Event images captured at runtime.
- `logs/` - JSONL event log output.
- `config.py` - Central configuration and defaults.

## 🧠 Core runtime flow
### 1) Live recognition (GUI Live tab)
- `DoorbellRuntime` reads frames from camera.
- `FaceRecognition` detects faces (optionally ROI-filtered).
- Embedding is extracted and matched against `face/known_faces/face_db.json`.
- Optional liveness uses `LivenessChecker` (modelrgb.onnx + blur + movement).
- GUI draws ROI and status, and can trigger door control.

### 2) Door control
- `DoorController` controls servo (open/close), LED, and LCD.
- Policies:
  - Hold door while face is present.
  - Require known identity.
  - Require live face.
- Plays open/close sounds when configured.

### 3) Event capture and storage
- `EventStore` writes images to `media/` and logs JSONL to `logs/events.jsonl`.
- `LiveTab` can auto-capture events at an interval for known faces.
- Doorbell ring events are logged when the GPIO button is pressed.
- API actions (unlock/lock) are logged as action events using the last captured image URL.

### 4) API
- `server/app.py` exposes:
  - `GET /health` - health check.
  - `GET /events` - returns event list (up to `EVENT_MAX_ITEMS`).
  - `POST /events/clear` - clears in-memory events, media images, and JSONL log.
  - `POST /unlock` - open door + light; logs `UNLOCK`.
  - `POST /lock` - close door + light; logs `LOCK`.
  - `GET /media/{file}` serves captured images.

## 👤 Face recognition stack
- Detection: MediaPipe FaceDetection.
- Embedding: TFLite model `models/MobileNet-v2_float.tflite`.
- Similarity: cosine distance; threshold in `config.py`.
- ROI filtering: ellipse-based region with coverage + center tolerance.
- DB: JSON store at `face/known_faces/face_db.json`.
- Optional backend: InsightFace (SCRFD + ArcFace) with keypoint alignment, enabled by `DOORBELL_FACE_BACKEND=insightface`.
- When switching backend, re-enroll faces because embedding formats are not compatible.

## 🧪 Liveness (anti-spoof)
- ONNX model `models/modelrgb.onnx`.
- Additional checks:
  - Laplacian sharpness threshold.
  - Micro movement across frames.
- Combines average score and movement rule to decide real/spoof.

## 🖥️ GUI overview
- Live tab: preview, status, door control, event capture.
- People tab: CRUD for face DB, add/update embeddings.
- About tab: tunnel URL, diagnostics, policy toggles.
- Tabs About/People require access ID/password from config.

## 📦 Data and storage
- `media/` holds event images captured by `EventStore` (pruned by `EVENT_MEDIA_MAX_FILES`).
- `logs/events.jsonl` stores append-only events (if enabled).
- `face/known_faces/face_db.json` stores identities and embeddings.
- Note: in-memory event list resets on restart (log file is not reloaded).

## 🧩 Dependencies (from `requirements.txt`)
- Core: `opencv-python-headless`, `numpy`, `mediapipe`, `tflite-runtime`
- Liveness: `onnxruntime`
- GUI: `PySide6`
- API: `fastapi`, `uvicorn`
- Hardware: `gpiozero`, `picamera2`
- Telegram: `python-telegram-bot`
- Other: `imutils`, `insightface`, `tensorflow-aarch64`
- `scipy` is required but noted to install via apt.

## ⚙️ Configuration reference
All defaults live in `config.py`. Many settings can be overridden by env vars.

### API and media
- `PUBLIC_BASE_URL` (default: trycloudflare URL)
- `API_HOST` (default: 0.0.0.0)
- `API_PORT` (default: 8000)
- `EVENT_CAPTURE_INTERVAL_SEC` (default: 5.0)
- `DOORBELL_EVENT_CAPTURE_ENABLED` (default: 1)
- `EVENT_MAX_ITEMS` (default: 500)
- `EVENT_MEDIA_DIR` (default: media/)
- `EVENT_MEDIA_MAX_FILES` (default: 200)
- `EVENT_LOG_ENABLED` (default: True)
- `EVENT_LOG_PATH` (default: logs/events.jsonl)
### Firebase RTDB (optional)
- `DOORBELL_FIREBASE_URL` (default: application-a1bfa-default-rtdb)
- `DOORBELL_FIREBASE_KEY` (default: Key_Cloud)
- `DOORBELL_FIREBASE_AUTH` (default: empty)
- `DOORBELL_FIREBASE_ENABLE` (default: 1)

### Camera
- `USE_PICAMERA2` (default: True)
- `FRAME_WIDTH` (default: 1280)
- `FRAME_HEIGHT` (default: 960)

### Face detection and ROI
- `FACE_DETECTION_CONFIDENCE` (default: 0.5)
- `FACE_MIN_RELATIVE_SIZE` (default: 0.0)
- `FACE_ROI_ENABLED` (default: 1)
- `FACE_ROI_RELATIVE_W` (default: 0.5)
- `FACE_ROI_RELATIVE_H` (default: 0.8)
- `FACE_ROI_ROTATE_DEG` (default: 90)
- `FACE_ROI_MIN_COVERAGE` (default: 0.5)
- `FACE_ROI_CENTER_TOLERANCE_X` (default: 0.15)
- `FACE_SIZE_MIN_RELATIVE_AREA` (default: 0.08)
- `FACE_SIZE_MAX_RELATIVE_AREA` (default: 0.35)

### Recognition
- `MODEL_PATH` (default: models/MobileNet-v2_float.tflite)
- `IMG_SIZE` (default: 224x224)
- `RECOGNITION_THRESHOLD` (default: 0.80)
- `RECOGNITION_MARGIN` (default: 0.0)
- `RECOGNITION_SMOOTH_WINDOW` (default: 3)
- `RECOGNITION_STABLE_COUNT` (default: 2)
- `RECOGNITION_STABLE_HOLD_SEC` (default: 1.0)
- `RECOGNITION_STABLE_MIN_SCORE` (default: 0.80)
- `N_DETECTION_FRAMES` (default: 3)
- `DB_PATH` (default: face/known_faces/face_db.json)
- `DOORBELL_FACE_BACKEND` (default: insightface)
- `DOORBELL_INSIGHTFACE_DET_MODEL` (default: models/scrfd_10g_bnkps.onnx)
- `DOORBELL_INSIGHTFACE_REC_MODEL` (default: models/w600k_r50.onnx)
- `DOORBELL_INSIGHTFACE_DET_SIZE` (default: 640)
- `DOORBELL_INSIGHTFACE_THRESHOLD` (default: 0.35)
- `DOORBELL_INSIGHTFACE_MARGIN` (default: 0.08)

### Liveness (anti-spoof)
- `LIVENESS_MODEL_PATH` (default: models/modelrgb.onnx)
- `LIVENESS_LAPLACIAN_THRESH` (default: 15)
- `MIN_FACE_MOVEMENT_RATIO` (default: 0.008)
- `MULTI_FRAME_COUNT` (default: 3)

### GUI
- `DOORBELL_GUI_LIVENESS` (default: 0)
- `DOORBELL_GUI_FACE` (default: 1)
- `DOORBELL_GUI_AUTO_INFER` (default: 1)
- `DOORBELL_GUI_THREAD_INFER` (default: 0)
- `DOORBELL_GUI_INFER_TIMEOUT_SEC` (default: 8)

### Face distance prompts
- `DOORBELL_FACE_DISTANCE_PROMPT` (default: 1)
- `DOORBELL_FACE_DISTANCE_PROMPT_NEAR_MP3`
- `DOORBELL_FACE_DISTANCE_PROMPT_FAR_MP3`
- `DOORBELL_FACE_DISTANCE_PROMPT_PLAYER`
- `DOORBELL_FACE_DISTANCE_PROMPT_CMD`
- `DOORBELL_FACE_DISTANCE_PROMPT_COOLDOWN` (default: 3)

### About and People tab access
- `DOORBELL_ABOUT_ID` (default: admin)
- `DOORBELL_ABOUT_PASSWORD` (default: admin)

### Doorbell ring button
- `DOORBELL_RING_ENABLED` (default: 1)
- `DOORBELL_RING_BUTTON_PIN` (default: 23)
- `DOORBELL_RING_BUTTON_PULL_UP` (default: 1)
- `DOORBELL_RING_BUTTON_BOUNCE_SEC` (default: 0.1)
- `DOORBELL_RING_SOUND_MP3`
- `DOORBELL_RING_SOUND_PLAYER`
- `DOORBELL_RING_COOLDOWN_SEC` (default: 1.5)

### LED and known-person alerts
- `KNOWN_ALERT_ENABLED` (default: False)
- `LED_PIN` (default: 17)
- `LED_ACTIVE_HIGH` (default: True)
- `LED_OFF_DELAY_SEC` (default: 0.0)
- `DOORBELL_KNOWN_ALERT`
- `DOORBELL_KNOWN_ALERT_COOLDOWN_SEC`
- `DOORBELL_KNOWN_REQUIRE_REAL`
- `DOORBELL_LIGHT_HOLD_ON_KNOWN`
- `DOORBELL_LIGHT_OFF_DELAY_SEC`
- `DOORBELL_LIGHT_PIN`
- `DOORBELL_LIGHT_ACTIVE_HIGH`
- `DOORBELL_LIGHT_ON_SEC`
- `DOORBELL_SOUND_PATH`
- `DOORBELL_SOUND_CMD`

### LCD I2C (16x2)
- `DOORBELL_LCD_ENABLED` (default: 1)
- `DOORBELL_LCD_I2C_BUS` (default: 1)
- `DOORBELL_LCD_I2C_ADDRESS` (default: 0x3f)
- `DOORBELL_LCD_COLS` (default: 16)
- `DOORBELL_LCD_ROWS` (default: 2)
- `DOORBELL_LCD_BACKLIGHT` (default: 1)
- `DOORBELL_LCD_UPDATE_MIN_INTERVAL_SEC` (default: 0.2)

### Servo and door mechanics
- `SERVO_PIN` (default: 18)
- `SERVO_OPEN_ANGLE` (default: 90)
- `SERVO_CLOSE_ANGLE` (default: 0)
- `SERVO_OPEN_SEC` (default: 2.0)
- `SERVO_FRAME_WIDTH` (default: 0.02)
- `SERVO_DETACH_AFTER_CLOSE` (default: True)
- `SERVO_DETACH_DELAY_SEC` (default: 0.2)
- `SERVO_DETACH_AFTER_OPEN` (default: True)
- `SERVO_DETACH_OPEN_DELAY_SEC` (default: 0.5)
- `SERVO_USE_PIGPIO` (default: False)
- `SERVO_MIN_ANGLE` (default: 0)
- `SERVO_MAX_ANGLE` (default: 180)
- `SERVO_MIN_PULSE_WIDTH` (default: 0.0005)
- `SERVO_MAX_PULSE_WIDTH` (default: 0.0025)

### Door policies
- `DOOR_LIGHT_FOLLOW_DOOR` (default: True)
- `DOOR_HOLD_ON_FACE` (default: True)
- `DOOR_CLOSE_DELAY_SEC` (default: 2.0)
- `DOOR_REQUIRE_KNOWN` (default: False)
- `DOOR_REQUIRE_REAL` (default: False)

### Door sounds
- `DOORBELL_DOOR_OPEN_SOUND_ENABLED` (default: 1)
- `DOORBELL_DOOR_OPEN_SOUND_MP3`
- `DOORBELL_DOOR_OPEN_SOUND_PLAYER`
- `DOORBELL_DOOR_CLOSE_SOUND_ENABLED` (default: 1)
- `DOORBELL_DOOR_CLOSE_SOUND_MP3`
- `DOORBELL_DOOR_CLOSE_SOUND_PLAYER`

### Tunnel (run_all.py)
- `DOORBELL_TUNNEL_ENABLE` (default: 1)
- `DOORBELL_TUNNEL_TARGET` (default: http://API_HOST:API_PORT)
- `DOORBELL_TUNNEL_CMD` (default: cloudflared tunnel --url {url} --no-autoupdate)
- `DOORBELL_TUNNEL_TIMEOUT_SEC` (default: 10)
- `PUBLIC_BASE_URL` / `DOORBELL_TUNNEL_URL` (set at runtime when tunnel is ready)

### Telegram
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Notes and limitations
- API has no auth; consider network isolation if exposed publicly.
- `GET /events` returns the latest list in memory (max `EVENT_MAX_ITEMS`).
- Event list is in-memory; logs are append-only but not reloaded on startup.
- `PUBLIC_BASE_URL` in `config.py` includes a hardcoded trycloudflare URL; update in production.
