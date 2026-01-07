import os
import threading
import time
import shlex
import shutil
import subprocess

from gui.alert import LightController
from utils.lcd_i2c import get_lcd_display

try:
    import config as _config
except Exception:
    _config = None

CONFIG_SERVO_PIN = getattr(_config, "SERVO_PIN", 0) if _config else 0
CONFIG_SERVO_OPEN_ANGLE = getattr(_config, "SERVO_OPEN_ANGLE", 90) if _config else 90
CONFIG_SERVO_CLOSE_ANGLE = getattr(_config, "SERVO_CLOSE_ANGLE", 0) if _config else 0
CONFIG_SERVO_OPEN_SEC = getattr(_config, "SERVO_OPEN_SEC", 2.0) if _config else 2.0
CONFIG_SERVO_FRAME_WIDTH = (
    getattr(_config, "SERVO_FRAME_WIDTH", 0.02) if _config else 0.02
)
CONFIG_SERVO_DETACH_AFTER_OPEN = (
    getattr(_config, "SERVO_DETACH_AFTER_OPEN", True) if _config else True
)
CONFIG_SERVO_DETACH_OPEN_DELAY_SEC = (
    getattr(_config, "SERVO_DETACH_OPEN_DELAY_SEC", 0.5) if _config else 0.5
)
CONFIG_SERVO_DETACH_AFTER_CLOSE = (
    getattr(_config, "SERVO_DETACH_AFTER_CLOSE", True) if _config else True
)
CONFIG_SERVO_DETACH_DELAY_SEC = (
    getattr(_config, "SERVO_DETACH_DELAY_SEC", 0.2) if _config else 0.2
)
CONFIG_SERVO_USE_PIGPIO = (
    getattr(_config, "SERVO_USE_PIGPIO", False) if _config else False
)
CONFIG_LED_PIN = getattr(_config, "LED_PIN", 0) if _config else 0
CONFIG_LED_ACTIVE_HIGH = getattr(_config, "LED_ACTIVE_HIGH", True) if _config else True
CONFIG_DOOR_LIGHT_FOLLOW_DOOR = (
    getattr(_config, "DOOR_LIGHT_FOLLOW_DOOR", True) if _config else True
)
CONFIG_DOOR_HOLD_ON_FACE = (
    getattr(_config, "DOOR_HOLD_ON_FACE", True) if _config else True
)
CONFIG_DOOR_CLOSE_DELAY_SEC = (
    getattr(_config, "DOOR_CLOSE_DELAY_SEC", 2.0) if _config else 2.0
)
CONFIG_DOOR_REQUIRE_KNOWN = (
    getattr(_config, "DOOR_REQUIRE_KNOWN", False) if _config else False
)
CONFIG_DOOR_REQUIRE_REAL = (
    getattr(_config, "DOOR_REQUIRE_REAL", False) if _config else False
)
CONFIG_SERVO_MIN_ANGLE = getattr(_config, "SERVO_MIN_ANGLE", 0) if _config else 0
CONFIG_SERVO_MAX_ANGLE = getattr(_config, "SERVO_MAX_ANGLE", 180) if _config else 180
CONFIG_SERVO_MIN_PULSE_WIDTH = (
    getattr(_config, "SERVO_MIN_PULSE_WIDTH", 0.0005) if _config else 0.0005
)
CONFIG_SERVO_MAX_PULSE_WIDTH = (
    getattr(_config, "SERVO_MAX_PULSE_WIDTH", 0.0025) if _config else 0.0025
)
CONFIG_DOOR_OPEN_SOUND_ENABLED = (
    getattr(_config, "DOOR_OPEN_SOUND_ENABLED", True) if _config else True
)
CONFIG_DOOR_OPEN_SOUND_MP3 = (
    getattr(_config, "DOOR_OPEN_SOUND_MP3", "") if _config else ""
)
CONFIG_DOOR_OPEN_SOUND_PLAYER = (
    getattr(_config, "DOOR_OPEN_SOUND_PLAYER", "cvlc --play-and-exit --quiet {path}")
    if _config
    else "cvlc --play-and-exit --quiet {path}"
)
CONFIG_DOOR_CLOSE_SOUND_ENABLED = (
    getattr(_config, "DOOR_CLOSE_SOUND_ENABLED", True) if _config else True
)
CONFIG_DOOR_CLOSE_SOUND_MP3 = (
    getattr(_config, "DOOR_CLOSE_SOUND_MP3", "") if _config else ""
)
CONFIG_DOOR_CLOSE_SOUND_PLAYER = (
    getattr(_config, "DOOR_CLOSE_SOUND_PLAYER", "cvlc --play-and-exit --quiet {path}")
    if _config
    else "cvlc --play-and-exit --quiet {path}"
)


def _env_bool(key, default=False):
    raw = os.getenv(key)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _env_int(key, default=0):
    raw = os.getenv(key)
    if raw is None:
        return int(default)
    try:
        return int(str(raw).strip())
    except ValueError:
        return int(default)


def _env_float(key, default=0.0):
    raw = os.getenv(key)
    if raw is None:
        return float(default)
    try:
        return float(str(raw).strip())
    except ValueError:
        return float(default)


def _env_str(key, default=""):
    raw = os.getenv(key)
    if raw is None:
        return str(default)
    return str(raw)


class DoorController:
    def __init__(self):
        self.pin = _env_int("DOORBELL_SERVO_PIN", CONFIG_SERVO_PIN)
        self.open_angle = _env_float(
            "DOORBELL_SERVO_OPEN_ANGLE",
            CONFIG_SERVO_OPEN_ANGLE,
        )
        self.close_angle = _env_float(
            "DOORBELL_SERVO_CLOSE_ANGLE",
            CONFIG_SERVO_CLOSE_ANGLE,
        )
        self.open_sec = _env_float("DOORBELL_SERVO_OPEN_SEC", CONFIG_SERVO_OPEN_SEC)
        self.frame_width = _env_float(
            "DOORBELL_SERVO_FRAME_WIDTH",
            CONFIG_SERVO_FRAME_WIDTH,
        )
        self.detach_after_open = _env_bool(
            "DOORBELL_SERVO_DETACH_AFTER_OPEN",
            CONFIG_SERVO_DETACH_AFTER_OPEN,
        )
        self.detach_open_delay_sec = _env_float(
            "DOORBELL_SERVO_DETACH_OPEN_DELAY_SEC",
            CONFIG_SERVO_DETACH_OPEN_DELAY_SEC,
        )
        self.detach_after_close = _env_bool(
            "DOORBELL_SERVO_DETACH_AFTER_CLOSE",
            CONFIG_SERVO_DETACH_AFTER_CLOSE,
        )
        self.detach_delay_sec = _env_float(
            "DOORBELL_SERVO_DETACH_DELAY_SEC",
            CONFIG_SERVO_DETACH_DELAY_SEC,
        )
        self.use_pigpio = _env_bool("DOORBELL_SERVO_USE_PIGPIO", CONFIG_SERVO_USE_PIGPIO)

        self.hold_on_face = _env_bool(
            "DOORBELL_DOOR_HOLD_ON_FACE",
            CONFIG_DOOR_HOLD_ON_FACE,
        )
        self.close_delay_sec = _env_float(
            "DOORBELL_DOOR_CLOSE_DELAY_SEC",
            CONFIG_DOOR_CLOSE_DELAY_SEC,
        )
        self.require_known = _env_bool(
            "DOORBELL_DOOR_REQUIRE_KNOWN",
            CONFIG_DOOR_REQUIRE_KNOWN,
        )
        self.require_real = _env_bool(
            "DOORBELL_DOOR_REQUIRE_REAL",
            CONFIG_DOOR_REQUIRE_REAL,
        )

        self.light_follow = _env_bool(
            "DOORBELL_LIGHT_FOLLOW_DOOR",
            CONFIG_DOOR_LIGHT_FOLLOW_DOOR,
        )
        light_pin = _env_int("DOORBELL_LIGHT_PIN", CONFIG_LED_PIN)
        light_active_high = _env_bool(
            "DOORBELL_LIGHT_ACTIVE_HIGH",
            CONFIG_LED_ACTIVE_HIGH,
        )
        self.light = LightController(
            light_pin,
            active_high=light_active_high,
            on_sec=0.0,
        )
        self._lcd = get_lcd_display()
        self.open_sound_enabled = _env_bool(
            "DOORBELL_DOOR_OPEN_SOUND_ENABLED",
            CONFIG_DOOR_OPEN_SOUND_ENABLED,
        )
        self.open_sound_mp3 = _env_str(
            "DOORBELL_DOOR_OPEN_SOUND_MP3",
            CONFIG_DOOR_OPEN_SOUND_MP3,
        )
        self.open_sound_player = _env_str(
            "DOORBELL_DOOR_OPEN_SOUND_PLAYER",
            CONFIG_DOOR_OPEN_SOUND_PLAYER,
        )
        self.close_sound_enabled = _env_bool(
            "DOORBELL_DOOR_CLOSE_SOUND_ENABLED",
            CONFIG_DOOR_CLOSE_SOUND_ENABLED,
        )
        self.close_sound_mp3 = _env_str(
            "DOORBELL_DOOR_CLOSE_SOUND_MP3",
            CONFIG_DOOR_CLOSE_SOUND_MP3,
        )
        self.close_sound_player = _env_str(
            "DOORBELL_DOOR_CLOSE_SOUND_PLAYER",
            CONFIG_DOOR_CLOSE_SOUND_PLAYER,
        )



        self.min_angle = _env_float("DOORBELL_SERVO_MIN_ANGLE", CONFIG_SERVO_MIN_ANGLE)
        self.max_angle = _env_float("DOORBELL_SERVO_MAX_ANGLE", CONFIG_SERVO_MAX_ANGLE)
        self.min_pulse = _env_float(
            "DOORBELL_SERVO_MIN_PULSE_WIDTH",
            CONFIG_SERVO_MIN_PULSE_WIDTH,
        )
        self.max_pulse = _env_float(
            "DOORBELL_SERVO_MAX_PULSE_WIDTH",
            CONFIG_SERVO_MAX_PULSE_WIDTH,
        )

        self.available = False
        self._error = None
        self._servo = None
        self._timer = None
        self._detach_timer = None
        self._lock = threading.Lock()
        self._last_seen_ts = 0.0
        self._is_open = False
        self._light_on = False

        if self.pin <= 0:
            self._error = "Servo pin not set"
            return

        try:
            from gpiozero import AngularServo
        except Exception as exc:
            self._error = f"gpiozero unavailable: {exc}"
            return

        pin_factory = None
        if self.use_pigpio:
            try:
                from gpiozero.pins.pigpio import PiGPIOFactory

                pin_factory = PiGPIOFactory()
            except Exception:
                pin_factory = None

        try:
            kwargs = dict(
                min_angle=self.min_angle,
                max_angle=self.max_angle,
                min_pulse_width=self.min_pulse,
                max_pulse_width=self.max_pulse,
                frame_width=self.frame_width,
            )
            if pin_factory is not None:
                kwargs["pin_factory"] = pin_factory
            self._servo = AngularServo(self.pin, **kwargs)
            self.available = True
        except Exception as exc:
            self._error = f"servo init failed: {exc}"

    def _play_open_sound(self):
        if not self.open_sound_enabled:
            return False
        path = str(self.open_sound_mp3).strip()
        if not path or not os.path.isfile(path):
            return False
        cmd = str(self.open_sound_player).strip()
        args = None
        if cmd:
            try:
                raw_args = shlex.split(cmd.format(path=path))
            except Exception:
                raw_args = shlex.split(cmd) + [path]
            if raw_args:
                exe = raw_args[0]
                if shutil.which(exe):
                    args = raw_args
        if not args:
            if shutil.which("mpg123"):
                args = ["mpg123", "-q", path]
            elif shutil.which("ffplay"):
                args = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
            elif shutil.which("omxplayer"):
                args = ["omxplayer", "-o", "local", path]
            elif shutil.which("mpv"):
                args = ["mpv", "--no-video", "--really-quiet", path]
            elif shutil.which("cvlc"):
                args = ["cvlc", "--play-and-exit", "--quiet", path]
        if not args:
            return False
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False


    def _play_close_sound(self):
        if not self.close_sound_enabled:
            return False
        path = str(self.close_sound_mp3).strip()
        if not path or not os.path.isfile(path):
            return False
        cmd = str(self.close_sound_player).strip()
        args = None
        if cmd:
            try:
                raw_args = shlex.split(cmd.format(path=path))
            except Exception:
                raw_args = shlex.split(cmd) + [path]
            if raw_args:
                exe = raw_args[0]
                if shutil.which(exe):
                    args = raw_args
        if not args:
            if shutil.which("mpg123"):
                args = ["mpg123", "-q", path]
            elif shutil.which("ffplay"):
                args = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
            elif shutil.which("omxplayer"):
                args = ["omxplayer", "-o", "local", path]
            elif shutil.which("mpv"):
                args = ["mpv", "--no-video", "--really-quiet", path]
            elif shutil.which("cvlc"):
                args = ["cvlc", "--play-and-exit", "--quiet", path]
        if not args:
            return False
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False


    def _cancel_detach_timer(self):
        if self._detach_timer is not None:
            try:
                self._detach_timer.cancel()
            except Exception:
                pass
            self._detach_timer = None

    def _cancel_timer(self):
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None

    def _schedule_detach_after_open(self):
        if not self.detach_after_open:
            return
        delay = max(0.0, float(self.detach_open_delay_sec))
        self._cancel_detach_timer()

        def _do_detach():
            try:
                if self._servo is not None and self._is_open:
                    self._servo.detach()
            except Exception:
                pass

        if delay == 0.0:
            _do_detach()
        else:
            self._detach_timer = threading.Timer(delay, _do_detach)
            self._detach_timer.daemon = True
            self._detach_timer.start()

    def _schedule_detach_after_close(self):
        if not self.detach_after_close:
            return
        delay = max(0.0, float(self.detach_delay_sec))
        self._cancel_detach_timer()

        def _do_detach():
            try:
                if self._servo is not None:
                    self._servo.detach()
            except Exception:
                pass

        if delay == 0.0:
            _do_detach()
        else:
            self._detach_timer = threading.Timer(delay, _do_detach)
            self._detach_timer.daemon = True
            self._detach_timer.start()

    def _set_light(self, on):
        if not self.light_follow or self.light is None:
            return False
        ok = self.light.set_state(bool(on))
        if ok:
            self._light_on = bool(on)
        return ok

    def set_light_state(self, on):
        if self.light is None:
            return False
        ok = self.light.set_state(bool(on))
        if ok:
            self._light_on = bool(on)
        return ok

    def _update_lcd_state(self, is_open):
        lcd = getattr(self, "_lcd", None)
        if lcd is None:
            return False
        try:
            return bool(lcd.set_status(door_open=is_open))
        except Exception:
            return False

    def _set_angle(self, angle):
        if self._servo is None:
            return False
        try:
            self._servo.angle = float(angle)
            return True
        except Exception:
            return False

    def _open_hold(self):
        self._cancel_detach_timer()
        self._cancel_timer()
        if not self._set_angle(self.open_angle):
            return False
        self._is_open = True
        self._set_light(True)
        self._update_lcd_state(True)
        self._schedule_detach_after_open()
        return True

    def open_and_close(self):
        if not self.available:
            return False, self._error or "Servo unavailable"
        with self._lock:
            if self.hold_on_face:
                self._last_seen_ts = time.time()
                if not self._open_hold():
                    return False, "Failed to set open angle"
                return True, "Door opened"
            self._cancel_detach_timer()
            self._cancel_timer()
            if not self._set_angle(self.open_angle):
                return False, "Failed to set open angle"
            self._is_open = True
            self._set_light(True)
            self._update_lcd_state(True)
            self._schedule_detach_after_open()
            if self.open_sec and self.open_sec > 0:
                self._timer = threading.Timer(self.open_sec, self.close)
                self._timer.daemon = True
                self._timer.start()
        return True, "Door opened"

    def close(self):
        with self._lock:
            was_open = bool(self._is_open)
            self._cancel_detach_timer()
            self._cancel_timer()
            self._set_angle(self.close_angle)
            self._is_open = False
            self._set_light(False)
            self._update_lcd_state(False)
            self._schedule_detach_after_close()
        if was_open:
            self._play_close_sound()

    def handle_result(self, result):
        if not self.available or not self.hold_on_face or not result:
            return False

        present = bool(result.get("has_face"))
        if present and self.require_known:
            present = bool(result.get("id") and result.get("name"))
            if present and result.get("stabilizing") is True:
                present = False
        if present and self.require_real:
            present = result.get("is_real") is True

        now = time.time()
        if present:
            self._last_seen_ts = now
            if not self._is_open:
                with self._lock:
                    opened = self._open_hold()
                if opened:
                    self._play_open_sound()
            return True

        if self._is_open:
            if now - self._last_seen_ts >= float(self.close_delay_sec):
                self.close()
        return False

    def shutdown(self):
        with self._lock:
            self._cancel_detach_timer()
            self._cancel_timer()
            self._set_light(False)
            if self._servo is not None:
                try:
                    self._servo.detach()
                except Exception:
                    pass
