from fastapi.testclient import TestClient

from app.detector import Detection
from app.main import create_app

INVITE = "class-2026"


class FakeDetector:
    name = "fake"

    def detect(self, image):
        # glasses lying on the desk zone, wallet uncertain
        return [Detection("glasses", 0.9, (0.10, 0.70, 0.20, 0.80)),
                Detection("wallet", 0.5, (0.70, 0.60, 0.80, 0.70))]


def client(settings, monkeypatch, detector=None):
    import app.main as m
    monkeypatch.setattr(m, "decode_image", lambda data: object())
    settings.invite_code = INVITE
    return TestClient(create_app(settings, detector=detector or FakeDetector()))


def register(c, name="My room"):
    """Set up a camera; returns (camera headers, room headers, device id)."""
    r = c.post("/api/devices/register", json={"name": name, "invite_code": INVITE})
    assert r.status_code == 200, r.text
    j = r.json()
    return {"X-Camera-Token": j["camera_token"]}, {"X-Room-Key": j["room_key"]}, j["device"]["id"]


def photo(c, cam):
    return c.post("/api/frames", headers=cam, files={"file": ("f.jpg", b"x", "image/jpeg")})


def test_everything_needs_the_right_key(settings, monkeypatch):
    c = client(settings, monkeypatch)
    assert c.post("/api/ask", json={"question": "where are my glasses"}).status_code == 401
    assert c.post("/api/ask", headers={"X-API-Key": "test-key"},
                  json={"question": "where are my glasses"}).status_code == 401   # admin key can't read rooms
    assert c.post("/api/frames", files={"file": ("f.jpg", b"x", "image/jpeg")}).status_code == 401
    assert c.get("/api/admin/devices").status_code == 401


def test_register_needs_invite_code(settings, monkeypatch):
    c = client(settings, monkeypatch)
    assert c.post("/api/devices/register", json={"name": "x", "invite_code": "wrong"}).status_code == 403
    assert c.post("/api/devices/register", headers={"X-API-Key": "test-key"},
                  json={"name": "admin-made"}).status_code == 200
    settings.max_devices = 1
    assert c.post("/api/devices/register", json={"name": "x", "invite_code": INVITE}).status_code == 409


def test_wrong_invite_codes_are_throttled(settings, monkeypatch):
    c = client(settings, monkeypatch)
    for _ in range(10):
        c.post("/api/devices/register", json={"name": "x", "invite_code": "guess"})
    assert c.post("/api/devices/register", json={"name": "x", "invite_code": INVITE}).status_code == 429


def test_frame_then_ask(settings, monkeypatch):
    settings.location_mode = "zones"          # the v1 drawn-zones behaviour
    c = client(settings, monkeypatch)
    cam, room, _ = register(c)
    r = photo(c, cam)
    assert r.status_code == 200, r.text
    dets = {d["object"]: d for d in r.json()["detections"]}
    assert dets["glasses"]["location"] == "on the desk" and dets["glasses"]["confirmed"]
    assert dets["wallet"]["location"] == "on the bed" and not dets["wallet"]["confirmed"]

    a = c.post("/api/ask", headers=room, json={"question": "Where are my glasses?"}).json()
    assert a["status"] == "current" and a["location"] == "on the desk"
    w = c.post("/api/ask", headers=room, json={"question": "Where is my wallet?"}).json()
    assert w["status"] == "possible" and w["confirmed"] is False

    objs = c.get("/api/objects", headers=room).json()["objects"]
    assert {o["object"] for o in objs} == {"glasses", "wallet", "card", "earphones", "phone", "charger", "hairtie"}
    assert c.get("/api/room", headers=room).json()["photos"] == 1
    assert set(c.get("/api/health").json()) == {"status", "detector", "setup_open"}   # public: no counts


def test_pages_zones_and_test_photos(settings, monkeypatch):
    c = client(settings, monkeypatch)
    cam, room, dev = register(c)
    for page in ("/", "/camera", "/zones"):
        assert c.get(page).status_code == 200
    z = c.get("/api/zones", headers=room).json()
    assert z["mode"] == "auto" and z["zones"] == []
    assert c.get("/api/test-photos/latest", headers=room).status_code == 404
    r = c.post("/api/test-photos", headers=cam, files={"file": ("p.jpg", b"jpegbytes", "image/jpeg")}).json()
    assert r["saved"] == "img_001.jpg" and r["folder"] == f"data/devices/{dev}/eval/images"
    r = c.post("/api/test-photos", headers=cam, files={"file": ("p.jpg", b"second", "image/jpeg")}).json()
    assert r["saved"] == "img_002.jpg"
    assert c.get("/api/test-photos/latest", headers=room).content == b"second"
    assert c.post("/api/test-photos", headers=room, files={"file": ("p.jpg", b"x", "image/jpeg")}).status_code == 401


def test_save_zones(settings, monkeypatch):
    c = client(settings, monkeypatch)
    cam, room, _ = register(c)
    body = {"zones": [{"name": "my_desk", "label": "on my desk",
                       "polygon": [[0, 0.5], [0.5, 0.5], [0.5, 1], [0, 1]]}]}
    r = c.post("/api/zones", headers=room, json=body)
    assert r.status_code == 200 and r.json()["zones"] == ["my_desk"]
    # the next frame uses the new zone (glasses box is at x .1-.2, y .7-.8)
    assert {x["object"]: x["location"] for x in photo(c, cam).json()["detections"]}["glasses"] == "on my desk"
    assert c.get("/api/zones", headers=room).json()["zones"][0]["name"] == "my_desk"
    # clearing goes back to automatic locations
    assert c.delete("/api/zones", headers=room).json() == {"cleared": True}
    d = photo(c, cam).json()
    assert {x["object"]: x["location"] for x in d["detections"]}["glasses"] == "in the bottom-left of the camera view"
    # validation
    bad = {"zones": [{"name": "Bad Name!", "polygon": [[0, 0], [1, 0], [1, 1]]}]}
    assert c.post("/api/zones", headers=room, json=bad).status_code == 400
    two = {"zones": [{"name": "x", "polygon": [[0, 0], [2, 0]]}]}
    assert c.post("/api/zones", headers=room, json=two).status_code == 400
    assert c.post("/api/zones", headers=cam, json=body).status_code == 401      # camera can't change zones


def test_old_database_is_upgraded(tmp_path):
    import sqlite3
    from datetime import datetime, timezone

    from app.db import Database
    path = tmp_path / "old.db"
    c = sqlite3.connect(path)
    c.executescript("""CREATE TABLE frames (id INTEGER PRIMARY KEY AUTOINCREMENT, captured_at TEXT NOT NULL,
                       camera_id TEXT NOT NULL DEFAULT 'cam1', image_path TEXT);
                       CREATE TABLE detections (id INTEGER PRIMARY KEY AUTOINCREMENT, frame_id INTEGER NOT NULL,
                       object TEXT NOT NULL, location TEXT NOT NULL, location_label TEXT NOT NULL,
                       confidence REAL NOT NULL, x1 REAL, y1 REAL, x2 REAL, y2 REAL, detected_at TEXT NOT NULL);
                       INSERT INTO frames (captured_at) VALUES ('2026-11-01T00:00:00+00:00');""")
    c.commit(); c.close()
    db = Database(str(path))                         # adds interval_s and device_id columns
    assert db.latest_frame().interval_s is None      # old data: device_id NULL
    db.add_frame(datetime(2026, 11, 2, tzinfo=timezone.utc), [], interval_s=900)
    assert db.latest_frame().interval_s == 900
    dev, _, _ = db.create_device("new camera")
    assert db.latest_frame(dev.id) is None           # old records never appear under a camera
