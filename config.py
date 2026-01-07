# config.py
import os

# =========================================================
# BASE PATH
# =========================================================
BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE_DIR, "models")

# =========================================================
# API / MEDIA
# =========================================================
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://fitted-jeffrey-sen-data.trycloudflare.com")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
EVENT_CAPTURE_INTERVAL_SEC = 5.0
EVENT_CAPTURE_ENABLED = os.getenv("DOORBELL_EVENT_CAPTURE_ENABLED", "1").strip().lower() not in ("0", "false", "no")
EVENT_MAX_ITEMS = 500
EVENT_MEDIA_DIR = os.path.join(BASE_DIR, "media")
try:
    EVENT_MEDIA_MAX_FILES = max(0, int(os.getenv("DOORBELL_EVENT_MEDIA_MAX_FILES", "200")))
except ValueError:
    EVENT_MEDIA_MAX_FILES = 200
EVENT_LOG_ENABLED = True
EVENT_LOG_PATH = os.path.join(BASE_DIR, "logs", "events.jsonl")

# =========================================================
# FIREBASE RTDB (optional)
# =========================================================
FIREBASE_RTDB_URL = os.getenv(
    "DOORBELL_FIREBASE_URL",
    "https://application-a1bfa-default-rtdb.firebaseio.com/",
)
FIREBASE_RTDB_KEY = os.getenv("DOORBELL_FIREBASE_KEY", "Key_Cloud")
FIREBASE_RTDB_AUTH = os.getenv("DOORBELL_FIREBASE_AUTH", "")
FIREBASE_RTDB_ENABLE = os.getenv("DOORBELL_FIREBASE_ENABLE", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)

# =========================================================
# CAMERA CONFIG
# =========================================================
USE_PICAMERA2 = True
FRAME_WIDTH = 1280
FRAME_HEIGHT = 960

# =====================================================
# FACE RECOGNITION
# =====================================================
FACE_DETECTION_CONFIDENCE = 0.5
FACE_MIN_RELATIVE_SIZE = 0.0
FACE_ROI_ENABLED = os.getenv("FACE_ROI_ENABLED", "1").strip().lower() not in ("0", "false", "no")
FACE_ROI_RELATIVE_W = float(os.getenv("FACE_ROI_RELATIVE_W", "0.5"))
FACE_ROI_RELATIVE_H = float(os.getenv("FACE_ROI_RELATIVE_H", "0.8"))
FACE_ROI_ROTATE_DEG = float(os.getenv("FACE_ROI_ROTATE_DEG", "90"))
FACE_ROI_MIN_COVERAGE = float(os.getenv("FACE_ROI_MIN_COVERAGE", "0.5"))
FACE_ROI_CENTER_TOLERANCE_X = float(os.getenv("FACE_ROI_CENTER_TOLERANCE_X", "0.15"))

# Face backend selection
FACE_BACKEND = os.getenv("DOORBELL_FACE_BACKEND", "insightface").strip().lower()
FACE_BACKEND_STRICT = os.getenv("DOORBELL_FACE_STRICT", "1").strip().lower() not in ("0", "false", "no")
INSIGHTFACE_DET_MODEL_PATH = os.getenv(
    "DOORBELL_INSIGHTFACE_DET_MODEL",
    os.path.join(MODEL_DIR, "scrfd_10g_bnkps.onnx"),
)
INSIGHTFACE_REC_MODEL_PATH = os.getenv(
    "DOORBELL_INSIGHTFACE_REC_MODEL",
    os.path.join(MODEL_DIR, "w600k_r50.onnx"),
)
try:
    INSIGHTFACE_DET_SIZE = max(160, int(os.getenv("DOORBELL_INSIGHTFACE_DET_SIZE", "640")))
except ValueError:
    INSIGHTFACE_DET_SIZE = 640
try:
    INSIGHTFACE_THRESHOLD = float(os.getenv("DOORBELL_INSIGHTFACE_THRESHOLD", "0.35"))
except ValueError:
    INSIGHTFACE_THRESHOLD = 0.35
try:
    INSIGHTFACE_MARGIN = max(0.0, float(os.getenv("DOORBELL_INSIGHTFACE_MARGIN", "0.08")))
except ValueError:
    INSIGHTFACE_MARGIN = 0.08
FACE_SIZE_MIN_RELATIVE_AREA = float(os.getenv("FACE_SIZE_MIN_RELATIVE_AREA", "0.08"))
FACE_SIZE_MAX_RELATIVE_AREA = float(os.getenv("FACE_SIZE_MAX_RELATIVE_AREA", "0.35"))
FACE_DISTANCE_PROMPT_NEAR_MP3 = os.getenv("DOORBELL_FACE_DISTANCE_PROMPT_NEAR_MP3", os.getenv("FACE_DISTANCE_PROMPT_NEAR_MP3", os.path.join(BASE_DIR, "sounds", "face_closer.mp3")))
FACE_DISTANCE_PROMPT_FAR_MP3 = os.getenv("DOORBELL_FACE_DISTANCE_PROMPT_FAR_MP3", os.getenv("FACE_DISTANCE_PROMPT_FAR_MP3", os.path.join(BASE_DIR, "sounds", "face_farther.mp3")))
FACE_DISTANCE_PROMPT_PLAYER = os.getenv("DOORBELL_FACE_DISTANCE_PROMPT_PLAYER", os.getenv("FACE_DISTANCE_PROMPT_PLAYER", "cvlc --play-and-exit --quiet {path}"))

# =========================================================
# GUI SETTINGS
# =========================================================
GUI_ENABLE_LIVENESS = False
GUI_ENABLE_FACE = os.getenv("DOORBELL_GUI_FACE", "1").strip().lower() not in ("0", "false", "no")
GUI_AUTO_INFER = os.getenv("DOORBELL_GUI_AUTO_INFER", "1").strip().lower() not in ("0", "false", "no")
GUI_THREAD_INFER = os.getenv("DOORBELL_GUI_THREAD_INFER", "0").strip().lower() not in ("0", "false", "no")
try:
    GUI_INFER_TIMEOUT_SEC = max(2.0, float(os.getenv("DOORBELL_GUI_INFER_TIMEOUT_SEC", "8")))
except ValueError:
    GUI_INFER_TIMEOUT_SEC = 8.0

FACE_DISTANCE_PROMPT_ENABLED = os.getenv("DOORBELL_FACE_DISTANCE_PROMPT", "1").strip().lower() not in ("0", "false", "no")
try:
    FACE_DISTANCE_PROMPT_COOLDOWN_SEC = max(0.5, float(os.getenv("DOORBELL_FACE_DISTANCE_PROMPT_COOLDOWN", "3")))
except ValueError:
    FACE_DISTANCE_PROMPT_COOLDOWN_SEC = 3.0
FACE_DISTANCE_PROMPT_CMD = os.getenv("DOORBELL_FACE_DISTANCE_PROMPT_CMD", "")

# =========================================================
# ABOUT TAB ACCESS
# =========================================================
ABOUT_ACCESS_ID = os.getenv("DOORBELL_ABOUT_ID", "admin")
ABOUT_ACCESS_PASSWORD = os.getenv("DOORBELL_ABOUT_PASSWORD", "admin")


MODEL_PATH = os.path.join(MODEL_DIR, "MobileNet-v2_float.tflite")
IMG_SIZE = (224, 224)
RECOGNITION_THRESHOLD = 0.80
try:
    RECOGNITION_MARGIN = max(0.0, float(os.getenv("DOORBELL_RECOGNITION_MARGIN", "0")))
except ValueError:
    RECOGNITION_MARGIN = 0.0
RECOGNITION_SMOOTH_WINDOW = 3
RECOGNITION_STABLE_COUNT = 2
RECOGNITION_STABLE_HOLD_SEC = 1.0
RECOGNITION_STABLE_MIN_SCORE = RECOGNITION_THRESHOLD
N_DETECTION_FRAMES = 3

# =========================================================
# FACE DATABASE
# =========================================================
DB_PATH = os.path.join(BASE_DIR, "face", "known_faces", "face_db.json")


# =====================================================
# ANTI-SPOOF
# =====================================================
LIVENESS_MODEL_PATH = os.path.join(MODEL_DIR, "modelrgb.onnx")

LIVENESS_LAPLACIAN_THRESH = 15
MIN_FACE_MOVEMENT_RATIO = 0.008
MULTI_FRAME_COUNT = 3

# =========================================================
# GPIO
# =========================================================
BUTTON_PIN = 17
MOTION_PIN = 27

# =========================================================
# DOORBELL BUTTON
# =========================================================
RING_ENABLED = os.getenv("DOORBELL_RING_ENABLED", "1").strip().lower() not in ("0", "false", "no")
RING_BUTTON_PIN = int(os.getenv("DOORBELL_RING_BUTTON_PIN", "23"))
RING_BUTTON_PULL_UP = os.getenv("DOORBELL_RING_BUTTON_PULL_UP", "1").strip().lower() not in ("0", "false", "no")
RING_BUTTON_BOUNCE_SEC = float(os.getenv("DOORBELL_RING_BUTTON_BOUNCE_SEC", "0.1"))
RING_SOUND_MP3 = os.getenv(
    "DOORBELL_RING_SOUND_MP3",
    os.path.join(BASE_DIR, "sounds", "tieng_bam_chuong_cua_2_lan_lien_tuc-www_tiengdong_com.mp3"),
)
RING_SOUND_PLAYER = os.getenv("DOORBELL_RING_SOUND_PLAYER", "cvlc --play-and-exit --quiet {path}")
RING_COOLDOWN_SEC = float(os.getenv("DOORBELL_RING_COOLDOWN_SEC", "1.5"))


# =========================================================
# LED
# =========================================================
KNOWN_ALERT_ENABLED = False
LED_PIN = 17
LED_ACTIVE_HIGH = True
LED_OFF_DELAY_SEC = 0.0

# =========================================================
# LCD I2C 16x2
# =========================================================
LCD_ENABLED = os.getenv("DOORBELL_LCD_ENABLED", "1").strip().lower() not in ("0", "false", "no")
LCD_I2C_BUS = int(os.getenv("DOORBELL_LCD_I2C_BUS", "1"))
LCD_I2C_ADDRESS = int(os.getenv("DOORBELL_LCD_I2C_ADDRESS", "0x3f"), 0)
LCD_COLS = int(os.getenv("DOORBELL_LCD_COLS", "16"))
LCD_ROWS = int(os.getenv("DOORBELL_LCD_ROWS", "2"))
LCD_BACKLIGHT = os.getenv("DOORBELL_LCD_BACKLIGHT", "1").strip().lower() not in ("0", "false", "no")
LCD_UPDATE_MIN_INTERVAL_SEC = float(os.getenv("DOORBELL_LCD_UPDATE_MIN_INTERVAL_SEC", "0.2"))


# =========================================================
# SERVO DOOR
# =========================================================
SERVO_PIN = 18
SERVO_OPEN_ANGLE = 90
SERVO_CLOSE_ANGLE = 0
SERVO_OPEN_SEC = 2.0
SERVO_FRAME_WIDTH = 0.02
SERVO_DETACH_AFTER_CLOSE = True
SERVO_DETACH_DELAY_SEC = 0.2
SERVO_DETACH_AFTER_OPEN = True
SERVO_DETACH_OPEN_DELAY_SEC = 0.5
SERVO_USE_PIGPIO = False
SERVO_MIN_ANGLE = 0
SERVO_MAX_ANGLE = 180
SERVO_MIN_PULSE_WIDTH = 0.0005
SERVO_MAX_PULSE_WIDTH = 0.0025




# =========================================================
# DOOR LOGIC
# =========================================================
DOOR_LIGHT_FOLLOW_DOOR = True
DOOR_HOLD_ON_FACE = True
DOOR_CLOSE_DELAY_SEC = 2.0
DOOR_REQUIRE_KNOWN = True
DOOR_REQUIRE_REAL = False




# =========================================================
# DOOR SOUND
# =========================================================
DOOR_OPEN_SOUND_ENABLED = os.getenv("DOORBELL_DOOR_OPEN_SOUND_ENABLED", "1").strip().lower() not in ("0", "false", "no")
DOOR_OPEN_SOUND_MP3 = os.getenv("DOORBELL_DOOR_OPEN_SOUND_MP3", os.path.join(BASE_DIR, "sounds", "tieng_ting_mp3-www_tiengdong_com.mp3"))
DOOR_OPEN_SOUND_PLAYER = os.getenv("DOORBELL_DOOR_OPEN_SOUND_PLAYER", "cvlc --play-and-exit --quiet {path}")
DOOR_CLOSE_SOUND_ENABLED = os.getenv("DOORBELL_DOOR_CLOSE_SOUND_ENABLED", "1").strip().lower() not in ("0", "false", "no")
DOOR_CLOSE_SOUND_MP3 = os.getenv("DOORBELL_DOOR_CLOSE_SOUND_MP3", os.path.join(BASE_DIR, "sounds", "Am_thanh_tieng_Dong_cua-www_tiengdong_com.mp3"))
DOOR_CLOSE_SOUND_PLAYER = os.getenv("DOORBELL_DOOR_CLOSE_SOUND_PLAYER", "cvlc --play-and-exit --quiet {path}")

# =========================================================
# TELEGRAM CONFIG
# =========================================================
# Telegram (set env vars in production)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8255947529:AAEajLKCGTnbDNLjwL6goPUVhxIe3KI1SBE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5832487292")
