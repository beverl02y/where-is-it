"""Hybrid RAG fallback: rules first; Gemini answers only what the rules can't, from this camera's
records only, and every answer is checked in code (record ids, 75% rule, never 100%)."""
import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import Database
from app.main import create_app
from app.rag import RagAnswerer, is_open_question
from app.search import SearchEngine

NOW = datetime(2026, 11, 9, 6, 0, tzinfo=timezone.utc)          # 15:00 in Seoul


def setup(settings, reply):
    """Records: keys on the desk (x2) and shelf (x1), a bottle seen earlier, a wallet in view now,
    an unconfirmed (50%) cup. `reply(prompt)` stands in for Gemini."""
    db = Database(settings.db_path)
    dev, _, _ = db.create_device("t", "1234")

    def add(mins, items):
        rows = [dict(object=o, location="ai", location_label=loc, confidence=c, box=None, appearance=ap,
                     name_ko=nk, location_ko=lk, appearance_ko=None) for o, ap, loc, nk, lk, c in items]
        db.add_frame(NOW - timedelta(minutes=mins), rows, camera_id=dev.id, device_id=dev.id, interval_s=900)
    keys = ("keys", "silver car keys", "on the desk next to the laptop", "열쇠", "책상 위 노트북 옆", 0.9)
    add(60 * 20, [keys])
    add(60 * 8, [("keys", "silver car keys", "on the shelf by the door", "열쇠", "문 옆 선반 위", 0.88)])
    add(60 * 3, [keys, ("water bottle", "clear water bottle", "on the bedside table", "물병", "침대 옆 탁자 위", 0.92),
                 ("cup", "white mug", "on the windowsill", "컵", "창틀 위", 0.5)])
    add(0, [("wallet", "brown wallet", "on the bed", "지갑", "침대 위", 0.9)])
    prompts = []
    rag = RagAnswerer(settings, db, client=object())
    rag.call_model = lambda p: (prompts.append(p), reply(p))[1]
    eng = SearchEngine(settings, db, rag=rag)
    db.dev = dev.id                                  # remembered for ids() below
    return (lambda q: eng.ask(q, NOW, dev.id)), prompts, db


def ids(db, obj):
    return [f"R{r.id}" for r in db.history(obj, db.dev)]


def test_which_questions_go_to_rag():
    for q in ("Where do I usually leave my keys?", "what was on my desk this morning?", "열쇠 보통 어디에 둬?",
              "어디부터 찾아봐야 해?", "어제 지갑 어디 있었어?", "where is the thing I drink from?"):
        assert is_open_question(q), q
    for q in ("Where is my wallet?", "지갑 어디 있어?", "where are my white earphones", "마스크 찾아줘"):
        assert not is_open_question(q), q


def test_normal_questions_stay_with_rules(settings):
    ask, prompts, _ = setup(settings, lambda p: "{}")
    a = ask("Where is my wallet?")
    assert a.source == "rules" and a.status == "current" and not prompts       # no AI call, instant
    assert ask("지갑 어디 있어?").source == "rules" and not prompts
    assert ask("where is my phone?").source == "rules" and not prompts          # key item never seen


def test_usual_place_question_uses_records(settings):
    holder = {}

    def reply(p):
        holder["p"] = p
        return json.dumps({"answer": "Based on past camera records, you usually leave your silver car keys on the "
                                     "desk next to the laptop (seen there 2 times, last at 12:00 PM today, 90%).",
                           "status": "last_seen", "record_ids": holder["ids"]})
    ask, prompts, db = setup(settings, reply)
    holder["ids"] = ids(db, "keys")[:1]
    a = ask("Where do I usually leave my keys?")
    assert a.source == "rag" and a.status == "last_seen" and a.confirmed and a.confidence == 0.9
    assert "usual places: on the desk next to the laptop ×2, on the shelf by the door ×1" in holder["p"]
    assert "brown wallet | on the bed | 90% CONFIRMED | in current view: yes" in holder["p"]
    assert "English" in holder["p"]


def test_korean_rag_question(settings):
    ask, prompts, db = setup(settings, lambda p: json.dumps(
        {"answer": "지난 카메라 기록으로 보면 열쇠는 주로 책상 위 노트북 옆에 있었어요 (신뢰도 90%).",
         "status": "last_seen", "record_ids": ids(db, "keys")[:1]}))
    a = ask("열쇠 보통 어디에 둬?")
    assert a.source == "rag" and a.lang == "ko" and a.message.startswith("지난 카메라 기록")
    assert "Korean" in prompts[0] and "책상 위 노트북 옆" in prompts[0]


def test_vague_name_goes_to_rag(settings):
    ask, prompts, db = setup(settings, lambda p: json.dumps(
        {"answer": "You probably mean your clear water bottle: it was on the bedside table at 12:00 PM today (92%).",
         "status": "last_seen", "record_ids": ids(db, "water bottle")}))
    a = ask("where is the thing I drink water from?")
    assert a.source == "rag" and "water bottle" in a.message and a.object == "water bottle"


def test_unconfirmed_records_cannot_become_facts(settings):
    ask, _, db = setup(settings, lambda p: json.dumps(
        {"answer": "Your mug is on the windowsill (100%).", "status": "last_seen", "record_ids": ids(db, "cup")}))
    a = ask("what was on the windowsill today?")
    assert a.source == "rag" and a.status == "possible" and not a.confirmed     # 50% < 75%: forced to possible
    assert "100%" not in a.message and "99%" in a.message                       # never 100%


def test_made_up_record_falls_back_to_rules(settings):
    ask, _, _ = setup(settings, lambda p: json.dumps(
        {"answer": "Your keys are in the kitchen.", "status": "last_seen", "record_ids": ["R999"]}))
    a = ask("Where do I usually leave my keys?")
    assert a.source == "rules" and "kitchen" not in a.message


def test_place_without_records_falls_back(settings):
    ask, _, _ = setup(settings, lambda p: json.dumps(
        {"answer": "They are under the bed.", "status": "last_seen", "record_ids": []}))
    assert ask("Where do I usually leave my keys?").source == "rules"


def test_gemini_failure_falls_back(settings):
    def fail(p):
        raise TimeoutError("slow network")
    ask, _, _ = setup(settings, fail)
    a = ask("Where do I usually leave my keys?")
    assert a.source == "rules" and a.message                                    # still an answer


def test_rag_off(settings):
    settings.rag_enabled = False
    ask, prompts, _ = setup(settings, lambda p: "{}")
    assert ask("Where do I usually leave my keys?").source == "rules" and not prompts


def test_api_reports_source(settings):
    from test_api import INVITE, register
    settings.invite_code = INVITE
    c = TestClient(create_app(settings))                                        # model none -> rules only
    _, room, _ = register(c)
    a = c.post("/api/ask", headers=room, json={"question": "where is my wallet"}).json()
    assert a["source"] == "rules"
