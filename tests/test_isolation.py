"""Two people, two camera phones, same kinds of objects: their records must never mix."""
from test_api import client, photo, register

from app.detector import Detection


class SwitchingDetector:
    """Returns whatever the test puts in `.next` (simulates two different rooms)."""
    name = "fake"

    def __init__(self):
        self.next = []

    def detect(self, image):
        return self.next


def ask(c, room, q):
    return c.post("/api/ask", headers=room, json={"question": q}).json()


def test_two_cameras_never_mix(settings, monkeypatch):
    det = SwitchingDetector()
    c = client(settings, monkeypatch, det)
    me_cam, me_room, me_id = register(c, "Lae's room")
    her_cam, her_room, her_id = register(c, "Minji's room")
    assert me_id != her_id

    det.next = [Detection("glasses", 0.9, (0.1, 0.1, 0.2, 0.2), where="on the desk next to the laptop")]
    photo(c, me_cam)
    det.next = [Detection("glasses", 0.9, (0.6, 0.6, 0.7, 0.7), where="on the bed near the pillow"),
                Detection("water bottle", 0.9, (0.3, 0.3, 0.4, 0.4), where="on the shelf")]
    photo(c, her_cam)

    # same object type, different answers
    assert "on the desk next to the laptop" in ask(c, me_room, "Where are my glasses?")["message"]
    assert "on the bed near the pillow" in ask(c, her_room, "Where are my glasses?")["message"]
    # her extra item does not exist in my room
    assert ask(c, me_room, "where is my water bottle")["status"] == "not_found"
    assert ask(c, her_room, "where is my water bottle")["status"] == "current"
    # overviews and counts are separate
    mine = {o["object"]: o["location"] for o in c.get("/api/objects", headers=me_room).json()["objects"]}
    assert mine["glasses"] == "on the desk next to the laptop" and "water bottle" not in mine
    assert c.get("/api/room", headers=me_room).json()["device"]["name"] == "Lae's room"
    assert c.get("/api/room", headers=me_room).json()["photos"] == 1


def test_zones_and_test_photos_are_per_camera(settings, monkeypatch):
    det = SwitchingDetector()
    c = client(settings, monkeypatch, det)
    a_cam, a_room, _ = register(c, "A")
    b_cam, b_room, _ = register(c, "B")
    zone = {"zones": [{"name": "drawer", "label": "in my drawer", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}]}
    c.post("/api/zones", headers=a_room, json=zone)
    assert c.get("/api/zones", headers=b_room).json()["zones"] == []

    det.next = [Detection("phone", 0.9, (0.4, 0.4, 0.5, 0.5), where="on the table")]
    assert photo(c, a_cam).json()["detections"][0]["location"] == "in my drawer"
    assert photo(c, b_cam).json()["detections"][0]["location"] == "on the table"

    c.post("/api/test-photos", headers=a_cam, files={"file": ("p.jpg", b"A-photo", "image/jpeg")})
    assert c.get("/api/test-photos/latest", headers=a_room).content == b"A-photo"
    assert c.get("/api/test-photos/latest", headers=b_room).status_code == 404


def test_keys_only_do_their_own_job(settings, monkeypatch):
    c = client(settings, monkeypatch, SwitchingDetector())
    cam, room, _ = register(c)
    assert c.post("/api/ask", headers=cam, json={"question": "where is my phone"}).status_code == 401
    assert c.get("/api/objects", headers=cam).status_code == 401
    assert photo(c, room).status_code == 401
    assert c.post("/api/camera/room-key", headers=room).status_code == 401
    assert c.delete("/api/camera", headers=room).status_code == 401


def test_new_room_link_disables_old_one(settings, monkeypatch):
    c = client(settings, monkeypatch, SwitchingDetector())
    cam, room, _ = register(c)
    new_key = c.post("/api/camera/room-key", headers=cam).json()["room_key"]
    assert c.get("/api/room", headers=room).status_code == 401
    assert c.get("/api/room", headers={"X-Room-Key": new_key}).status_code == 200


def test_delete_history_and_remove_camera(settings, monkeypatch):
    det = SwitchingDetector()
    c = client(settings, monkeypatch, det)
    a_cam, a_room, a_id = register(c, "A")
    b_cam, b_room, _ = register(c, "B")
    det.next = [Detection("wallet", 0.9, (0.4, 0.4, 0.5, 0.5), where="on the desk")]
    photo(c, a_cam); photo(c, b_cam)

    assert c.delete("/api/room/history", headers=a_room).json() == {"deleted_photos": 1}
    assert ask(c, a_room, "where is my wallet")["status"] == "not_found"
    assert ask(c, b_room, "where is my wallet")["status"] == "current"      # B untouched

    assert c.delete("/api/camera", headers=a_cam).json() == {"removed": a_id}
    assert c.get("/api/room", headers=a_room).status_code == 401
    assert photo(c, a_cam).status_code == 401
    assert ask(c, b_room, "where is my wallet")["status"] == "current"


def test_admin_sees_cameras_not_records(settings, monkeypatch):
    det = SwitchingDetector()
    c = client(settings, monkeypatch, det)
    cam, room, dev = register(c, "Lae's room")
    det.next = [Detection("glasses", 0.9, (0.1, 0.1, 0.2, 0.2), where="on the desk")]
    photo(c, cam)
    admin = {"X-API-Key": "test-key"}
    devices = c.get("/api/admin/devices", headers=admin).json()["devices"]
    assert devices[0]["name"] == "Lae's room" and devices[0]["photos"] == 1
    assert "glasses" not in str(devices) and "desk" not in str(devices)
    assert c.delete(f"/api/admin/devices/{dev}", headers=admin).json() == {"removed": dev}
    assert c.get("/api/room", headers=room).status_code == 401
