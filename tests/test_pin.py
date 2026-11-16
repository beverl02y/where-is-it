"""Connecting a phone to a room with camera ID + PIN."""
from test_api import INVITE, client, photo

from app.detector import Detection


class Fake:
    name = "fake"

    def __init__(self):
        self.next = [Detection("glasses", 0.9, (0.1, 0.1, 0.2, 0.2), where="on the desk")]

    def detect(self, image):
        return self.next


def setup_camera(c, name, pin="2580"):
    r = c.post("/api/devices/register", json={"name": name, "invite_code": INVITE, "pin": pin}).json()
    return {"X-Camera-Token": r["camera_token"]}, r["device"]["id"]


def connect(c, cam_id, pin):
    return c.post("/api/room/connect", json={"camera_id": cam_id, "pin": pin})


def test_connect_with_id_and_pin(settings, monkeypatch):
    c = client(settings, monkeypatch, Fake())
    cam, cam_id = setup_camera(c, "Lae's room")
    photo(c, cam)
    r = connect(c, cam_id.upper(), "2580")                  # ID is not case-sensitive
    assert r.status_code == 200 and r.json()["device"]["name"] == "Lae's room"
    room = {"X-Room-Key": r.json()["room_key"]}
    a = c.post("/api/ask", headers=room, json={"question": "Where are my glasses?"}).json()
    assert a["status"] == "current" and "on the desk" in a["message"]
    # the session only reads: it can't upload or manage the camera
    assert photo(c, room).status_code == 401
    assert c.post("/api/camera/pin", headers=room, json={"pin": "1111"}).status_code == 401


def test_wrong_pin_and_unknown_id_look_the_same(settings, monkeypatch):
    c = client(settings, monkeypatch, Fake())
    _, cam_id = setup_camera(c, "A")
    wrong = connect(c, cam_id, "0000")
    unknown = connect(c, "ffffffff", "2580")
    assert wrong.status_code == unknown.status_code == 403
    assert wrong.json() == unknown.json()


def test_five_wrong_pins_lock_the_camera(settings, monkeypatch):
    c = client(settings, monkeypatch, Fake())
    _, cam_id = setup_camera(c, "A")
    for _ in range(5):
        assert connect(c, cam_id, "9999").status_code == 403
    assert connect(c, cam_id, "2580").status_code == 429     # even the right PIN waits


def test_another_cameras_pin_does_not_open_mine(settings, monkeypatch):
    c = client(settings, monkeypatch, Fake())
    _, mine = setup_camera(c, "Mine", pin="1234")
    _, hers = setup_camera(c, "Hers", pin="5678")
    assert connect(c, mine, "5678").status_code == 403
    assert connect(c, hers, "5678").json()["device"]["name"] == "Hers"


def test_changing_pin_disconnects_old_phones(settings, monkeypatch):
    c = client(settings, monkeypatch, Fake())
    cam, cam_id = setup_camera(c, "A")
    old = {"X-Room-Key": connect(c, cam_id, "2580").json()["room_key"]}
    assert c.post("/api/camera/pin", headers=cam, json={"pin": "73519"}).json() == {"pin_set": True}
    assert c.get("/api/room", headers=old).status_code == 401
    assert connect(c, cam_id, "2580").status_code == 403
    assert connect(c, cam_id, "73519").status_code == 200


def test_existing_camera_without_pin(settings, monkeypatch):
    c = client(settings, monkeypatch, Fake())
    r = c.post("/api/devices/register", json={"name": "Old", "invite_code": INVITE}).json()
    cam, cam_id = {"X-Camera-Token": r["camera_token"]}, r["device"]["id"]
    assert r["device"]["has_pin"] is False
    assert connect(c, cam_id, "2580").status_code == 403        # no PIN yet: can't connect
    c.post("/api/camera/pin", headers=cam, json={"pin": "2580"})
    assert c.get("/api/camera", headers=cam).json()["device"]["has_pin"] is True
    assert connect(c, cam_id, "2580").status_code == 200


def test_pin_format_and_removal(settings, monkeypatch):
    c = client(settings, monkeypatch, Fake())
    for bad in ("12", "1234567", "12ab"):
        assert c.post("/api/devices/register",
                      json={"name": "x", "invite_code": INVITE, "pin": bad}).status_code == 422
    cam, cam_id = setup_camera(c, "A")
    room = {"X-Room-Key": connect(c, cam_id, "2580").json()["room_key"]}
    c.delete("/api/camera", headers=cam)
    assert c.get("/api/room", headers=room).status_code == 401
    assert connect(c, cam_id, "2580").status_code == 403


def test_pin_is_not_stored_in_plain_text(tmp_path):
    from app.db import Database
    db = Database(str(tmp_path / "w.db"))
    dev, _, _ = db.create_device("A", pin="2580")
    stored = db.pin_hash(dev.id)
    assert "2580" not in stored and stored.startswith("pbkdf2$")
