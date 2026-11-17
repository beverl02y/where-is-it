"""Korean questions get Korean answers; English questions stay English."""
import json

from fastapi.testclient import TestClient

from app.gemini_detector import parse_response
from app.korean import josa, to_english
from test_gemini import gemini_app, jpeg_bytes


def test_korean_question_to_search():
    assert to_english("내 지갑 어디 있어?")[0] == "where is my wallet"
    assert to_english("흰색 물병 어디 있어?") == ("where is my white water bottle", None, "흰색 물병")
    assert to_english("종이컵 어디 있어?") == ("where is my paper cup", None, "종이컵")
    assert to_english("유리병 어디", {"유리병": "glass bottle"})[2] == "유리병"
    assert to_english("폰 어딨어")[0] == "where is my phone"                 # one-letter word
    assert to_english("책상 위에 있던 키 어디야")[0] == "where is my keys"   # "책상" is not "책"
    assert to_english("블루투스 이어폰 어디")[0] == "where is my wireless earphones"
    assert to_english("텀블러 어디 있어", {"텀블러": "tumbler"})[0] == "where is my tumbler"
    assert to_english("선풍기 어디 있어?")[1] == "선풍기"                    # unknown item


def test_particles():
    assert josa("지갑", "은는") == "지갑은" and josa("마스크", "은는") == "마스크는"
    assert josa("휴대폰", "이가") == "휴대폰이" and josa("물병", "을를") == "물병을"


def test_gemini_korean_fields(settings):
    reply = json.dumps({"detections": [{"category": "wallet", "name": "wallet", "location": "on the desk",
                                        "confidence": 0.9, "name_ko": "지갑", "location_ko": "책상 위.",
                                        "appearance_ko": "갈색 지갑"}]})
    d = parse_response(reply, settings)[0]
    assert (d.name_ko, d.where_ko, d.appearance_ko) == ("지갑", "책상 위", "갈색 지갑")


BOTTLES = [
    {"category": "other", "name": "water bottle", "location": "on the desk", "confidence": 0.9,
     "appearance": "white water bottle", "color": "white",
     "name_ko": "물병", "location_ko": "책상 위", "appearance_ko": "흰색 물병"},
    {"category": "other", "name": "glass bottle", "location": "on the shelf", "confidence": 0.9,
     "appearance": "blue glass bottle", "color": "blue",
     "name_ko": "유리병", "location_ko": "선반 위", "appearance_ko": "파란색 유리병"},
    {"category": "wallet", "name": "wallet", "location": "on the bed", "confidence": 0.88,
     "name_ko": "지갑", "location_ko": "침대 위"},
]


def test_korean_answers_end_to_end(settings, monkeypatch):
    c, cam, room = gemini_app(settings, monkeypatch, lambda jpeg: json.dumps({"detections": BOTTLES}))
    c.post("/api/frames", headers=cam, files={"file": ("f.jpg", jpeg_bytes(), "image/jpeg")})
    ask = lambda q: c.post("/api/ask", headers=room, json={"question": q}).json()

    a = ask("내 지갑 어디 있어?")
    assert a["lang"] == "ko" and a["status"] == "current"
    assert a["message"].startswith("지갑은 침대 위에 있어요") and "신뢰도 88%" in a["message"]

    a = ask("병 어디 있어?")
    assert "2개" in a["message"] and "흰색 물병" in a["message"] and "파란색 유리병" in a["message"]
    assert "파란색 유리병은 선반 위에 있어요" in ask("파란 병 어디야")["message"]
    assert "유리병은 선반 위" in ask("유리병 어디 있어?")["message"]     # Korean name saved from Gemini

    a = ask("선풍기 어디 있어?")
    assert a["status"] == "not_found" and "선풍기를 본 적이 없어요" in a["message"]

    a = ask("Where is my wallet?")                                     # English stays English
    assert a["lang"] == "en" and a["message"].startswith("Your wallet is on the bed")


def test_older_records_without_korean(settings, monkeypatch):
    reply = json.dumps({"detections": [{"category": "phone", "name": "phone", "location": "on the bed",
                                        "confidence": 0.9}]})
    c, cam, room = gemini_app(settings, monkeypatch, lambda jpeg: reply)
    c.post("/api/frames", headers=cam, files={"file": ("f.jpg", jpeg_bytes(), "image/jpeg")})
    a = c.post("/api/ask", headers=room, json={"question": "핸드폰 어디 있어?"}).json()
    assert a["message"].startswith("핸드폰은 “on the bed” 위치에 있어요")


def test_cups_current_only_then_history(settings, monkeypatch):
    cups = [{"category": "other", "name": "cup", "location": "on the table left of the laptop", "confidence": 0.96,
             "appearance": "white paper cup with yellow sleeve", "color": "white",
             "name_ko": "종이컵", "location_ko": "노트북 왼쪽 테이블 위", "appearance_ko": "흰색 종이컵"},
            {"category": "other", "name": "cup", "location": "on the table right of the laptop", "confidence": 0.92,
             "appearance": "clear plastic cup with a yellow straw", "color": "clear",
             "name_ko": "컵", "location_ko": "노트북 오른쪽 테이블 위", "appearance_ko": "투명 플라스틱 컵"}]
    replies = iter([json.dumps({"detections": cups}), json.dumps({"detections": cups[:1]})])
    c, cam, room = gemini_app(settings, monkeypatch, lambda jpeg: next(replies))
    ask = lambda q: c.post("/api/ask", headers=room, json={"question": q}).json()["message"]
    for _ in range(2):
        c.post("/api/frames", headers=cam, files={"file": ("f.jpg", jpeg_bytes(), "image/jpeg")})
    m = ask("컵 어디 있어?")                                  # only the paper cup is in view now
    assert "노트북 왼쪽" in m and "오른쪽" not in m           # current view only
    assert "종이컵은 노트북 왼쪽" in ask("종이컵 어디 있어?")
    assert "플라스틱" in ask("플라스틱 컵 어디야")             # not in view -> its last place
