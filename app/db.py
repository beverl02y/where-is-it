"""SQLite storage (Detect -> SAVE).

Every camera phone is a *device* with its own records. Frames, detections, zones
and test photos all carry the device_id, and every read filters on it, so two
people using the service at the same time can never see each other's records.

Records written by older versions have device_id NULL; they are only reachable by
code that passes device_id=None (tests, offline tools), never through the web API.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id                TEXT PRIMARY KEY,        -- short public id, e.g. '3f9a1c2e'
    name              TEXT NOT NULL,           -- e.g. "Lae's room"
    camera_token_hash TEXT NOT NULL UNIQUE,    -- sha256 of the camera phone's secret
    room_key_hash     TEXT NOT NULL UNIQUE,    -- sha256 of the room link secret
    created_at        TEXT NOT NULL,
    last_seen_at      TEXT,
    interval_s        INTEGER
);

CREATE TABLE IF NOT EXISTS frames (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,          -- ISO-8601 UTC
    camera_id   TEXT NOT NULL DEFAULT 'cam1',
    image_path  TEXT,
    interval_s  INTEGER,                -- how often the camera sends photos (seconds)
    device_id   TEXT                    -- owner device (NULL = data from before devices)
);
CREATE INDEX IF NOT EXISTS idx_frames_time ON frames(captured_at);

CREATE TABLE IF NOT EXISTS detections (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_id       INTEGER NOT NULL REFERENCES frames(id) ON DELETE CASCADE,
    object         TEXT NOT NULL,       -- object key, e.g. 'glasses'
    location       TEXT NOT NULL,       -- zone name, e.g. 'desk'
    location_label TEXT NOT NULL,       -- e.g. 'on the desk'
    confidence     REAL NOT NULL,       -- 0..1
    x1 REAL, y1 REAL, x2 REAL, y2 REAL, -- normalised box
    detected_at    TEXT NOT NULL,       -- ISO-8601 UTC (= frame time)
    device_id      TEXT,                -- copied from the frame
    appearance     TEXT,                -- e.g. "large silver laptop" (tells same-name items apart)
    color          TEXT,
    size           TEXT,
    shape          TEXT,
    name_ko        TEXT,                -- Korean: "물병"
    location_ko    TEXT,                -- Korean: "책상 위 노트북 옆"
    appearance_ko  TEXT                 -- Korean: "흰색 물병"
);
CREATE INDEX IF NOT EXISTS idx_det_obj_time ON detections(object, detected_at);
CREATE INDEX IF NOT EXISTS idx_det_frame ON detections(frame_id);

CREATE TABLE IF NOT EXISTS room_sessions (   -- phones connected with camera ID + PIN
    token_hash TEXT PRIMARY KEY,
    device_id  TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS zones (
    device_id    TEXT NOT NULL,
    name         TEXT NOT NULL,
    label        TEXT NOT NULL,
    polygon_json TEXT NOT NULL,
    PRIMARY KEY (device_id, name)
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_frames_dev_time ON frames(device_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_det_dev_obj_time ON detections(device_id, object, detected_at);
"""


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def from_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def hash_secret(secret: str) -> str:
    """For long random secrets (tokens, keys)."""
    return hashlib.sha256(secret.encode()).hexdigest()


PIN_ITERATIONS = 200_000


def hash_pin(pin: str) -> str:
    """PINs are short, so use a salted, slow hash (PBKDF2)."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), PIN_ITERATIONS).hex()
    return f"pbkdf2${PIN_ITERATIONS}${salt}${digest}"


def check_pin(pin: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, iters, salt, digest = stored.split("$")
        test = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), int(iters)).hex()
    except ValueError:
        return False
    return hmac.compare_digest(test, digest)


@dataclass
class DetectionRecord:
    id: int
    frame_id: int
    object: str
    location: str
    location_label: str
    confidence: float
    detected_at: datetime
    appearance: str | None = None
    color: str | None = None
    size: str | None = None
    shape: str | None = None
    name_ko: str | None = None
    location_ko: str | None = None
    appearance_ko: str | None = None


@dataclass
class FrameRecord:
    id: int
    captured_at: datetime
    camera_id: str
    interval_s: int | None = None


@dataclass
class Device:
    id: str
    name: str
    created_at: datetime
    last_seen_at: datetime | None
    interval_s: int | None
    has_pin: bool = False


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript(SCHEMA)
            # upgrade databases created by earlier versions
            for table, col, typ in (("frames", "interval_s", "INTEGER"),
                                    ("frames", "device_id", "TEXT"),
                                    ("detections", "device_id", "TEXT"),
                                    ("devices", "pin_hash", "TEXT"),
                                    ("detections", "appearance", "TEXT"),
                                    ("detections", "color", "TEXT"),
                                    ("detections", "size", "TEXT"),
                                    ("detections", "shape", "TEXT"),
                                    ("detections", "name_ko", "TEXT"),
                                    ("detections", "location_ko", "TEXT"),
                                    ("detections", "appearance_ko", "TEXT")):
                cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
                if col not in cols:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
            c.executescript(INDEXES)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---------- devices ----------
    @staticmethod
    def _device(row) -> Device:
        return Device(row["id"], row["name"], from_iso(row["created_at"]),
                      from_iso(row["last_seen_at"]) if row["last_seen_at"] else None, row["interval_s"],
                      bool(row["pin_hash"]))

    def create_device(self, name: str, pin: str | None = None) -> tuple[Device, str, str]:
        """Returns (device, camera_token, room_key). The two secrets are shown once;
        only their hashes are stored."""
        camera_token = "cam_" + secrets.token_urlsafe(24)
        room_key = "room_" + secrets.token_urlsafe(24)
        now = to_iso(datetime.now(timezone.utc))
        with self.connect() as c:
            while True:
                dev_id = secrets.token_hex(4)
                if not c.execute("SELECT 1 FROM devices WHERE id = ?", (dev_id,)).fetchone():
                    break
            c.execute("INSERT INTO devices (id, name, camera_token_hash, room_key_hash, created_at, pin_hash) "
                      "VALUES (?, ?, ?, ?, ?, ?)", (dev_id, name, hash_secret(camera_token), hash_secret(room_key),
                                                     now, hash_pin(pin) if pin else None))
        return self.get_device(dev_id), camera_token, room_key

    def get_device(self, dev_id: str) -> Device | None:
        with self.connect() as c:
            row = c.execute("SELECT * FROM devices WHERE id = ?", (dev_id,)).fetchone()
        return self._device(row) if row else None

    def device_by_camera_token(self, token: str) -> Device | None:
        if not token:
            return None
        with self.connect() as c:
            row = c.execute("SELECT * FROM devices WHERE camera_token_hash = ?", (hash_secret(token),)).fetchone()
        return self._device(row) if row else None

    def device_by_room_key(self, key: str) -> Device | None:
        """Accepts the room link key OR a session made with camera ID + PIN."""
        if not key:
            return None
        h = hash_secret(key)
        with self.connect() as c:
            row = c.execute("SELECT * FROM devices WHERE room_key_hash = ?", (h,)).fetchone()
            if row is None:
                row = c.execute("SELECT d.* FROM room_sessions s JOIN devices d ON d.id = s.device_id "
                                "WHERE s.token_hash = ?", (h,)).fetchone()
        return self._device(row) if row else None

    # ---------- PIN ----------
    def pin_hash(self, dev_id: str) -> str | None:
        with self.connect() as c:
            row = c.execute("SELECT pin_hash FROM devices WHERE id = ?", (dev_id,)).fetchone()
        return row["pin_hash"] if row else None

    def set_pin(self, dev_id: str, pin: str) -> None:
        """New PIN; phones connected with the old PIN are disconnected."""
        with self.connect() as c:
            c.execute("UPDATE devices SET pin_hash = ? WHERE id = ?", (hash_pin(pin), dev_id))
            c.execute("DELETE FROM room_sessions WHERE device_id = ?", (dev_id,))

    def new_room_session(self, dev_id: str) -> str:
        token = "rs_" + secrets.token_urlsafe(24)
        with self.connect() as c:
            c.execute("INSERT INTO room_sessions (token_hash, device_id, created_at) VALUES (?, ?, ?)",
                      (hash_secret(token), dev_id, to_iso(datetime.now(timezone.utc))))
        return token

    def new_room_key(self, dev_id: str) -> str:
        key = "room_" + secrets.token_urlsafe(24)
        with self.connect() as c:
            c.execute("UPDATE devices SET room_key_hash = ? WHERE id = ?", (hash_secret(key), dev_id))
        return key

    def touch_device(self, dev_id: str, interval_s: int | None) -> None:
        with self.connect() as c:
            c.execute("UPDATE devices SET last_seen_at = ?, interval_s = COALESCE(?, interval_s) WHERE id = ?",
                      (to_iso(datetime.now(timezone.utc)), interval_s, dev_id))

    def list_devices(self) -> list[dict]:
        with self.connect() as c:
            rows = c.execute(
                "SELECT d.*, (SELECT COUNT(*) FROM frames f WHERE f.device_id = d.id) AS photos "
                "FROM devices d ORDER BY created_at").fetchall()
        return [{"id": r["id"], "name": r["name"], "created_at": r["created_at"],
                 "last_seen_at": r["last_seen_at"], "interval_s": r["interval_s"], "photos": r["photos"]}
                for r in rows]

    def count_devices(self) -> int:
        with self.connect() as c:
            return c.execute("SELECT COUNT(*) FROM devices").fetchone()[0]

    def delete_history(self, dev_id: str) -> int:
        with self.connect() as c:
            c.execute("DELETE FROM detections WHERE device_id = ?", (dev_id,))
            return c.execute("DELETE FROM frames WHERE device_id = ?", (dev_id,)).rowcount

    def delete_device(self, dev_id: str) -> None:
        self.delete_history(dev_id)
        with self.connect() as c:
            c.execute("DELETE FROM zones WHERE device_id = ?", (dev_id,))
            c.execute("DELETE FROM room_sessions WHERE device_id = ?", (dev_id,))
            c.execute("DELETE FROM devices WHERE id = ?", (dev_id,))

    # ---------- zones (per device) ----------
    def get_zones(self, dev_id: str) -> list[dict]:
        with self.connect() as c:
            rows = c.execute("SELECT name, label, polygon_json FROM zones WHERE device_id = ? ORDER BY name",
                             (dev_id,)).fetchall()
        return [{"name": r["name"], "label": r["label"], "polygon": json.loads(r["polygon_json"])} for r in rows]

    def set_zones(self, dev_id: str, zones: list[dict]) -> None:
        with self.connect() as c:
            c.execute("DELETE FROM zones WHERE device_id = ?", (dev_id,))
            c.executemany("INSERT INTO zones (device_id, name, label, polygon_json) VALUES (?, ?, ?, ?)",
                          [(dev_id, z["name"], z["label"], json.dumps(z["polygon"])) for z in zones])

    # ---------- writes ----------
    def add_frame(self, captured_at: datetime, detections: list[dict],
                  camera_id: str = "cam1", image_path: str | None = None,
                  interval_s: int | None = None, device_id: str | None = None) -> int:
        """Store one processed frame and all of its detections atomically.

        Each detection dict: object, location, location_label, confidence, box(x1,y1,x2,y2).
        """
        ts = to_iso(captured_at)
        with self.connect() as c:
            cur = c.execute(
                "INSERT INTO frames (captured_at, camera_id, image_path, interval_s, device_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, camera_id, image_path, interval_s, device_id),
            )
            frame_id = cur.lastrowid
            c.executemany(
                """INSERT INTO detections (frame_id, object, location, location_label,
                   confidence, x1, y1, x2, y2, detected_at, device_id, appearance, color, size, shape,
                   name_ko, location_ko, appearance_ko)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (frame_id, d["object"], d["location"], d["location_label"],
                     float(d["confidence"]), *(d.get("box") or (None, None, None, None)), ts, device_id,
                     d.get("appearance"), d.get("color"), d.get("size"), d.get("shape"),
                     d.get("name_ko"), d.get("location_ko"), d.get("appearance_ko"))
                    for d in detections
                ],
            )
        return frame_id

    def prune(self, older_than: datetime) -> int:
        with self.connect() as c:
            cur = c.execute("DELETE FROM frames WHERE captured_at < ?", (to_iso(older_than),))
            return cur.rowcount

    # ---------- reads (always for ONE device; `IS ?` also matches NULL) ----------
    @staticmethod
    def _det(row) -> DetectionRecord:
        return DetectionRecord(
            id=row["id"], frame_id=row["frame_id"], object=row["object"],
            location=row["location"], location_label=row["location_label"],
            confidence=row["confidence"], detected_at=from_iso(row["detected_at"]),
            appearance=row["appearance"], color=row["color"], size=row["size"], shape=row["shape"],
            name_ko=row["name_ko"], location_ko=row["location_ko"], appearance_ko=row["appearance_ko"],
        )

    def latest_frame(self, device_id: str | None = None) -> FrameRecord | None:
        with self.connect() as c:
            row = c.execute(
                "SELECT id, captured_at, camera_id, interval_s FROM frames WHERE device_id IS ? "
                "ORDER BY captured_at DESC, id DESC LIMIT 1", (device_id,)
            ).fetchone()
        if not row:
            return None
        return FrameRecord(row["id"], from_iso(row["captured_at"]), row["camera_id"], row["interval_s"])

    @staticmethod
    def _names(obj) -> tuple[str, list[str]]:
        """SQL for one item name or several ("water bottle" and "glass bottle")."""
        names = [obj] if isinstance(obj, str) else list(obj)
        return f"object IN ({', '.join('?' * len(names))})", names

    def best_in_frame(self, frame_id: int, obj: str, device_id: str | None = None) -> DetectionRecord | None:
        with self.connect() as c:
            row = c.execute(
                f"SELECT * FROM detections WHERE frame_id = ? AND {self._names(obj)[0]} AND device_id IS ? "
                "ORDER BY confidence DESC LIMIT 1",
                (frame_id, *self._names(obj)[1], device_id),
            ).fetchone()
        return self._det(row) if row else None

    def instances_in_frame(self, frame_id: int, obj: str, device_id: str | None = None) -> list[DetectionRecord]:
        """Every copy of `obj` in one photo (e.g. two laptops), most confident first."""
        with self.connect() as c:
            rows = c.execute(
                f"SELECT * FROM detections WHERE frame_id = ? AND {self._names(obj)[0]} AND device_id IS ? "
                "ORDER BY confidence DESC", (frame_id, *self._names(obj)[1], device_id)).fetchall()
        return [self._det(r) for r in rows]

    def history(self, obj: str, device_id: str | None = None, limit: int = 500) -> list[DetectionRecord]:
        """Recent records of `obj`, newest first (used to filter by appearance)."""
        with self.connect() as c:
            rows = c.execute(
                f"SELECT * FROM detections WHERE device_id IS ? AND {self._names(obj)[0]} "
                "ORDER BY detected_at DESC, confidence DESC LIMIT ?", (device_id, *self._names(obj)[1], limit)).fetchall()
        return [self._det(r) for r in rows]

    def last_confirmed(self, obj: str, threshold: float, device_id: str | None = None) -> DetectionRecord | None:
        with self.connect() as c:
            row = c.execute(
                f"SELECT * FROM detections WHERE device_id IS ? AND {self._names(obj)[0]} AND confidence >= ? "
                "ORDER BY detected_at DESC, confidence DESC LIMIT 1",
                (device_id, *self._names(obj)[1], threshold),
            ).fetchone()
        return self._det(row) if row else None

    def latest_unconfirmed(self, obj: str, threshold: float, after: datetime | None = None,
                           device_id: str | None = None) -> DetectionRecord | None:
        sql = f"SELECT * FROM detections WHERE device_id IS ? AND {self._names(obj)[0]} AND confidence < ?"
        args: list = [device_id, *self._names(obj)[1], threshold]
        if after is not None:
            sql += " AND detected_at > ?"
            args.append(to_iso(after))
        sql += " ORDER BY detected_at DESC, confidence DESC LIMIT 1"
        with self.connect() as c:
            row = c.execute(sql, args).fetchone()
        return self._det(row) if row else None

    def merge_item_names(self, rename) -> int:
        """Give older records the one name for their kind of item ("facial mask" -> "face mask").
        `rename(name)` returns the name to use. Runs when the server starts."""
        changed = 0
        with self.connect() as c:
            for (name,) in c.execute("SELECT DISTINCT object FROM detections").fetchall():
                new = rename(name)
                if new and new != name:
                    changed += c.execute("UPDATE detections SET object = ? WHERE object = ?",
                                         (new, name)).rowcount
        return changed

    def recent(self, device_id: str | None, since: datetime, limit: int = 800) -> list[DetectionRecord]:
        """All records of this camera since `since`, newest first (searched by the RAG fallback)."""
        with self.connect() as c:
            rows = c.execute(
                "SELECT * FROM detections WHERE device_id IS ? AND detected_at >= ? "
                "ORDER BY detected_at DESC, confidence DESC LIMIT ?", (device_id, to_iso(since), limit)).fetchall()
        return [self._det(r) for r in rows]

    def frame_ids_at(self, frame_id: int, device_id: str | None) -> set[int]:
        """Record ids in one photo (to mark what is in the current view)."""
        with self.connect() as c:
            return {r[0] for r in c.execute("SELECT id FROM detections WHERE frame_id = ? AND device_id IS ?",
                                            (frame_id, device_id))}

    def korean_names(self, device_id: str | None = None) -> dict[str, str]:
        """Korean name -> saved item name for this camera, e.g. {"물병": "water bottle"}."""
        with self.connect() as c:
            rows = c.execute(
                "SELECT name_ko, object FROM detections WHERE device_id IS ? AND name_ko IS NOT NULL "
                "GROUP BY name_ko, object ORDER BY MAX(detected_at) DESC", (device_id,)).fetchall()
        out: dict[str, str] = {}
        for ko, obj in rows:
            out.setdefault(ko, obj)
        return out

    def known_objects(self, device_id: str | None = None) -> list[str]:
        """Every object name this device's camera has detected (items beyond the 7)."""
        with self.connect() as c:
            return [r[0] for r in c.execute("SELECT DISTINCT object FROM detections WHERE device_id IS ?",
                                            (device_id,))]

    def recent_confirmed_objects(self, threshold: float, since: datetime,
                                 device_id: str | None = None) -> list[str]:
        with self.connect() as c:
            rows = c.execute(
                "SELECT object, MAX(detected_at) AS t FROM detections "
                "WHERE device_id IS ? AND confidence >= ? AND detected_at >= ? GROUP BY object ORDER BY t DESC",
                (device_id, threshold, to_iso(since)),
            ).fetchall()
        return [r[0] for r in rows]

    def frame_count(self, device_id: str | None = None) -> int:
        with self.connect() as c:
            return c.execute("SELECT COUNT(*) FROM frames WHERE device_id IS ?", (device_id,)).fetchone()[0]
