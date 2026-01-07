import os
import time

try:
    import config as _config
except Exception:
    _config = None

from gui.alert import SoundPlayer

CONFIG_RING_ENABLED = getattr(_config, "RING_ENABLED", True) if _config else True
CONFIG_RING_BUTTON_PIN = getattr(_config, "RING_BUTTON_PIN", 23) if _config else 23
CONFIG_RING_BUTTON_PULL_UP = (
    getattr(_config, "RING_BUTTON_PULL_UP", True) if _config else True
)
CONFIG_RING_BUTTON_BOUNCE_SEC = (
    getattr(_config, "RING_BUTTON_BOUNCE_SEC", 0.1) if _config else 0.1
)
CONFIG_RING_SOUND_MP3 = getattr(_config, "RING_SOUND_MP3", "") if _config else ""
CONFIG_RING_SOUND_PLAYER = (
    getattr(_config, "RING_SOUND_PLAYER", "") if _config else ""
)
CONFIG_RING_COOLDOWN_SEC = (
    getattr(_config, "RING_COOLDOWN_SEC", 1.5) if _config else 1.5
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
    return str(raw).strip()


class DoorbellRingButton:
    def __init__(self, on_press=None):
        self.enabled = _env_bool("DOORBELL_RING_ENABLED", CONFIG_RING_ENABLED)
        self.pin = _env_int("DOORBELL_RING_BUTTON_PIN", CONFIG_RING_BUTTON_PIN)
        self.pull_up = _env_bool("DOORBELL_RING_BUTTON_PULL_UP", CONFIG_RING_BUTTON_PULL_UP)
        self.bounce_sec = _env_float(
            "DOORBELL_RING_BUTTON_BOUNCE_SEC",
            CONFIG_RING_BUTTON_BOUNCE_SEC,
        )
        self.cooldown_sec = _env_float("DOORBELL_RING_COOLDOWN_SEC", CONFIG_RING_COOLDOWN_SEC)
        self.sound_mp3 = _env_str("DOORBELL_RING_SOUND_MP3", CONFIG_RING_SOUND_MP3)
        self.sound_player = _env_str(
            "DOORBELL_RING_SOUND_PLAYER",
            CONFIG_RING_SOUND_PLAYER,
        )
        self.sound = SoundPlayer(self.sound_mp3, cmd=self.sound_player)
        self._on_press_cb = on_press
        self._last_ring_ts = 0.0
        self.available = False
        self._error = None
        self._button = None

        if not self.enabled or self.pin <= 0:
            return

        try:
            from gpiozero import Button

            self._button = Button(
                self.pin,
                pull_up=self.pull_up,
                bounce_time=self.bounce_sec,
            )
            self._button.when_pressed = self._on_pressed
            self.available = True
        except Exception as exc:
            self._error = f"button init failed: {exc}"
            self._button = None

    def _on_pressed(self):
        self.ring()

    def ring(self):
        if not self.enabled:
            return False
        now = time.time()
        if self.cooldown_sec > 0 and now - self._last_ring_ts < self.cooldown_sec:
            return False
        ok = self.sound.play() if self.sound else False
        self._last_ring_ts = now
        if self._on_press_cb is not None:
            try:
                self._on_press_cb()
            except Exception:
                pass
        return ok

    def close(self):
        if self._button is not None:
            try:
                self._button.close()
            except Exception:
                pass
