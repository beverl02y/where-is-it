"""Tests that map one-to-one onto SPEC section 6 (acceptance criteria)."""
from datetime import datetime, timedelta, timezone

from conftest import det

NOW = datetime(2026, 10, 28, 1, 0, tzinfo=timezone.utc)   # 10:00 AM in Seoul


def test_ac03_current_detection(engine, db):
    db.add_frame(NOW - timedelta(seconds=30), [det("glasses", 0.91, "bedside_table", "on the bedside table")])
    a = engine.ask("Where are my glasses?", now=NOW)
    assert a.status == "current" and a.confirmed
    assert "on the bedside table" in a.message and "91%" in a.message and "9:59 AM" in a.message


def test_ac04_ac05_last_seen_when_not_currently_visible(engine, db):
    db.add_frame(NOW - timedelta(hours=1, minutes=30), [det("glasses", 0.88, "bed", "beside the bed")])
    db.add_frame(NOW - timedelta(seconds=10), [det("phone", 0.95)])          # current view, no glasses
    a = engine.ask("Where are my glasses?", now=NOW)
    assert a.status == "last_seen"
    assert "not visible in the current camera view" in a.message
    assert "beside the bed at 8:30 AM today" in a.message


def test_below_75_never_confirmed(engine, db):
    db.add_frame(NOW - timedelta(seconds=10), [det("wallet", 0.74)])
    a = engine.ask("Where is my wallet?", now=NOW)
    assert a.status == "possible" and not a.confirmed
    assert a.message.count("Possibility (not confirmed)") == 1


def test_ac06_possibility_after_confirmed_sighting(engine, db):
    db.add_frame(NOW - timedelta(hours=3), [det("charger", 0.90, "desk", "on the desk")])
    db.add_frame(NOW - timedelta(hours=1), [det("charger", 0.55, "bed", "on the bed")])
    a = engine.ask("where is my charger", now=NOW)
    assert a.status == "last_seen" and "on the desk" in a.message
    assert a.suggestion and "might be on the bed" in a.suggestion


def test_old_low_confidence_not_suggested(engine, db):
    db.add_frame(NOW - timedelta(hours=5), [det("charger", 0.55, "bed", "on the bed")])
    db.add_frame(NOW - timedelta(hours=2), [det("charger", 0.90)])
    a = engine.ask("where is my charger", now=NOW)
    assert a.suggestion is None


def test_safe_failure_no_record(engine, db):
    db.add_frame(NOW - timedelta(seconds=5), [])
    a = engine.ask("where is my hair tie", now=NOW)
    assert a.status == "not_found"
    assert "couldn't find" in a.message and "outside the camera's view" in a.message


def test_stale_camera_is_reported(engine, db):
    db.add_frame(NOW - timedelta(hours=2), [det("wallet", 0.9)])
    a = engine.ask("where is my wallet", now=NOW)
    assert a.status == "last_seen" and "hasn't sent a recent image" in a.message


def test_ambiguous_asks_to_clarify(engine):
    a = engine.ask("where is my cable", now=NOW)
    assert a.status == "clarify" and "charger" in a.message and "earphones" in a.message


def test_never_100_percent_and_no_blame(engine, db):
    db.add_frame(NOW - timedelta(seconds=5), [det("phone", 0.999)])
    a = engine.ask("where is my phone", now=NOW)
    assert "100%" not in a.message and "99%" in a.message
    db.add_frame(NOW - timedelta(seconds=1), [])
    for q in ["where is my phone", "where is my wallet", "where are my glasses"]:
        m = engine.ask(q, now=NOW).message.lower()
        for word in ("someone", "pet", "cat", "dog", "roommate", "stole"):
            assert word not in m


def test_response_time_target(engine, db):
    for i in range(500):
        db.add_frame(NOW - timedelta(minutes=i), [det("wallet", 0.9), det("phone", 0.6)])
    a = engine.ask("where is my wallet", now=NOW)
    assert a.elapsed_ms < 2000


def test_slow_camera_interval_still_counts_as_current(engine, db):
    # one photo every 15 min: a 10-minute-old photo is still the current view
    db.add_frame(NOW - timedelta(minutes=10), [det("phone", 0.9)], interval_s=900)
    a = engine.ask("where is my phone", now=NOW)
    assert a.status == "current"
    # ...but after 25 minutes with no photo, the camera is reported as not sending
    db.add_frame(NOW - timedelta(minutes=25), [], interval_s=900)
    a = engine.ask("where is my phone", now=NOW + timedelta(minutes=16))
    assert a.status == "last_seen" and "hasn't sent a recent image" in a.message


def test_fast_camera_uses_default_window(engine, db):
    db.add_frame(NOW - timedelta(minutes=5), [det("phone", 0.9)], interval_s=20)
    a = engine.ask("where is my phone", now=NOW)
    assert a.status == "last_seen"      # 5 min old > 2 min window for a 20 s camera
