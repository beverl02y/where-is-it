from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

GOLDEN = Path(os.environ.get("WIIA_GOLDEN", Path(__file__).parent / "harness" / "golden_cases.yaml"))
SPEC = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
CASES = SPEC["cases"]
MIN_CONF = float(SPEC["minimum_confirmed_confidence"])


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _key(name: str) -> str:
    return name.strip().lower()


def _load(db, records: list[dict]) -> dict[int, str]:
    """One camera frame per fixture record. Returns detection id -> fixture_id."""
    ids: dict[int, str] = {}
    for r in records:
        frame_id = db.add_frame(_ts(r["timestamp"]), [{
            "object": _key(r["object"]), "location": r["location"],
            "location_label": f"on the {r['location']}", "confidence": float(r["confidence"]),
            "box": (0.1, 0.1, 0.2, 0.2),
        }])
        for d in db.instances_in_frame(frame_id, _key(r["object"])):
            ids[d.id] = r["fixture_id"]
    return ids


def _now(records: list[dict]) -> datetime:
    """Well after the newest record, so no photo counts as the current view."""
    if not records:
        return datetime.fromisoformat("2026-10-28T18:00:00+09:00")
    return max(_ts(r["timestamp"]) for r in records) + timedelta(hours=4)


def test_golden_file_is_valid():
    assert MIN_CONF == 0.75
    names = [c["name"] for c in CASES]
    assert len(names) == len(set(names)), "duplicate case names"
    for c in CASES:
        fixtures = {r["fixture_id"] for r in c["context"]["records"]}
        assert c["expect_record"] is None or c["expect_record"] in fixtures, c["name"]
        assert set(c.get("must_exclude", [])) <= fixtures, c["name"]


def test_server_threshold_matches_golden(settings):
    assert settings.confirm_threshold == MIN_CONF


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_record_selection(case, db, settings):
    ctx = case["context"]
    ids = _load(db, ctx["records"])
    got = db.last_confirmed(_key(ctx["object_name"]), settings.confirm_threshold)
    got_id = ids.get(got.id) if got else None

    assert got_id == case["expect_record"], f"{case['name']}: selected {got_id}, expected {case['expect_record']}"
    if got is not None and "must_min_confidence" in case:
        assert got.confidence >= case["must_min_confidence"]
    assert got_id not in case.get("must_exclude", [])


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_user_answer(case, db, engine):
    ctx = case["context"]
    records = ctx["records"]
    _load(db, records)
    obj = _key(ctx["object_name"])
    ans = engine.ask(f"Where is my {obj}?", now=_now(records)).to_dict()
    msg = ans["message"]

    # A sighting is historical evidence, never "it is there now".
    assert ans["status"] != "current", msg

    want = next((r for r in records if r["fixture_id"] == case["expect_record"]), None)
    if want is not None:
        assert ans["status"] == "last_seen", msg
        assert ans["confirmed"] is True
        assert want["location"] in (ans["location"] or ""), msg
        assert _ts(ans["seen_at"]) == _ts(want["timestamp"])
        assert ans["confidence"] == pytest.approx(want["confidence"])
        assert ans["confidence"] >= case.get("must_min_confidence", MIN_CONF)
        assert "last seen" in msg.lower(), msg
    else:
        # No reliable record: no confirmed location, no invented record.
        assert ans["status"] not in ("current", "last_seen"), msg
        assert ans["confirmed"] is not True, msg
        if not records:
            assert ans["location"] is None and ans["seen_at"] is None and ans["confidence"] is None, msg

    # Excluded records must not be presented as the confirmed answer.
    for r in records:
        if r["fixture_id"] in case.get("must_exclude", []) and ans["confirmed"]:
            assert _ts(ans["seen_at"]) != _ts(r["timestamp"]), f"used excluded {r['fixture_id']}: {msg}"

    # Below-threshold scores must not be rounded up to the threshold (GC-03).
    for r in records:
        if float(r["confidence"]) < MIN_CONF:
            shown = [int(p) for p in re.findall(r"(\d+)%", msg)]
            assert all(p < round(MIN_CONF * 100) for p in shown), f"{r['confidence']} shown as {shown}%: {msg}"
