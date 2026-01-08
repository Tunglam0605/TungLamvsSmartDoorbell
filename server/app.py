from datetime import datetime
import importlib.util
import os
import sys
from typing import List, Optional


def _force_typing_extensions():
    venv = os.getenv("VIRTUAL_ENV")
    base = venv if venv and os.path.isdir(venv) else sys.prefix
    site_dir = os.path.join(
        base,
        "lib",
        f"python{sys.version_info.major}.{sys.version_info.minor}",
        "site-packages",
    )
    te_path = os.path.join(site_dir, "typing_extensions.py")
    if os.path.isfile(te_path):
        sys.modules.pop("typing_extensions", None)
        spec = importlib.util.spec_from_file_location("typing_extensions", te_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules["typing_extensions"] = module


_force_typing_extensions()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import EVENT_MEDIA_DIR
from server.control import get_door_controller
from server.event_store import get_event_store

app = FastAPI(title="SmartDoorbell Server")

app.mount("/media", StaticFiles(directory=EVENT_MEDIA_DIR), name="media")


class DoorEvent(BaseModel):
    eventId: str
    timestamp: str
    type: str  # "KNOWN" | "UNKNOWN" | "RING"
    imageUrl: str
    personName: Optional[str] = None


class UnlockRequest(BaseModel):
    eventId: str
    source: Optional[str] = None


class ClearEventsRequest(BaseModel):
    removeMedia: Optional[bool] = True
    removeLog: Optional[bool] = True


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/events", response_model=List[DoorEvent])
def events():
    store = get_event_store()
    items = store.list_events() if store is not None else []
    return items


@app.post("/events/clear")
def clear_events(req: ClearEventsRequest):
    store = get_event_store()
    if store is None:
        return {"ok": False, "message": "event store unavailable"}
    result = store.clear_events(
        remove_media=bool(req.removeMedia),
        remove_log=bool(req.removeLog),
    )
    return {"ok": True, **result}


@app.post("/unlock")
def unlock(req: UnlockRequest):
    door = get_door_controller()
    ok = False
    message = "door unavailable"
    light_ok = False
    if door is not None:
        ok, message = door.open_and_close()
        try:
            light_ok = door.set_light_state(True)
        except Exception:
            light_ok = False
    store = get_event_store()
    if store is not None:
        store.log_action(
            "UNLOCK",
            ok,
            message=message,
            source=req.source or "api",
            request_event_id=req.eventId,
        )
    return {
        "ok": ok,
        "eventId": req.eventId,
        "message": message,
        "lightOk": light_ok,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/lock")
def lock(req: UnlockRequest):
    door = get_door_controller()
    ok = False
    message = "door unavailable"
    light_ok = False
    if door is not None:
        door.close()
        ok = True
        message = "door closed"
        try:
            light_ok = door.set_light_state(False)
        except Exception:
            light_ok = False
    store = get_event_store()
    if store is not None:
        store.log_action(
            "LOCK",
            ok,
            message=message,
            source=req.source or "api",
            request_event_id=req.eventId,
        )
    return {
        "ok": ok,
        "eventId": req.eventId,
        "message": message,
        "lightOk": light_ok,
        "timestamp": datetime.utcnow().isoformat(),
    }
