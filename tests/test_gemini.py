"""Gemini detection: parsing, location phrases, open-vocabulary search, failures.
Gemini itself is replaced by canned answers (no network, no API key needed)."""
import json

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.gemini_detector import (DetectionUnavailable, GeminiDetector, build_prompt,
                                 parse_response, response_schema)
from app.main import create_app
from test_api import INVITE, register


def jpeg_bytes():
    ok, buf = cv2.imencode(".jpg", np.full((720, 1280, 3), 128, np.uint8))
    return buf.tobytes()


def answer(*objs):
    return json.dumps({"detections": list(objs)})


GLASSES = {"category": "glasses", "name": "glasses", "box_2d": [600, 100, 700, 200],
           "confidence": 0.92, "location": "On the desk next to the laptop."}
BOTTLE = {"category": "other", "name": "Water Bottle", "box_2d": [300, 700, 600, 760],
          "confidence": 0.88, "location": "on the bedside table"}
EARBUDS = {"category": "earphones", "name": "airpods case", "box_2d": [650, 400, 690, 440],
           "confidence": 0.55, "location": "on the desk near the mug"}


def test_parse_converts_boxes_and_cleans_text(settings):
    dets = {d.object: d for d in parse_response(answer(GLASSES, BOTTLE, EARBUDS), settings)}
    g = dets["glasses"]
    assert g.box == (0.1, 0.6, 0.2, 0.7)              # [ymin,xmin,ymax,xmax]/1000 -> x1,y1,x2,y2
    assert g.where == "on the desk next to the laptop"  # lower-cased, no full stop
    assert dets["water bottle"].label == "water bottle"  # other items kept under their name
    assert dets["earphones"].confidence == 0.55


def test_parse_rules(settings):
    sure = dict(GLASSES, confidence=1.0)
    faint = dict(BOTTLE, confidence=0.05)                     # below store_threshold
    broken = dict(GLASSES, box_2d=[700, 200, 600, 100])        # inverted box
    dets = parse_response(answer(sure, faint, broken), settings)
    assert [d.object for d in dets] == ["glasses"] and dets[0].confidence == 0.99   # never 100%
    settings.detect_all_objects = False
    assert [d.object for d in parse_response(answer(GLASSES, BOTTLE), settings)] == ["glasses"]
    with pytest.raises(DetectionUnavailable):
        parse_response("not json", settings)


def test_prompt_and_schema_cover_key_items(settings):
    p = build_prompt(settings)
    for word in ("glasses", "wallet", "earphones", "AirPods", "hair tie", "box_2d", "0-1000", "Never use 1.0"):
        assert word in p
    item = response_schema(settings)["properties"]["detections"]["items"]
    assert item["required"] == ["category", "name", "location", "confidence"]
    assert item["properties"]["category"]["enum"] == list(settings.objects) + ["other"]
    for optional in ("box_2d", "appearance", "color", "size", "shape"):
        assert optional in item["properties"] and optional not in item["required"]


def test_only_required_fields(settings):
    """Gemini may send just category, name, location, confidence (no box)."""
    minimal = {"category": "wallet", "name": "wallet", "location": "inside the open drawer", "confidence": 0.8}
    other = {"category": "other", "name": "Car Keys", "location": "on the shelf", "confidence": 0.9}
    dets = parse_response(answer(minimal, other, dict(minimal)), settings)   # wallet listed twice
    assert [(d.object, d.box, d.where) for d in dets] == [("wallet", None, "inside the open drawer"),
                                                          ("keys", None, "on the shelf")]   # same_items: car keys -> keys


def test_old_answer_format_still_read(settings):
    old = json.dumps({"objects": [{"category": "phone", "label": "phone", "box_2d": [0, 0, 100, 100],
                                   "confidence": 0.9, "location": "on the desk"}]})
    assert parse_response(old, settings)[0].label == "phone"


def test_frame_without_boxes(settings, monkeypatch):
    reply = lambda jpeg: answer({"category": "glasses", "name": "glasses", "location": "on the bookshelf",
                                 "confidence": 0.9})
    c, cam, room = gemini_app(settings, monkeypatch, reply)
    r = c.post("/api/frames", headers=cam, files={"file": ("f.jpg", jpeg_bytes(), "image/jpeg")})
    assert r.status_code == 200 and r.json()["detections"][0]["location"] == "on the bookshelf"
    a = c.post("/api/ask", headers=room, json={"question": "where are my glasses"}).json()
    assert a["status"] == "current" and "on the bookshelf" in a["message"]


def gemini_app(settings, monkeypatch, reply):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    settings.model_type = "gemini"
    settings.invite_code = INVITE
    det = GeminiDetector(settings)
    monkeypatch.setattr(det, "call_gemini", reply)
    c = TestClient(create_app(settings, detector=det))
    cam, room, _ = register(c)
    return c, cam, room


def test_frame_to_answers_with_gemini(settings, monkeypatch):
    c, cam, H = gemini_app(settings, monkeypatch, lambda jpeg: answer(GLASSES, BOTTLE, EARBUDS))
    r = c.post("/api/frames", headers=cam, files={"file": ("f.jpg", jpeg_bytes(), "image/jpeg")}).json()
    locs = {d["object"]: d["location"] for d in r["detections"]}
    assert locs["glasses"] == "on the desk next to the laptop"

    a = c.post("/api/ask", headers=H, json={"question": "Where are my glasses?"}).json()
    assert a["status"] == "current" and "on the desk next to the laptop" in a["message"]

    a = c.post("/api/ask", headers=H, json={"question": "where did I leave my water bottle"}).json()
    assert a["status"] == "current" and "on the bedside table" in a["message"]
    a = c.post("/api/ask", headers=H, json={"question": "where is my bottle?"}).json()
    assert a["status"] == "current"                                   # partial name still matches

    a = c.post("/api/ask", headers=H, json={"question": "Where are my earphones?"}).json()
    assert a["status"] == "possible" and not a["confirmed"]           # 55% < 75%: possibility only

    a = c.post("/api/ask", headers=H, json={"question": "I can't find my keys"}).json()
    assert a["status"] == "not_found" and "haven't seen any keys" in a["message"]

    names = [o["display"] for o in c.get("/api/objects", headers=H).json()["objects"]]
    assert "water bottle" in names and "glasses" in names


def test_gemini_failure_saves_nothing(settings, monkeypatch):
    def fail(jpeg):
        raise DetectionUnavailable("rate limit or free-tier quota reached (429)")
    c, cam, room = gemini_app(settings, monkeypatch, fail)
    r = c.post("/api/frames", headers=cam, files={"file": ("f.jpg", jpeg_bytes(), "image/jpeg")})
    assert r.status_code == 503 and "quota" in r.json()["detail"] and r.headers["retry-after"] == "30"
    assert c.get("/api/room", headers=room).json()["photos"] == 0   # no empty frame pretending "nothing visible"


def test_missing_api_key(settings, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    settings.model_type = "gemini"
    settings.invite_code = INVITE
    c = TestClient(create_app(settings, detector=GeminiDetector(settings)))
    cam, _, _ = register(c)
    assert "GEMINI_API_KEY missing" in c.get("/api/health").json()["detector"]
    r = c.post("/api/frames", headers=cam, files={"file": ("f.jpg", jpeg_bytes(), "image/jpeg")})
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]


def test_image_is_shrunk_before_sending(settings, monkeypatch):
    seen = {}

    def capture(jpeg):
        parts = jpeg if isinstance(jpeg, list) else [jpeg]
        seen["shapes"] = [cv2.imdecode(np.frombuffer(j, np.uint8), cv2.IMREAD_COLOR).shape for j in parts]
        return answer()
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    det = GeminiDetector(settings)
    monkeypatch.setattr(det, "call_gemini", capture)
    assert det.detect(np.zeros((3000, 4000, 3), np.uint8)) == []
    whole, *zoomed = seen["shapes"]
    assert max(whole[:2]) == settings.gemini_max_image_side
    assert len(zoomed) == settings.gemini_tiles ** 2 == 4                 # 4 zoomed-in parts
    assert all(1200 < max(s[:2]) <= settings.gemini_max_image_side for s in zoomed)   # more detail
    settings.gemini_tiles = 1                                             # tiles: 1 -> one photo only
    det = GeminiDetector(settings)
    monkeypatch.setattr(det, "call_gemini", capture)
    det.detect(np.zeros((3000, 4000, 3), np.uint8))
    assert len(seen["shapes"]) == 1


def test_prompt_mentions_distance_and_zoom(settings):
    p = build_prompt(settings)
    assert "3 metres" in p and "Image 1 is the whole photo" in p and "ONCE" in p
