import os
import shlex
import shutil
import subprocess
import threading
import time

try:
    import config as _config
except Exception:
    _config = None

CONFIG_LED_PIN = getattr(_config, "LED_PIN", 0) if _config else 0
CONFIG_LED_ACTIVE_HIGH = getattr(_config, "LED_ACTIVE_HIGH", True) if _config else True
CONFIG_LED_OFF_DELAY_SEC = (
    getattr(_config, "LED_OFF_DELAY_SEC", 0.0) if _config else 0.0
)

CONFIG_KNOWN_ALERT_ENABLED = (
    getattr(_config, "KNOWN_ALERT_ENABLED", False) if _config else False
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


class LightController:
    _shared_devices = {}
    def __init__(self, pin, active_high=True, on_sec=2.0):
        self.pin = int(pin) if pin else 0
        self.active_high = bool(active_high)
        self.on_sec = float(on_sec) if on_sec is not None else 0.0
        self._device = None
        self._off_timer = None
        self._state = False
        if self.pin > 0:
            key = (self.pin, self.active_high)
            if key in LightController._shared_devices:
                self._device = LightController._shared_devices[key]
            else:
                try:
                    from gpiozero import LED

                    self._device = LED(self.pin, active_high=self.active_high)
                    LightController._shared_devices[key] = self._device
                except Exception:
                    self._device = None

    def _cancel_timer(self):
        if self._off_timer is not None:
            try:
                self._off_timer.cancel()
            except Exception:
                pass
            self._off_timer = None

    def set_state(self, on):
        if self._device is None:
            return False
        try:
            self._cancel_timer()
            if on:
                self._device.on()
                self._state = True
            else:
                self._device.off()
                self._state = False
            return True
        except Exception:
            return False

    def trigger(self):
        if self._device is None:
            return False
        try:
            self._cancel_timer()
            self._device.on()
            self._state = True
            if self.on_sec and self.on_sec > 0:
                self._off_timer = threading.Timer(self.on_sec, self._device.off)
                self._off_timer.daemon = True
                self._off_timer.start()
            return True
        except Exception:
            return False

    def close(self):
        self._cancel_timer()
        if self._device is not None:
            try:
                self._device.off()
            except Exception:
                pass


class SoundPlayer:
    def __init__(self, path, cmd=""):
        self.path = path
        self.cmd = cmd
        self._resolved_cmd = None
        self._enabled = False

        if self.path and os.path.isfile(self.path):
            if self.cmd:
                self._resolved_cmd = self.cmd
                self._enabled = True
            else:
                for candidate in ("aplay", "paplay", "omxplayer"):
                    if shutil.which(candidate):
                        self._resolved_cmd = candidate
                        self._enabled = True
                        break

    def play(self):
        if not self._enabled or not self._resolved_cmd:
            return False
        try:
            if "{path}" in self._resolved_cmd:
                args = shlex.split(self._resolved_cmd.format(path=self.path))
            else:
                args = [self._resolved_cmd, self.path]
            subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False


class KnownPersonAlert:
    def __init__(self):
        self.enabled = _env_bool("DOORBELL_KNOWN_ALERT", CONFIG_KNOWN_ALERT_ENABLED)
        self.cooldown_sec = _env_float("DOORBELL_KNOWN_ALERT_COOLDOWN_SEC", 5.0)
        self.require_real = _env_bool("DOORBELL_KNOWN_REQUIRE_REAL", False)
        self.hold_on_known = _env_bool("DOORBELL_LIGHT_HOLD_ON_KNOWN", True)
        self.off_delay_sec = _env_float(
            "DOORBELL_LIGHT_OFF_DELAY_SEC",
            CONFIG_LED_OFF_DELAY_SEC,
        )

        light_pin = _env_int("DOORBELL_LIGHT_PIN", CONFIG_LED_PIN)
        light_active_high = _env_bool(
            "DOORBELL_LIGHT_ACTIVE_HIGH",
            CONFIG_LED_ACTIVE_HIGH,
        )
        light_on_sec = _env_float("DOORBELL_LIGHT_ON_SEC", 2.0)
        self.light = LightController(
            light_pin,
            active_high=light_active_high,
            on_sec=light_on_sec,
        )

        sound_path = _env_str("DOORBELL_SOUND_PATH", "")
        sound_cmd = _env_str("DOORBELL_SOUND_CMD", "")
        self.sound = SoundPlayer(sound_path, cmd=sound_cmd)

        self._last_seen_ts = 0.0
        self._last_sound_ts = 0.0
        self._light_on = False

    def _play_sound(self, now):
        if self.sound is None:
            return False
        if self.cooldown_sec > 0 and now - self._last_sound_ts < self.cooldown_sec:
            return False
        if self.sound.play():
            self._last_sound_ts = now
            return True
        return False

    def handle_result(self, result):
        if not self.enabled or not result:
            return False

        rid = result.get("id")
        name = result.get("name")
        score = result.get("score")
        known = bool(rid and name and score is not None)

        if self.require_real:
            is_real = result.get("is_real")
            if is_real is not True:
                known = False

        now = time.time()

        if known:
            self._last_seen_ts = now
            if self.hold_on_known:
                if not self._light_on:
                    self._light_on = self.light.set_state(True)
                    self._play_sound(now)
                return True
            self._play_sound(now)
            return self.light.trigger()

        if self.hold_on_known and self._light_on:
            if self.off_delay_sec > 0 and now - self._last_seen_ts < self.off_delay_sec:
                return False
            self.light.set_state(False)
            self._light_on = False
        return False

    def close(self):
        if self.light is not None:
            self.light.close()
