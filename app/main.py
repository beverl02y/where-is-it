"""FastAPI server: receives camera frames, stores detections, answers questions.

Every camera phone is its own *device* with separate records:
  * the camera phone holds a secret CAMERA TOKEN  -> may only upload photos
  * the owner holds a secret ROOM KEY (room link)  -> may only ask about that camera
  * the server operator holds WIIA_API_KEY         -> admin: list / remove devices
A device never sees another device's records.

Run:  uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
import secrets
import shutil
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .appearance import item_name
from .config import Settings, Zone, load_settings, parse_zones
from .db import Database, Device, check_pin, from_iso, to_iso
from .detector import build_detector
from .gemini_detector import DetectionUnavailable
from .locate import describe
from .search import SearchEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("whereisit")

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=300)


class ZoneIn(BaseModel):
    name: str
    label: str = ""
    polygon: list[list[float]]


class ZonesRequest(BaseModel):
    zones: list[ZoneIn] = Field(..., max_length=30)


PIN_PATTERN = r"^\d{4,6}$"


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    invite_code: str = Field("", max_length=100)
    pin: str | None = Field(None, pattern=PIN_PATTERN)


class PinRequest(BaseModel):
    pin: str = Field(..., pattern=PIN_PATTERN)


class ConnectRequest(BaseModel):
    camera_id: str = Field(..., min_length=1, max_length=20)
    pin: str = Field(..., min_length=1, max_length=10)


def decode_image(data: bytes):
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "File is not a valid image")
    return img


def device_info(d: Device) -> dict:
    return {"id": d.id, "name": d.name, "created_at": to_iso(d.created_at),
            "last_photo_at": to_iso(d.last_seen_at) if d.last_seen_at else None,
            "interval_s": d.interval_s, "has_pin": d.has_pin}


def create_app(settings: Settings | None = None, detector=None) -> FastAPI:
    settings = settings or load_settings()
    db = Database(settings.db_path)
    merged = db.merge_item_names(
        lambda n: n if n in settings.objects else item_name(n, settings.same_items))
    if merged:
        log.info("Merged %d records under one item name (same_items)", merged)
    rag = None
    if settings.rag_enabled and settings.model_type != "none":     # hybrid RAG fallback (needs Gemini)
        from .rag import RagAnswerer
        rag = RagAnswerer(settings, db)
    engine = SearchEngine(settings, db, rag=rag)
    data_dir = Path(settings.db_path).parent
    state = {"detector": detector, "last_prune": 0.0}
    det_lock = threading.Lock()
    failed_invites: dict[str, list[float]] = defaultdict(list)
    failed_pins_by_camera: dict[str, list[float]] = defaultdict(list)
    failed_pins_by_ip: dict[str, list[float]] = defaultdict(list)
    LOCK_WINDOW = 15 * 60

    def recent(store: dict, key: str) -> list[float]:
        store[key] = [t for t in store[key] if time.time() - t < LOCK_WINDOW]
        return store[key]

    def get_detector():
        with det_lock:
            if state["detector"] is None:
                state["detector"] = build_detector(settings)
        return state["detector"]

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if settings.api_key in ("", "change-me"):
            log.warning("Admin key is not set! Set WIIA_API_KEY before exposing this server.")
        if not settings.invite_code:
            log.warning("WIIA_INVITE_CODE is not set: only the admin can set up new cameras.")
        if settings.model_type != "none" and detector is None:
            d = get_detector()
            if hasattr(d, "warmup"):
                d.warmup()
        yield

    app = FastAPI(title="Where-Is-It AI", version="2.0.0", lifespan=lifespan)

    # ---------------- who is calling? ----------------
    def is_admin(key: str | None) -> bool:
        return bool(settings.api_key) and settings.api_key != "change-me" and \
            secrets.compare_digest(key or "", settings.api_key)

    def require_admin(x_api_key: str | None = Header(default=None)):
        if not is_admin(x_api_key):
            raise HTTPException(401, "Admin key required (X-API-Key)")

    def camera_device(x_camera_token: str | None = Header(default=None)) -> Device:
        d = db.device_by_camera_token(x_camera_token or "")
        if d is None:
            raise HTTPException(401, "This camera is not set up or was removed. Set it up again on the camera page.")
        return d

    def room_device(x_room_key: str | None = Header(default=None)) -> Device:
        d = db.device_by_room_key(x_room_key or "")
        if d is None:
            raise HTTPException(401, "This room link is not valid. Open the room link shown on your camera page.")
        return d

    def device_zones(dev: Device) -> list[Zone]:
        return [Zone(z["name"], z["label"], [tuple(p) for p in z["polygon"]]) for z in db.get_zones(dev.id)]

    def device_dir(dev_id: str) -> Path:
        return data_dir / "devices" / dev_id

    # ---------------- camera set-up ----------------
    @app.post("/api/devices/register")
    def register(req: RegisterRequest, request: Request, x_api_key: str | None = Header(default=None)):
        """A phone becomes a camera with its own records. Needs the invite code
        (or the admin key), so strangers can't use the server's Gemini quota."""
        ip = request.client.host if request.client else "?"
        recent = [t for t in failed_invites[ip] if time.time() - t < 900]
        failed_invites[ip] = recent
        if len(recent) >= 10:
            raise HTTPException(429, "Too many wrong invite codes. Try again in 15 minutes.")
        ok = is_admin(x_api_key) or (settings.invite_code and
                                     secrets.compare_digest(req.invite_code.strip(), settings.invite_code))
        if not ok:
            failed_invites[ip].append(time.time())
            raise HTTPException(403, "Wrong invite code. Ask the person who runs the server.")
        if db.count_devices() >= settings.max_devices:
            raise HTTPException(409, f"This server already has {settings.max_devices} cameras.")
        dev, camera_token, room_key = db.create_device(req.name.strip(), pin=req.pin)
        log.info("New camera %s (%s)", dev.id, dev.name)
        return {"device": device_info(dev), "camera_token": camera_token, "room_key": room_key}

    @app.get("/api/camera")
    def camera_info(dev: Device = Depends(camera_device)):
        return {"device": device_info(dev), "photos": db.frame_count(dev.id)}

    @app.post("/api/camera/pin")
    def set_pin(req: PinRequest, dev: Device = Depends(camera_device)):
        """Set or change the PIN used with the camera ID. Phones connected
        with the old PIN are disconnected."""
        db.set_pin(dev.id, req.pin)
        failed_pins_by_camera.pop(dev.id, None)
        return {"pin_set": True}

    @app.post("/api/room/connect")
    def connect_room(req: ConnectRequest, request: Request):
        """Connect a phone to a room with camera ID + PIN. Returns a private key
        for this phone only. 5 wrong PINs lock that camera ID for 15 minutes."""
        ip = request.client.host if request.client else "?"
        cam_id = req.camera_id.strip().lower()
        if len(recent(failed_pins_by_camera, cam_id)) >= 5:
            raise HTTPException(429, "Too many wrong PINs for this camera. Try again in 15 minutes.")
        if len(recent(failed_pins_by_ip, ip)) >= 20:
            raise HTTPException(429, "Too many wrong attempts. Try again in 15 minutes.")
        dev = db.get_device(cam_id)
        if dev is None or not check_pin(req.pin.strip(), db.pin_hash(cam_id)):
            failed_pins_by_camera[cam_id].append(time.time())
            failed_pins_by_ip[ip].append(time.time())
            # same message whether the ID exists or not, so IDs can't be discovered
            raise HTTPException(403, "Camera ID or PIN is wrong (or that camera has no PIN yet).")
        failed_pins_by_camera.pop(cam_id, None)
        return {"room_key": db.new_room_session(dev.id), "device": device_info(dev)}

    @app.post("/api/camera/room-key")
    def reset_room_key(dev: Device = Depends(camera_device)):
        """Make a new room link; the old one stops working (e.g. it was shared by mistake)."""
        return {"room_key": db.new_room_key(dev.id)}

    @app.delete("/api/camera")
    def remove_camera(dev: Device = Depends(camera_device)):
        """Remove this camera and ALL its records, zones and photos."""
        db.delete_device(dev.id)
        shutil.rmtree(device_dir(dev.id), ignore_errors=True)
        return {"removed": dev.id}

    # ---------------- DETECT + SAVE (camera token) ----------------
    @app.post("/api/frames")
    def upload_frame(file: UploadFile = File(...),
                     captured_at: str | None = Form(None),
                     interval_s: int | None = Form(None),
                     dev: Device = Depends(camera_device)):
        t0 = time.perf_counter()
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image too large (max 8 MB)")
        image = decode_image(data)

        ts = datetime.now(timezone.utc)
        if captured_at:
            try:
                ts = from_iso(captured_at)
            except ValueError:
                raise HTTPException(400, "captured_at must be ISO-8601")
        if interval_s is not None and not (1 <= interval_s <= 24 * 3600):
            interval_s = None

        try:
            dets = get_detector().detect(image)
        except DetectionUnavailable as e:
            # Don't save an empty frame: that would wrongly mean "nothing visible now".
            log.warning("Detection unavailable: %s", e)
            raise HTTPException(503, f"AI detection unavailable: {e}", headers={"Retry-After": "30"})
        zones = device_zones(dev)
        rows = []
        for d in dets:
            zone, label = describe(d.box, settings, phrase=d.where, saved_zones=zones)
            rows.append({"object": d.object, "location": zone, "location_label": label,
                         "confidence": d.confidence, "box": d.box,
                         "appearance": d.appearance, "color": d.color, "size": d.size, "shape": d.shape,
                         "name_ko": d.name_ko, "appearance_ko": d.appearance_ko,
                         # Gemini's Korean place only when its own phrase was used (not a zone/grid)
                         "location_ko": d.where_ko if zone == "ai" else None})

        image_path = None
        if settings.save_frames:
            import cv2
            folder = device_dir(dev.id) / "frames"
            folder.mkdir(parents=True, exist_ok=True)
            image_path = str(folder / f"{ts.strftime('%Y%m%dT%H%M%S')}.jpg")
            cv2.imwrite(image_path, image)

        frame_id = db.add_frame(ts, rows, camera_id=dev.id, image_path=image_path,
                                interval_s=interval_s, device_id=dev.id)
        db.touch_device(dev.id, interval_s)

        # Retention cleanup at most once an hour (all devices).
        if time.time() - state["last_prune"] > 3600:
            state["last_prune"] = time.time()
            removed = db.prune(datetime.now(timezone.utc) - timedelta(days=settings.retention_days))
            if removed:
                log.info("Pruned %d old frames", removed)

        return {
            "frame_id": frame_id,
            "captured_at": to_iso(ts),
            "processing_ms": round((time.perf_counter() - t0) * 1000, 1),
            "detections": [
                {"object": r["object"], "appearance": r["appearance"], "location": r["location_label"],
                 "confidence": round(r["confidence"], 3),
                 "confirmed": r["confidence"] >= settings.confirm_threshold}
                for r in rows
            ],
        }

    # ---------------- test / training photos ----------------
    @app.post("/api/test-photos")
    def save_test_photo(file: UploadFile = File(...), dev: Device = Depends(camera_device)):
        """Save a full-quality photo (zone drawing, accuracy test) in this camera's folder."""
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image too large (max 8 MB)")
        decode_image(data)  # reject non-images
        folder = device_dir(dev.id) / "eval" / "images"
        folder.mkdir(parents=True, exist_ok=True)
        n = len(list(folder.glob("img_*.jpg"))) + 1
        while (folder / f"img_{n:03d}.jpg").exists():
            n += 1
        path = folder / f"img_{n:03d}.jpg"
        path.write_bytes(data)
        return {"saved": path.name, "total": len(list(folder.glob("img_*.jpg"))),
                "folder": f"data/devices/{dev.id}/eval/images"}

    @app.get("/api/test-photos/latest")
    def latest_test_photo(dev: Device = Depends(room_device)):
        folder = device_dir(dev.id) / "eval" / "images"
        photos = sorted(folder.glob("img_*.jpg")) if folder.exists() else []
        if not photos:
            raise HTTPException(404, "No test photo yet — press 'Save test photo' on the camera page")
        return FileResponse(photos[-1], media_type="image/jpeg")

    # ---------------- SEARCH + EXPLAIN (room key) ----------------
    @app.get("/api/room")
    def room_info(dev: Device = Depends(room_device)):
        return {"device": device_info(dev), "photos": db.frame_count(dev.id)}

    @app.post("/api/ask")
    def ask(req: AskRequest, dev: Device = Depends(room_device)):
        return engine.ask(req.question, device_id=dev.id).to_dict()

    @app.get("/api/objects")
    def objects(dev: Device = Depends(room_device)):
        return {"objects": engine.overview(device_id=dev.id), "confirm_threshold": settings.confirm_threshold}

    @app.delete("/api/room/history")
    def delete_history(dev: Device = Depends(room_device)):
        return {"deleted_photos": db.delete_history(dev.id)}

    @app.get("/api/zones")
    def get_zones(dev: Device = Depends(room_device)):
        return {"mode": settings.location_mode, "saved": bool(db.get_zones(dev.id)),
                "zones": db.get_zones(dev.id)}

    @app.post("/api/zones")
    def save_zones(req: ZonesRequest, dev: Device = Depends(room_device)):
        """Zones for THIS camera only. Take effect for the next photo."""
        try:
            zones = parse_zones([z.model_dump() for z in req.zones])
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(400, str(e))
        if not zones:
            raise HTTPException(400, "Draw at least one zone")
        db.set_zones(dev.id, [{"name": z.name, "label": z.label, "polygon": [list(p) for p in z.polygon]}
                              for z in zones])
        return {"saved": len(zones), "zones": [z.name for z in zones]}

    @app.delete("/api/zones")
    def clear_zones(dev: Device = Depends(room_device)):
        db.set_zones(dev.id, [])
        return {"cleared": True}

    # ---------------- admin (server operator only) ----------------
    @app.get("/api/admin/devices", dependencies=[Depends(require_admin)])
    def admin_devices():
        """Lists cameras (name, last photo, number of photos) — never their records."""
        return {"devices": db.list_devices()}

    @app.delete("/api/admin/devices/{dev_id}", dependencies=[Depends(require_admin)])
    def admin_remove(dev_id: str):
        if db.get_device(dev_id) is None:
            raise HTTPException(404, "No such camera")
        db.delete_device(dev_id)
        shutil.rmtree(device_dir(dev_id), ignore_errors=True)
        return {"removed": dev_id}

    # ---------------- public ----------------
    @app.get("/api/health")
    def health():
        """Public: says nothing about any camera or its records."""
        d = state["detector"]
        return {"status": "ok", "detector": getattr(d, "name", "not loaded"),
                "setup_open": bool(settings.invite_code)}

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/camera", include_in_schema=False)
    def camera_page():
        return FileResponse(STATIC / "camera.html")

    @app.get("/zones", include_in_schema=False)
    def zones_page():
        return FileResponse(STATIC / "zones.html")

    app.state.db = db
    app.state.engine = engine
    app.state.settings = settings
    return app
