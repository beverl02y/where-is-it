"""Korean questions and answers.

A question written in Korean ("흰색 물병 어디 있어?") is turned into the English search
the rest of the system already understands ("where is my white water bottle"), and the
answer is written back in Korean. Korean item names and places come from Gemini
(name_ko, location_ko, appearance_ko); this file only holds the common words.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

HANGUL = re.compile(r"[가-힣]")


def is_korean(text: str | None) -> bool:
    return bool(text and HANGUL.search(text))


# ---------- words ----------
# Korean -> English item name (as the parser / same_items know it)
ITEMS = {
    # key items
    "안경": "glasses", "선글라스": "glasses", "안경집": "glasses case", "안경케이스": "glasses case",
    "안경 케이스": "glasses case",
    "지갑": "wallet", "카드지갑": "card holder", "카드 지갑": "card holder", "반지갑": "wallet", "장지갑": "wallet",
    "카드": "card", "학생증": "student id", "신분증": "id card", "교통카드": "transit card",
    "체크카드": "debit card", "신용카드": "credit card", "티머니": "t money card",
    "이어폰": "earphones", "에어팟": "airpods", "에어팟 케이스": "airpods case", "에어팟케이스": "airpods case",
    "버즈": "galaxy buds", "갤럭시 버즈": "galaxy buds", "헤드폰": "headphones", "헤드셋": "headphones",
    "무선 이어폰": "earbuds", "이어폰 케이스": "earphone case",
    "휴대폰": "phone", "핸드폰": "phone", "휴대전화": "phone", "스마트폰": "phone", "폰": "phone",
    "아이폰": "iphone", "갤럭시": "galaxy", "폰케이스": "phone case", "휴대폰 케이스": "phone case",
    "핸드폰 케이스": "phone case",
    "충전기": "charger", "충전선": "charging cable", "충전 케이블": "charging cable", "충전케이블": "charging cable",
    "어댑터": "adapter", "보조배터리": "power bank", "보조 배터리": "power bank",
    "머리끈": "hair tie", "머리 끈": "hair tie", "헤어밴드": "hair band", "곱창밴드": "scrunchie", "헤어끈": "hair tie",
    "케이블": "cable", "케이스": "case", "선": "cord",
    # other common things
    "물병": "water bottle", "생수병": "water bottle", "페트병": "plastic bottle", "병": "bottle",
    "텀블러": "tumbler", "마스크": "mask", "노트북": "laptop", "랩탑": "laptop", "태블릿": "tablet",
    "아이패드": "ipad", "가방": "bag", "백팩": "backpack", "책가방": "backpack", "배낭": "backpack",
    "에코백": "tote bag", "토트백": "tote bag", "쇼핑백": "shopping bag", "파우치": "pouch",
    "열쇠": "keys", "키": "keys", "차키": "car keys", "차 키": "car keys", "자동차 키": "car keys",
    "키링": "keychain", "열쇠고리": "keychain", "가방 고리": "bag charm", "가방고리": "bag charm",
    "컵": "cup", "머그컵": "mug", "머그": "mug", "시계": "watch", "손목시계": "watch",
    "모자": "cap", "야구모자": "baseball cap", "책": "book", "공책": "notebook", "노트": "notebook",
    "수첩": "notebook", "펜": "pen", "볼펜": "pen", "연필": "pencil", "필통": "pencil case",
    "리모컨": "remote control", "우산": "umbrella", "립밤": "lip balm", "립스틱": "lipstick",
    "빗": "comb", "거울": "mirror", "마우스": "mouse", "키보드": "keyboard", "반지": "ring",
    "목걸이": "necklace", "팔찌": "bracelet", "귀걸이": "earrings", "장갑": "gloves", "목도리": "scarf",
    "휴지": "tissue", "손수건": "handkerchief", "가위": "scissors", "계산기": "calculator",
    "usb": "usb", "유에스비": "usb",
}

# Korean -> English describing words (colour, size, shape, kind)
DESCRIBE = {
    "흰색": "white", "하얀색": "white", "하얀": "white", "흰": "white", "화이트": "white",
    "검은색": "black", "검정색": "black", "까만색": "black", "검은": "black", "검정": "black", "까만": "black", "블랙": "black",
    "파란색": "blue", "파랑": "blue", "파란": "blue", "블루": "blue", "하늘색": "light blue",
    "빨간색": "red", "빨강": "red", "빨간": "red", "레드": "red",
    "노란색": "yellow", "노랑": "yellow", "노란": "yellow",
    "초록색": "green", "초록": "green", "녹색": "green",
    "회색": "gray", "그레이": "gray", "은색": "silver", "실버": "silver", "금색": "gold", "골드": "gold",
    "분홍색": "pink", "분홍": "pink", "핑크": "pink", "보라색": "purple", "보라": "purple",
    "갈색": "brown", "브라운": "brown", "주황색": "orange", "주황": "orange", "남색": "navy",
    "베이지": "beige", "투명한": "clear", "투명": "clear",
    "큰": "large", "커다란": "large", "작은": "small", "조그만": "small", "긴": "long", "짧은": "short",
    "둥근": "round", "동그란": "round", "네모난": "rectangular", "사각형": "rectangular", "세모난": "triangular",
    "유선": "wired", "무선": "wireless", "블루투스": "wireless",
    "종이": "paper", "플라스틱": "plastic", "유리": "glass", "가죽": "leather", "천": "fabric",
    "금속": "metal", "쇠": "metal", "나무": "wooden", "원목": "wooden", "실리콘": "silicone", "털": "fluffy",
}

# English -> Korean, for answers
KEY_KO = {"glasses": "안경", "wallet": "지갑", "card": "카드", "earphones": "이어폰", "phone": "휴대폰",
          "charger": "충전기", "hairtie": "머리끈"}
EN_ITEM_KO = {en: ko for ko, en in reversed(list(ITEMS.items())) if len(ko) > 1}
EN_ITEM_KO.update({"face mask": "마스크", "water bottle": "물병", "keys": "열쇠", "bag": "가방",
                   "laptop": "노트북", "cup": "컵", "cap": "모자", "notebook": "공책", "tote bag": "에코백",
                   "bag charm": "가방 고리", "backpack": "백팩"})
EN_DESC_KO = {"white": "흰색", "black": "검은색", "blue": "파란색", "light blue": "하늘색", "red": "빨간색",
              "yellow": "노란색", "green": "초록색", "gray": "회색", "grey": "회색", "silver": "은색",
              "gold": "금색", "pink": "분홍색", "purple": "보라색", "brown": "갈색", "orange": "주황색",
              "navy": "남색", "beige": "베이지색", "clear": "투명한", "large": "큰", "big": "큰",
              "small": "작은", "long": "긴", "short": "짧은", "round": "둥근", "rectangular": "네모난",
              "wired": "유선", "wireless": "무선", "dark": "어두운", "light": "밝은", "airpods": "에어팟",
              "paper": "종이", "plastic": "플라스틱", "glass": "유리", "leather": "가죽", "fabric": "천",
              "metal": "금속", "wooden": "나무", "silicone": "실리콘"}

# question words that are not item names
FILLER = {"어디", "어딨어", "어딨지", "어디야", "어디에", "어디있어", "어디있지", "어디지", "어딘지", "어디서",
          "있어", "있지", "있나", "있니", "있나요", "있어요", "있을까", "있는지", "있었어", "있었지",
          "내", "제", "나의", "저의", "우리", "마지막으로", "마지막", "최근", "언제", "봤어", "봤지", "봤니",
          "본", "찾아줘", "찾아", "찾고", "찾을", "찾아봐", "알려줘", "알려", "좀", "혹시", "지금", "현재",
          "두었지", "뒀지", "놨지", "놓았지", "뒀더라", "놨더라", "뒀어", "놨어", "둔", "놓은", "잃어버렸어",
          "잃어버린", "없어", "없어졌어", "못", "찾겠어", "보여", "보여줘", "봐줘", "카메라", "방", "그",
          "이", "저", "거", "것", "게", "요", "줘", "해줘", "나", "니", "어", "였지", "더라"}

PARTICLES = ("에서는", "에서", "에게", "한테", "으로", "까지", "부터", "이랑", "이나", "랑", "하고",
             "은", "는", "이", "가", "을", "를", "도", "만", "의", "에", "로", "요", "야")


def _strip_particles(tok: str) -> str:
    for p in PARTICLES:
        if tok.endswith(p) and len(tok) > len(p):
            return tok[: -len(p)]
    return tok


def to_english(question: str, saved_ko: dict[str, str] | None = None) -> tuple[str, str | None, str | None]:
    """Korean question -> (English question, unknown Korean item word or None,
    the Korean name as the user typed it, e.g. "흰색 물병").
    saved_ko: Korean names Gemini gave to items this camera has seen ({"텀블러": "tumbler"})."""
    saved = {ko: en for ko, en in (saved_ko or {}).items() if ko not in ITEMS}
    words = {**ITEMS, **saved}
    text = " " + re.sub(r"[^\w\s]", " ", question.lower()) + " "
    original = text
    found: list[tuple[int, str, str, str]] = []     # (position, kind, english, korean as typed)

    # 1. words of two or more letters, found anywhere ("지갑은" -> 지갑), longest first
    for table, kind in ((ITEMS, "item"), (DESCRIBE, "desc"), (saved, "item")):
        for ko in sorted((k for k in table if len(k) > 1), key=len, reverse=True):
            for m in re.finditer(re.escape(ko), text):
                found.append((m.start(), kind, table[ko], ko))
            text = text.replace(ko, " " * len(ko))
    # 2. one-letter words ("폰", "키", "큰") only as a whole word, maybe with a particle
    rest = []
    for m in re.finditer(r"\S+", text):
        tok = _strip_particles(m.group())
        if tok in words and len(tok) == 1:
            found.append((m.start(), "item", words[tok], tok))
        elif tok in DESCRIBE:
            found.append((m.start(), "desc", DESCRIBE[tok], tok))
        elif HANGUL.search(tok) or tok.isalpha():
            rest.append(tok)
    found.sort()
    desc = [en for _, kind, en, _ in found if kind == "desc"]
    items = [en for _, kind, en, _ in found if kind == "item"]
    # the item exactly as typed ("종이컵", "흰색 물병"): from the first describing word to the item
    first_item = next(((pos, k) for pos, kind, _, k in found if kind == "item"), None)
    typed = None
    if first_item:
        start = min([pos for pos, kind, _, _ in found if kind == "desc" and pos < first_item[0]] + [first_item[0]])
        typed = re.sub(r"\s+", " ", original[start:first_item[0] + len(first_item[1])]).strip()
    unknown = [w for w in rest if w not in FILLER and _strip_particles(w) not in FILLER
               and not re.search(r"(어|요|지|니|나|까|줘|다|래|냐|죠|봐|해|했|었|았|있)$", w)]
    if not items:
        if unknown:
            return "", unknown[0], unknown[0]
        return "where is my " + " ".join(desc), None, None
    return "where is my " + " ".join(desc + items[:1]), None, typed


def close_items(word: str, saved_ko: dict[str, str] | None = None) -> list[str]:
    """Known Korean item names that a typo could mean: "지값" -> ["지갑"], "드폰" -> ["핸드폰", "헤드폰"].
    Only names of 2+ letters and only the closest ones, so unrelated words are not changed.
    More than one result means the typo is ambiguous: ask instead of guessing."""
    import difflib
    word = _strip_particles(word)
    if len(word) < 2 or not HANGUL.search(word):
        return []
    table = {**ITEMS, **(saved_ko or {})}
    close = difflib.get_close_matches(word, [k for k in table if len(k) >= 2 and " " not in k], n=4, cutoff=0.75)
    if not close:
        return []
    best = difflib.SequenceMatcher(None, word, close[0]).ratio()
    out, meanings = [], set()
    for c in close:
        if difflib.SequenceMatcher(None, word, c).ratio() == best and table[c] not in meanings:
            meanings.add(table[c])
            out.append(c)
    return out


# ---------- answers ----------
def has_batchim(word: str) -> bool:
    """Does the last sound end in a consonant? (decides 은/는, 이/가, 을/를)"""
    word = word.strip()
    if not word:
        return False
    ch = word[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    if ch.isdigit():
        return ch in "013678"
    return ch.lower() not in "aeiouyw”\"'"


def josa(word: str, pair: str) -> str:
    """josa("지갑", "은는") -> "지갑은"; josa("휴대폰", "이가") -> "휴대폰이"."""
    return word + (pair[0] if has_batchim(word) else pair[1])


def when_ko(local: datetime, today) -> str:
    ampm = "오전" if local.hour < 12 else "오후"
    clock = f"{ampm} {local.hour % 12 or 12}:{local.minute:02d}"
    if local.date() == today:
        return f"오늘 {clock}"
    if local.date() == today - timedelta(days=1):
        return f"어제 {clock}"
    return f"{local.month}월 {local.day}일 {clock}"


GRID_KO = {"centre": "가운데", "left side": "왼쪽", "right side": "오른쪽", "top middle": "위쪽 가운데",
           "bottom middle": "아래쪽 가운데", "top-left": "왼쪽 위", "top-right": "오른쪽 위",
           "bottom-left": "왼쪽 아래", "bottom-right": "오른쪽 아래"}


def place_ko(location: str, label: str, location_ko: str | None) -> str:
    """Korean place WITHOUT a final particle, so the sentence can add 에/에서."""
    if location_ko:
        return location_ko
    if location.startswith("view:"):
        return "카메라 화면 " + GRID_KO.get(location[5:], "안")
    if location == "unknown":
        return "알 수 없는 곳"
    return f"“{label}” 위치"          # a zone name or an older English record


def item_ko(english: str, name_ko: str | None = None) -> str:
    if name_ko:
        return name_ko
    if english in KEY_KO:
        return KEY_KO[english]
    return EN_ITEM_KO.get(english, english)


def desc_ko(words: list[str]) -> list[str]:
    return [EN_DESC_KO.get(w, w) for w in words]
