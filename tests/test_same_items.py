"""One name per kind of item: "face mask", "facial mask", "mask", "facemask" are the same."""
import json
from datetime import datetime, timezone

from app.appearance import item_name
from app.db import Database
from app.gemini_detector import parse_response
from app.main import create_app
from app.search import SearchEngine
from fastapi.testclient import TestClient


def test_names_are_merged(settings):
    for name in ("mask", "masks", "facial mask", "facemask", "face masks", "kf94 mask", "Face Mask"):
        assert item_name(name.lower(), settings.same_items) == "face mask"
    assert item_name("laptop", settings.same_items) == "laptop"          # not listed: unchanged


def test_gemini_names_stored_as_one(settings):
    reply = json.dumps({"detections": [{"category": "other", "name": "Facial Mask", "location": "on the bag",
                                        "confidence": 0.9}]})
    assert [d.object for d in parse_response(reply, settings)] == ["face mask"]


def ask_all(settings, stored_name, appearance=None):
    db = Database(settings.db_path)
    dev, _, _ = db.create_device("t", "1234")
    now = datetime.now(timezone.utc)
    db.add_frame(now, [{"object": stored_name, "location": "ai", "location_label": "on the black cloth bag",
                        "confidence": 0.9, "box": None, "appearance": appearance}],
                 camera_id=dev.id, device_id=dev.id, interval_s=900)
    eng = SearchEngine(settings, db)
    return {q: eng.ask(q, now, dev.id) for q in
            ("where is my mask?", "where is my face mask", "where is my facial mask", "where's my facemask",
             "where is my white mask")}


def test_every_way_of_asking_finds_it(settings):
    for q, a in ask_all(settings, "face mask").items():
        assert a.status == "current" and "on the black cloth bag" in a.message, q


def test_colour_used_only_when_known(settings):
    a = ask_all(settings, "face mask", appearance="black cloth face mask")
    assert a["where is my mask?"].status == "current"
    assert a["where is my white mask"].status == "not_found"            # it is black, not white
    assert "black cloth face mask" in a["where is my white mask"].message  # ...and it says what it saw


def test_old_records_renamed_on_start(settings):
    db = Database(settings.db_path)
    dev, _, _ = db.create_device("t", "1234")
    db.add_frame(datetime.now(timezone.utc), [{"object": "facial mask", "location": "ai", "location_label": "on the bed",
                                               "confidence": 0.9, "box": None}],
                 camera_id=dev.id, device_id=dev.id, interval_s=900)
    TestClient(create_app(settings))
    assert db.known_objects(dev.id) == ["face mask"]
