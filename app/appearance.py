"""Telling apart several items with the same name ("which laptop?").

Gemini describes every item it sees (colour, size, shape, and a short phrase such
as "large silver laptop"). When a question contains describing words ("my black
laptop", "the big round bottle"), the records are filtered with them.

Words are normalised so different ways of saying the same thing match:
big / large / huge -> large, circle / round / circular -> round, grey -> gray ...
"""
from __future__ import annotations

import re

CANON = {
    # size
    "big": "large", "large": "large", "huge": "large", "bigger": "large", "larger": "large", "biggest": "large",
    "small": "small", "little": "small", "tiny": "small", "mini": "small", "smaller": "small", "smallest": "small",
    "medium": "medium", "mid": "medium", "middle": "medium",
    # height / thickness
    "tall": "tall", "long": "tall", "taller": "tall", "short": "short", "shorter": "short",
    "thin": "thin", "slim": "thin", "flat": "thin", "thick": "thick", "chunky": "thick", "bulky": "thick",
    # shape
    "round": "round", "circle": "round", "circular": "round", "oval": "round", "sphere": "round",
    "rectangle": "rectangular", "rectangular": "rectangular", "oblong": "rectangular",
    "square": "square", "squared": "square",
    "triangle": "triangular", "triangular": "triangular",
    "cylinder": "cylindrical", "cylindrical": "cylindrical", "tube": "cylindrical",
    # earphones and cables
    "cable": "wired", "corded": "wired", "wire": "wired", "wired": "wired",
    "bluetooth": "wireless", "wireless": "wireless", "cordless": "wireless",
    # colour spellings
    "grey": "gray", "gray": "gray", "golden": "gold", "silvery": "silver", "colorful": "multicolored",
    "colourful": "multicolored", "transparent": "clear", "see-through": "clear",
}

COLOURS = {"black", "white", "gray", "silver", "gold", "red", "orange", "yellow", "green", "blue", "navy",
           "purple", "pink", "brown", "beige", "clear", "multicolored", "dark", "light"}

# words that describe appearance; anything else left in a question is ignored
DESCRIBING = set(CANON.values()) | set(CANON) | COLOURS | {
    "leather", "metal", "plastic", "fabric", "wooden", "glass", "striped", "patterned", "shiny", "matte",
    "new", "old", "cracked", "wireless", "wired", "foldable", "folding", "paper", "silicone", "fluffy",
    "cloth", "steel", "ceramic", "rubber"}


def words(text: str | None) -> list[str]:
    return re.findall(r"[a-z]+(?:-[a-z]+)?", (text or "").lower())


def canon(text: str | None) -> set[str]:
    return {CANON.get(w, w) for w in words(text)}


def describing_words(text_words: list[str]) -> list[str]:
    """Keep only the words that describe appearance (colour, size, shape, material)."""
    return [w for w in text_words if w in DESCRIBING or CANON.get(w) in DESCRIBING]


def record_terms(rec) -> set[str]:
    return canon(" ".join(filter(None, [getattr(rec, "appearance", None), getattr(rec, "color", None),
                                        getattr(rec, "size", None), getattr(rec, "shape", None)])))


def best_matches(records: list, descriptors: list[str]) -> list:
    """Records matching the most describing words (at least one), in their original order."""
    want = {CANON.get(w, w) for w in descriptors}
    if not want or not any(record_terms(r) for r in records):
        return list(records)          # nothing known about how they look: can't filter
    scored = [(len(want & record_terms(r)), r) for r in records]
    top = max((s for s, _ in scored), default=0)
    return [r for s, r in scored if s == top and s > 0]


# ---------- one name per kind of item ----------
# Gemini may call the same thing "face mask", "facial mask" or "mask" in different photos.
# config.yaml same_items lists such names; they are all stored and searched as one name.

def clean_name(text: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())).strip()


def singular(phrase: str) -> str:
    out = []
    for w in phrase.split():
        if len(w) > 3 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return " ".join(out)


def name_forms(name: str) -> list[str]:
    n = clean_name(name)
    forms = [n, singular(n)]
    return list(dict.fromkeys(forms + [f.replace(" ", "") for f in forms]))


def item_name(name: str, same_items: dict[str, str]) -> str:
    """The one name used for this kind of item ("facial mask" -> "face mask")."""
    for form in name_forms(name):
        if form in same_items:
            return same_items[form]
    return name                       # not listed: keep the name as it is
