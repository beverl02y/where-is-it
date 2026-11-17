"""Several items with the same name (two laptops): told apart by colour, size, shape."""
import json
from datetime import datetime, timedelta, timezone

from conftest import det

from app.appearance import best_matches, canon
from app.gemini_detector import parse_response

NOW = datetime(2026, 11, 6, 3, 0, tzinfo=timezone.utc)   # 12:00 PM in Seoul


def lap(appearance, color, size, where, conf=0.9, box=(0.1, 0.1, 0.3, 0.3)):
    d = det("laptop", conf, "ai", where)
    d.update(appearance=appearance, color=color, size=size, shape="rectangular", box=box)
    return d


SILVER = lap("large silver laptop", "silver", "large", "on the desk")
BLACK = lap("small black laptop", "black", "small", "on the bed", box=(0.6, 0.6, 0.8, 0.8))


def test_gemini_keeps_both_laptops_with_their_looks(settings):
    items = [{"category": "other", "name": "laptop", "box_2d": [100, 100, 300, 300], "confidence": 0.9,
              "location": "on the desk", "appearance": "Large Silver Laptop", "color": "silver",
              "size": "large", "shape": "rectangular"},
             {"category": "other", "name": "laptop", "box_2d": [600, 600, 800, 800], "confidence": 0.88,
              "location": "on the bed", "appearance": "small black laptop", "color": "black",
              "size": "small", "shape": "rectangular"},
             # the same silver laptop listed twice (overlapping box) is kept once
             {"category": "other", "name": "laptop", "box_2d": [102, 101, 301, 300], "confidence": 0.7,
              "location": "on the desk", "appearance": "silver laptop", "color": "silver",
              "size": "large", "shape": "rectangular"}]
    dets = parse_response(json.dumps({"detections": items}), settings)
    assert [d.appearance for d in dets] == ["large silver laptop", "small black laptop"]
    assert dets[1].size == "small" and dets[1].color == "black"


def test_two_visible_are_listed(engine, db):
    db.add_frame(NOW - timedelta(seconds=30), [SILVER, BLACK])
    a = engine.ask("Where is my laptop?", now=NOW)
    assert a.status == "current" and "I can see 2 laptops" in a.message
    assert "large silver laptop on the desk" in a.message and "small black laptop on the bed" in a.message
    assert "Which one is yours?" in a.message


def test_describing_words_pick_one(engine, db):
    db.add_frame(NOW - timedelta(seconds=30), [SILVER, BLACK])
    a = engine.ask("where is my black laptop", now=NOW)
    assert a.status == "current" and "small black laptop is on the bed" in a.message
    a = engine.ask("where's my big laptop?", now=NOW)                 # big = large
    assert "large silver laptop is on the desk" in a.message
    a = engine.ask("where is my grey laptop", now=NOW)                 # grey/silver: no exact colour
    assert a.status == "not_found" and "I have seen" in a.message and "silver laptop" in a.message


def test_history_lists_both_and_filters(engine, db):
    db.add_frame(NOW - timedelta(hours=2), [SILVER, BLACK])
    db.add_frame(NOW - timedelta(seconds=10), [])                     # now neither is visible
    a = engine.ask("Where is my laptop?", now=NOW)
    assert a.status == "last_seen" and "2 different laptops" in a.message
    a = engine.ask("Where is my small laptop?", now=NOW)
    assert a.status == "last_seen" and "small black laptop was last seen on the bed" in a.message


def test_key_items_too(engine, db):
    white = det("phone", 0.92, "ai", "on the chair"); white.update(appearance="white phone", color="white")
    black = det("phone", 0.9, "ai", "on the desk"); black.update(appearance="black phone", color="black")
    db.add_frame(NOW - timedelta(seconds=5), [white, black])
    a = engine.ask("where is my white phone", now=NOW)
    assert a.status == "current" and "white phone is on the chair" in a.message
    assert "I can see 2 phones" in engine.ask("where is my phone", now=NOW).message


def test_overview_shows_each(engine, db):
    db.add_frame(NOW - timedelta(minutes=5), [SILVER, BLACK])
    row = next(r for r in engine.overview(now=NOW) if r["object"] == "laptop")
    assert row["location"] == "large silver laptop on the desk; small black laptop on the bed"


def test_word_matching():
    assert canon("Big Round grey") == {"large", "round", "gray"}
    class R:  # minimal record
        def __init__(self, a): self.appearance, self.color, self.size, self.shape = a, None, None, None
    recs = [R("tall clear water bottle"), R("short blue water bottle")]
    assert [r.appearance for r in best_matches(recs, ["blue"])] == ["short blue water bottle"]
    assert [r.appearance for r in best_matches(recs, ["long", "transparent"])] == ["tall clear water bottle"]
    assert best_matches(recs, ["red"]) == []
