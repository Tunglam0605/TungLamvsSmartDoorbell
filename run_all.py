import importlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request


def _venv_site_dir():
    venv = os.getenv("VIRTUAL_ENV")
    base = venv if venv and os.path.isdir(venv) else sys.prefix
    return os.path.join(
        base,
        "lib",
        f"python{sys.version_info.major}.{sys.version_info.minor}",
        "site-packages",
    )


def _force_venv_packages():
    site_dir = _venv_site_dir()
    if not site_dir or not os.path.isdir(site_dir):
        return
    if site_dir not in sys.path:
        sys.path.insert(0, site_dir)

    # Force typing_extensions from venv
    te_path = os.path.join(site_dir, "typing_extensions.py")
    if os.path.isfile(te_path):
        sys.modules.pop("typing_extensions", None)
        spec = importlib.util.spec_from_file_location("typing_extensions", te_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules["typing_extensions"] = module
            return

    # Fallback: normal import after sys.path update
    sys.modules.pop("typing_extensions", None)
    try:
        importlib.import_module("typing_extensions")
    except Exception:
        pass


_force_venv_packages()

from PySide6 import QtWidgets

from gui.qt_utils import apply_theme

from config import API_HOST, API_PORT


def _announce_tunnel_url(url):
    if not url:
        return
    os.environ["PUBLIC_BASE_URL"] = url
    os.environ["DOORBELL_TUNNEL_URL"] = url
    try:
        import config as _config
        _config.PUBLIC_BASE_URL = url
    except Exception:
        pass
    try:
        import server.event_store as _event_store
        _event_store.PUBLIC_BASE_URL = url
    except Exception:
        pass
    _push_firebase_url(url)
    print(f"Tunnel URL: {url} (copy to app)")



_TUNNEL_URL_RE = re.compile(r"https?://[\w.-]+\.trycloudflare\.com")


def _push_firebase_url(url):
    if not url:
        return
    try:
        import config as _config
    except Exception:
        return
    if not getattr(_config, "FIREBASE_RTDB_ENABLE", False):
        return
    base_url = getattr(_config, "FIREBASE_RTDB_URL", "")
    key = getattr(_config, "FIREBASE_RTDB_KEY", "")
    auth = getattr(_config, "FIREBASE_RTDB_AUTH", "")
    if not base_url or not key:
        return
    base_url = base_url.rstrip("/") + "/"
    path = f"{key}.json"
    if auth:
        target = f"{base_url}{path}?{urllib.parse.urlencode({'auth': auth})}"
    else:
        target = f"{base_url}{path}"
    payload = json.dumps(url).encode("utf-8")
    request = urllib.request.Request(
        target,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
        print(f"Firebase RTDB: updated {key}")
    except Exception as exc:
        print(f"Firebase RTDB: update failed: {exc}")


def _start_tunnel():
    enabled = os.getenv("DOORBELL_TUNNEL_ENABLE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    if not enabled:
        return None, None

    target = os.getenv("DOORBELL_TUNNEL_TARGET", f"http://{API_HOST}:{API_PORT}")
    cmd_template = os.getenv(
        "DOORBELL_TUNNEL_CMD",
        "cloudflared tunnel --url {url} --no-autoupdate",
    )
    try:
        cmd = cmd_template.format(url=target)
    except Exception:
        cmd = f"{cmd_template} {target}"

    args = shlex.split(cmd)
    if not args:
        print("Tunnel: command empty, skip")
        return None, None

    exe = args[0]
    if shutil.which(exe) is None and not os.path.isfile(exe):
        print(
            f"Tunnel: '{exe}' not found. Install cloudflared or set DOORBELL_TUNNEL_CMD."
        )
        return None, None

    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        print(f"Tunnel: start failed: {exc}")
        return None, None

    url_holder = {"url": None, "printed": False}

    def _reader():
        if proc.stdout is None:
            return
        for line in proc.stdout:
            if not line:
                continue
            sys.stdout.write("[tunnel] " + line)
            sys.stdout.flush()
            match = _TUNNEL_URL_RE.search(line)
            if match and not url_holder["url"]:
                url_holder["url"] = match.group(0)
                if not url_holder["printed"]:
                    _announce_tunnel_url(url_holder["url"])
                    url_holder["printed"] = True

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    timeout_raw = os.getenv("DOORBELL_TUNNEL_TIMEOUT_SEC", "10")
    try:
        timeout_sec = max(1.0, float(timeout_raw))
    except ValueError:
        timeout_sec = 10.0

    start = time.time()
    while time.time() - start < timeout_sec:
        if url_holder["url"]:
            break
        if proc.poll() is not None:
            break
        time.sleep(0.1)

    return proc, url_holder


from gui.app_window import AppWindow
from server.control import set_door_controller


def _start_api():
    try:
        from server.app import app as api_app
    except Exception as exc:
        raise RuntimeError(f"API import failed: {exc}") from exc

    try:
        import uvicorn
    except Exception as exc:
        raise RuntimeError(f"uvicorn not available: {exc}") from exc

    config = uvicorn.Config(
        api_app,
        host=API_HOST,
        port=API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def main():
    try:
        import config as _config
        base_url = (
            os.getenv("DOORBELL_TUNNEL_URL")
            or os.getenv("PUBLIC_BASE_URL")
            or _config.PUBLIC_BASE_URL
        )
    except Exception:
        base_url = os.getenv("DOORBELL_TUNNEL_URL") or os.getenv("PUBLIC_BASE_URL")
    _push_firebase_url(base_url)

    tunnel_proc, tunnel_info = _start_tunnel()
    if tunnel_info is not None:
        tunnel_url = tunnel_info.get("url")
        if tunnel_url and not tunnel_info.get("printed"):
            _announce_tunnel_url(tunnel_url)
            tunnel_info["printed"] = True
    server, thread = _start_api()

    qt_app = QtWidgets.QApplication(sys.argv)
    apply_theme(qt_app)
    win = AppWindow()
    set_door_controller(win.live_tab._door)

    def _shutdown():
        win.shutdown()
        if server is not None:
            server.should_exit = True
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        if tunnel_proc is not None:
            try:
                tunnel_proc.terminate()
            except Exception:
                pass

    qt_app.aboutToQuit.connect(_shutdown)
    win.show()
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
