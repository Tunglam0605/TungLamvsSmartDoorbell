import os
import threading
import time

try:
    import config as _config
except Exception:
    _config = None


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
        return int(str(raw).strip(), 0)
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


def _get_cfg(name, default):
    if _config is None:
        return default
    return getattr(_config, name, default)


CONFIG_LCD_ENABLED = _get_cfg("LCD_ENABLED", True)
CONFIG_LCD_I2C_BUS = _get_cfg("LCD_I2C_BUS", 1)
CONFIG_LCD_I2C_ADDRESS = _get_cfg("LCD_I2C_ADDRESS", 0x3f)
CONFIG_LCD_COLS = _get_cfg("LCD_COLS", 16)
CONFIG_LCD_ROWS = _get_cfg("LCD_ROWS", 2)
CONFIG_LCD_BACKLIGHT = _get_cfg("LCD_BACKLIGHT", True)
CONFIG_LCD_UPDATE_MIN_INTERVAL_SEC = _get_cfg("LCD_UPDATE_MIN_INTERVAL_SEC", 0.2)


class _BaseDriver:
    def display_lines(self, line1, line2):
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError

    def close(self):
        pass


class _RplcdDriver(_BaseDriver):
    def __init__(self, lcd):
        self.lcd = lcd

    def display_lines(self, line1, line2):
        try:
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1)
            if self.lcd.rows > 1:
                self.lcd.cursor_pos = (1, 0)
                self.lcd.write_string(line2)
        except Exception:
            return

    def clear(self):
        try:
            self.lcd.clear()
        except Exception:
            return

    def close(self):
        try:
            self.lcd.close(clear=True)
        except Exception:
            return


class _PCF8574Driver(_BaseDriver):
    # Common PCF8574 backpack mapping:
    # P0=RS, P1=RW, P2=EN, P3=BACKLIGHT, P4=D4, P5=D5, P6=D6, P7=D7
    RS = 0x01
    RW = 0x02
    EN = 0x04
    BACKLIGHT = 0x08

    def __init__(self, bus, address, cols, rows, backlight=True):
        self.bus = bus
        self.address = address
        self.cols = cols
        self.rows = rows
        self.backlight = bool(backlight)
        self._backlight_mask = self.BACKLIGHT if self.backlight else 0x00
        self._init_lcd()

    def _write_byte(self, data):
        self.bus.write_byte(self.address, data | self._backlight_mask)

    def _pulse_enable(self, data):
        self._write_byte(data | self.EN)
        time.sleep(0.0005)
        self._write_byte(data & ~self.EN)
        time.sleep(0.0001)

    def _write4bits(self, data):
        self._write_byte(data)
        self._pulse_enable(data)

    def _command(self, cmd):
        self._write4bits(cmd & 0xF0)
        self._write4bits((cmd << 4) & 0xF0)

    def _write_char(self, char):
        val = ord(char)
        self._write4bits((val & 0xF0) | self.RS)
        self._write4bits(((val << 4) & 0xF0) | self.RS)

    def _init_lcd(self):
        time.sleep(0.05)
        self._write4bits(0x30)
        time.sleep(0.005)
        self._write4bits(0x30)
        time.sleep(0.001)
        self._write4bits(0x30)
        time.sleep(0.001)
        self._write4bits(0x20)
        time.sleep(0.001)
        self._command(0x28)  # 4-bit, 2 lines, 5x8
        self._command(0x0C)  # display on, cursor off
        self._command(0x06)  # entry mode
        self.clear()

    def _set_cursor(self, col, row):
        row_offsets = [0x00, 0x40, 0x14, 0x54]
        row = max(0, min(row, len(row_offsets) - 1))
        col = max(0, min(col, self.cols - 1))
        self._command(0x80 | (col + row_offsets[row]))

    def display_lines(self, line1, line2):
        self._set_cursor(0, 0)
        for ch in line1:
            self._write_char(ch)
        if self.rows > 1:
            self._set_cursor(0, 1)
            for ch in line2:
                self._write_char(ch)

    def clear(self):
        self._command(0x01)
        time.sleep(0.002)

    def close(self):
        try:
            self.clear()
        except Exception:
            return


class LCDDisplay:
    def __init__(self):
        self.enabled = _env_bool("DOORBELL_LCD_ENABLED", CONFIG_LCD_ENABLED)
        self.bus = _env_int("DOORBELL_LCD_I2C_BUS", CONFIG_LCD_I2C_BUS)
        self.address = _env_int("DOORBELL_LCD_I2C_ADDRESS", CONFIG_LCD_I2C_ADDRESS)
        self.cols = _env_int("DOORBELL_LCD_COLS", CONFIG_LCD_COLS)
        self.rows = _env_int("DOORBELL_LCD_ROWS", CONFIG_LCD_ROWS)
        self.backlight = _env_bool("DOORBELL_LCD_BACKLIGHT", CONFIG_LCD_BACKLIGHT)
        self.min_interval = _env_float(
            "DOORBELL_LCD_UPDATE_MIN_INTERVAL_SEC",
            CONFIG_LCD_UPDATE_MIN_INTERVAL_SEC,
        )

        self.available = False
        self._driver = None
        self._lock = threading.Lock()
        self._last_lines = ("", "")
        self._last_update_ts = 0.0
        self._door_open = False
        self._person_type = "NONE"
        self._person_name = ""

        if self.enabled:
            self._init_driver()

    def _init_driver(self):
        # Try RPLCD first
        try:
            from RPLCD.i2c import CharLCD

            lcd = CharLCD(
                "PCF8574",
                address=self.address,
                port=self.bus,
                cols=self.cols,
                rows=self.rows,
                charmap="A00",
                auto_linebreaks=False,
                backlight_enabled=self.backlight,
            )
            self._driver = _RplcdDriver(lcd)
            self.available = True
            return
        except Exception:
            pass

        # Fallback to smbus / smbus2
        bus = None
        try:
            from smbus2 import SMBus

            bus = SMBus(self.bus)
        except Exception:
            try:
                from smbus import SMBus

                bus = SMBus(self.bus)
            except Exception:
                bus = None

        if bus is None:
            self.available = False
            return

        try:
            self._driver = _PCF8574Driver(
                bus,
                address=self.address,
                cols=self.cols,
                rows=self.rows,
                backlight=self.backlight,
            )
            self.available = True
        except Exception:
            self._driver = None
            self.available = False

    def _format_line(self, text):
        clean = (text or "")
        if len(clean) > self.cols:
            clean = clean[: self.cols]
        return clean.ljust(self.cols)

    def _compose_lines(self):
        door_text = "OPEN" if self._door_open else "CLOSED"
        line1 = f"DOOR: {door_text}"

        person_type = self._person_type or "NONE"
        if person_type == "KNOWN":
            name = (self._person_name or "").strip() or "USER"
            line2 = f"KNOWN: {name}"
        elif person_type == "UNKNOWN":
            line2 = "UNKNOWN"
        elif person_type == "SPOOF":
            line2 = "SPOOF"
        elif person_type == "MOVE_CLOSE":
            line2 = "MOVE CLOSER"
        elif person_type == "MOVE_FAR":
            line2 = "MOVE FAR"
        else:
            line2 = "NO FACE"

        return self._format_line(line1), self._format_line(line2)

    def set_status(self, door_open=None, person_type=None, person_name=None):
        if not self.available or self._driver is None:
            return False
        with self._lock:
            if door_open is not None:
                self._door_open = bool(door_open)
            if person_type is not None:
                self._person_type = str(person_type)
            if person_name is not None:
                self._person_name = str(person_name)

            now = time.time()
            if self.min_interval and now - self._last_update_ts < self.min_interval:
                return False

            line1, line2 = self._compose_lines()
            if (line1, line2) == self._last_lines:
                return False

            try:
                self._driver.display_lines(line1, line2)
                self._last_lines = (line1, line2)
                self._last_update_ts = now
                return True
            except Exception:
                return False

    def clear(self):
        if not self.available or self._driver is None:
            return False
        try:
            self._driver.clear()
            self._last_lines = ("", "")
            return True
        except Exception:
            return False

    def close(self):
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:
                return


_LCD_INSTANCE = None


def get_lcd_display():
    global _LCD_INSTANCE
    if _LCD_INSTANCE is None:
        _LCD_INSTANCE = LCDDisplay()
    return _LCD_INSTANCE
