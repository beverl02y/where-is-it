"""Object detection (DETECT step) — Gemini 3.8 Flash.

One camera photo goes to the Gemini API (app/gemini_detector.py), which returns
every portable object it sees, how sure it is, where it is in words, and what it
looks like. model_type "none" turns detection off (demo data and tests).
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import Settings


@dataclass
class Detection:
    object: str                                   # object key, e.g. "glasses" or "water bottle"
    confidence: float                             # 0..1 (Gemini's own estimate)
    box: tuple[float, float, float, float] | None # normalised x1, y1, x2, y2 (None if Gemini gave none)
    label: str | None = None                      # human name, e.g. "water bottle"
    where: str | None = None                      # e.g. "on the desk next to the laptop"
    appearance: str | None = None                 # e.g. "large silver laptop"
    color: str | None = None
    size: str | None = None                       # small | medium | large
    shape: str | None = None
    name_ko: str | None = None                    # Korean, e.g. "물병"
    where_ko: str | None = None                   # e.g. "책상 위 노트북 옆"
    appearance_ko: str | None = None              # e.g. "흰색 물병"


class NullDetector:
    """Detects nothing. Used for demos/tests (model_type: none)."""
    name = "none"

    def detect(self, image) -> list[Detection]:
        return []


def build_detector(settings: Settings):
    if settings.model_type == "none":
        return NullDetector()
    from .gemini_detector import GeminiDetector
    return GeminiDetector(settings)
