"""Maps a detection bounding box to a named room zone (e.g. 'on the desk')."""
from __future__ import annotations

from .config import Zone


def point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    """Ray-casting test. Coordinates are normalised (0..1)."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def polygon_area(poly: list[tuple[float, float]]) -> float:
    area = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def assign_zone(box: tuple[float, float, float, float], zones: list[Zone],
                fallback_label: str) -> tuple[str, str]:
    """Return (zone_name, human_label) for a normalised (x1, y1, x2, y2) box.

    We use a point in the lower part of the box: objects rest ON surfaces, so the
    bottom of the box is a better indicator of which surface they are on.
    When zones overlap, the smallest zone wins (bedside table beats bed area).
    """
    x1, y1, x2, y2 = box
    px = (x1 + x2) / 2
    py = y1 + 0.75 * (y2 - y1)
    hits = [z for z in zones if point_in_polygon(px, py, z.polygon)]
    if not hits:
        return "unknown", fallback_label
    best = min(hits, key=lambda z: polygon_area(z.polygon))
    return best.name, best.label
