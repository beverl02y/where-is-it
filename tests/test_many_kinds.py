"""Several items of one kind: white + blue bottle, AirPods + wired earphones.
Asking for the kind ("bottle") answers with every one of them."""
import json
from datetime import datetime, timedelta, timezone

from app.db import Database
from app.gemini_detector import parse_response
from app.search import SearchEngine

WB = ("water bottle", "white water bottle", "white", "on the desk")
BB = ("water bottle", "blue water bottle", "blue", "on the shelf")
GB = ("glass bottle", "blue glass bottle", "blue", "on the shelf")
AP = ("earphones", "white airpods case", "white", "on the desk")
WE = ("earphones", "black wired earphones", "black", "on the bed")


def engine(settings, frames):
    db = Database(settings.db_path)
    dev, _, _ = db.create_device("t", "1234")
    now = datetime.now(timezone.utc)
    for mins, items in frames:
        rows = [{"object": o, "location": "ai", "location_label": loc, "confidence": 0.9, "box": None,
                 "appearance": ap, "color": c} for o, ap, c, loc in items]
        db.add_frame(now - timedelta(minutes=mins), rows, camera_id=dev.id, device_id=dev.id, interval_s=60)
    eng = SearchEngine(settings, db)
    return lambda q: eng.ask(q, now, dev.id)


def test_different_names_answered_together(settings):
    ask = engine(settings, [(0, [WB, GB])])
    a = ask("where is my bottle?")
    assert a.status == "current" and "white water bottle on the desk" in a.message \
        and "blue glass bottle on the shelf" in a.message
    assert "glass bottle" in ask("where is my blue bottle").message
    assert "glass" not in ask("where is my water bottle").message


def test_seen_at_different_times_lists_each(settings):
    a = engine(settings, [(30, [WB]), (10, [BB]), (0, [])])("where is my bottle")
    assert a.status == "last_seen" and "2 different" in a.message
    assert "white water bottle on the desk" in a.message and "blue water bottle on the shelf" in a.message


def test_visible_now_tells_only_the_current_view(settings):
    a = engine(settings, [(20, [GB]), (0, [WB])])("where is my bottle")
    assert a.status == "current" and "on the desk" in a.message
    assert "shelf" not in a.message and "also" not in a.message            # no older records


def test_same_item_not_listed_twice(settings):
    a = engine(settings, [(30, [WB]), (20, [WB]), (10, [WB]), (0, [])])("where is my bottle")
    assert a.status == "last_seen" and "different" not in a.message


def test_earphones(settings):
    ask = engine(settings, [(30, [AP]), (10, [WE]), (0, [])])
    a = ask("where are my earphones")
    assert "white airpods case on the desk" in a.message and "black wired earphones on the bed" in a.message
    assert "on the desk" in ask("where are my airpods").message and "on the bed" not in ask("where are my airpods").message
    assert "on the bed" in ask("where are my wired earphones").message


def test_bag_does_not_match_bag_charm(settings):
    ask = engine(settings, [(0, [("bag charm", "pink bag charm", "pink", "on the backpack"),
                                 ("tote bag", "beige tote bag", "beige", "on the chair")])])
    a = ask("where is my bag")
    assert "tote bag" in a.message and "charm" not in a.message


def test_airpods_sent_as_other_go_to_earphones(settings):
    reply = json.dumps({"detections": [{"category": "other", "name": "airpods", "location": "on the desk",
                                        "confidence": 0.9}]})
    assert [d.object for d in parse_response(reply, settings)] == ["earphones"]
