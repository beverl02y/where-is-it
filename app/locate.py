"""Describe WHERE an object is, in words — works in any room with no setup.

Order of preference (location.mode: auto):
  1. A zone drawn for this camera on the /zones page (optional)  -> "in my drawer"
  2. Gemini's own description of the place                        -> "on the desk next to the laptop"
  3. Its position in the camera picture (3 x 3 grid)              -> "in the bottom-left of the camera view"

With location.mode: zones, only zones are used.
"""
from __future__ import annotations

from .config import Settings, Zone
from .zones import assign_zone

Box = tuple[float, float, float, float]


def _anchor(box: Box) -> tuple[float, float]:
    """Point in the lower part of the box: objects rest ON surfaces."""
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2, y1 + 0.75 * (y2 - y1)


def grid_position(box: Box) -> tuple[str, str]:
    x, y = _anchor(box)
    col = "left" if x < 1 / 3 else "right" if x > 2 / 3 else "middle"
    row = "top" if y < 1 / 3 else "bottom" if y > 2 / 3 else "middle"
    if row == "middle" and col == "middle":
        where = "centre"
    elif row == "middle":
        where = f"{col} side"
    elif col == "middle":
        where = f"{row} middle"
    else:
        where = f"{row}-{col}"
    return f"view:{where}", f"in the {where} of the camera view"


def describe(box: Box | None, s: Settings, phrase: str | None = None,
             saved_zones: list[Zone] | None = None) -> tuple[str, str]:
    """Return (location key, human label) for an object's normalised box.
    `phrase` is Gemini's description of the place; `saved_zones` are this camera's zones.
    Without a box (Gemini gave none) only the phrase can be used."""
    if box is None:
        return ("ai", phrase) if phrase else ("unknown", s.fallback_location)
    if s.location_mode == "zones":
        return assign_zone(box, saved_zones or s.zones, s.fallback_location)

    if saved_zones:
        name, label = assign_zone(box, saved_zones, s.fallback_location)
        if name != "unknown":
            return name, label

    if phrase:
        return "ai", phrase

    return grid_position(box)
