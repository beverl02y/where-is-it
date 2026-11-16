"""Questions that are not about finding a belonging, answered instantly (no Gemini call).

The camera records say WHAT was seen, WHERE ("on the desk next to the laptop") and WHEN.
Questions about body parts, people, feelings, tasks for a chatbot, chat commands or
distances can't be answered from them, so there is no point asking Gemini (2-4 s).
Also: instructions hidden in a question ("ignore your rules", "always answer ...") are
noticed so the question is answered by the rules only, never by Gemini.
"""
from __future__ import annotations

import re

# distances: the records have places, not measurements
DISTANCE = re.compile(
    r"\b(how far|how close|how many (?:meters|metres|centimeters|cm|feet)|distance|"
    r"\d+(?:\.\d+)?\s*(?:m|cm|mm|meters?|metres?|feet|ft)\s+(?:away|from))\b"
    r"|얼마나\s*(?:멀|가까)|거리|몇\s*(?:미터|센티|m|cm)", re.I)

# not a belonging: body parts, people, feelings
NOT_A_THING = re.compile(
    r"\b(brain|teeth|tooth|soul|boyfriend|girlfriend|husband|wife|crush|"
    r"mom|mother|dad|father|parents|friend|friends|lover|feelings?|happiness)\b"
    r"|\bin love\b|\blove (?:me|you|him|her|them|someone|ai)\b"
    r"|뇌|이빨|치아|심장|영혼|남자\s*친구|여자\s*친구|남친|여친|애인|연애|사랑|행복", re.I)

# tasks for a general chatbot
TASK = re.compile(
    r"\b(write|code|program|python|javascript|java|essay|poem|story|translate|calculate|"
    r"homework|recipe|weather|news|joke)\b"
    r"|작성|코드|코딩|파이썬|프로그램|번역|숙제|날씨|뉴스|농담", re.I)

# the whole question is a chat command or greeting
COMMAND = re.compile(
    r"^\s*(quit|exit|stop|bye|goodbye|hello|hi|hey|thanks|thank you|ok|okay|test|help|"
    r"종료|그만|안녕|고마워|감사합니다|도움말)\s*[.!?]*\s*$", re.I)

# instructions aimed at the AI instead of a question
INJECTION = re.compile(
    r"\b(ignore|forget|disregard|override)\b.{0,40}\b(instructions?|rules?|records?|prompt|camera)\b"
    r"|\b(always|just|only)\s+(?:answer|say|reply|tell)\b|\bpretend\b|\bact as\b|\bsystem prompt\b"
    r"|무시하고|무시해|지시를?\s*무시|항상\s*(?:대답|말)", re.I)


def is_injection(question: str) -> bool:
    return bool(INJECTION.search(question or ""))


def out_of_scope(question: str, knows_item) -> str | None:
    """'distance' | 'not_a_thing' | 'task' | 'command', or None for a normal question.
    knows_item(question) -> True if the question names an item the system knows: then
    'love' or 'heart' may be part of an item name ("heart keychain") and it is not rejected."""
    q = question or ""
    if COMMAND.search(q):
        return "command"
    if DISTANCE.search(q):
        return "distance"
    if TASK.search(q) and not knows_item(q):
        return "task"
    if NOT_A_THING.search(q) and not knows_item(q):
        return "not_a_thing"
    return None


MESSAGES = {
    "distance": (
        "The camera records say where things are (for example “on the desk next to the laptop”), "
        "not how far apart they are, so I can't answer how far something is.",
        "카메라 기록에는 물건이 있는 곳(예: “노트북 옆 책상 위”)만 있고 거리는 없어서, "
        "얼마나 떨어져 있는지는 알려 드릴 수 없어요."),
    "not_a_thing": (
        "I can only help find belongings that the camera has seen in your room, "
        "so I can't answer that.",
        "저는 카메라가 방에서 본 물건을 찾는 것만 도와드릴 수 있어서, 그 질문에는 답할 수 없어요."),
    "task": (
        "I can only help find belongings that the camera has seen in your room. "
        "Ask me something like “Where is my wallet?”.",
        "저는 카메라가 방에서 본 물건을 찾는 것만 도와드릴 수 있어요. “지갑 어디 있어?”처럼 물어봐 주세요."),
    "command": (
        "Ask me where one of your belongings is, for example “Where is my wallet?”.",
        "찾고 싶은 물건을 물어봐 주세요. 예: “지갑 어디 있어?”"),
}


def message(kind: str, korean: bool) -> str:
    return MESSAGES[kind][1 if korean else 0]


# ---------- several items in one question ----------
SPLIT_EN = re.compile(r"\s*(?:,|&|\+|\band\b|\bplus\b)\s*", re.I)
SPLIT_KO = re.compile(r"(?<=[가-힣])(?:이랑|랑|하고)\s+|\s*,\s*")


# words that can stand alone between commas without naming anything ("So, ..., right?")
FILLER_EN = {"so", "right", "ok", "okay", "well", "yes", "no", "yeah", "hmm", "um", "then", "also", "just",
             "really", "actually", "maybe", "oh", "hey", "please", "thanks", "and", "or", "but", "too", "both"}


def split_items(question: str) -> list[str]:
    """"phone and signboard" -> ["phone", "signboard"]. Only the split is done here;
    the caller keeps it only if every part names an item ("black and white wallet" stays whole)."""
    q = (question or "").strip().rstrip("?.! ")
    parts = SPLIT_KO.split(q) if re.search(r"[가-힣]", q) else SPLIT_EN.split(q)
    return [p.strip() for p in parts if p and p.strip()]
