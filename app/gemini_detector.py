"""Object detection with the Gemini API (gemini-3.8-flash).

One photo -> one Gemini call that returns {"detections": [...]}, one entry per object:
  required
    category   one of the 7 SPEC objects (SUPPORTED_ITEMS), or "other"
    name       short name ("phone", "water bottle")
    location   where it is, in words ("on the desk next to the laptop")
    confidence the model's own 0-1 estimate (the SPEC 75% rule is applied to it)
  optional extras
    box_2d     [ymin, xmin, ymax, xmax] on a 0-1000 scale -> zones, camera-view fallback
    appearance "large silver laptop"; color, size, shape -> telling same-name items apart

Because Gemini describes the place itself, no zones or room setup are needed:
the same camera works in a bedroom, a classroom or anywhere else.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading

from .appearance import item_name
from .config import Settings

log = logging.getLogger(__name__)

class DetectionUnavailable(RuntimeError):
    """Detection could not run (no API key, quota, network, bad answer).
    The frame must NOT be saved: an empty result would wrongly mean 'not visible'."""


def build_prompt(settings: Settings) -> str:
    keys = []
    for key, obj in settings.objects.items():
        keys.append(f"- {key}: {obj.hint}")
    open_part = (
        "List EVERY distinct portable object you can see — things a person could misplace, "
        "for example phone, glasses, keys, bottle, book, notebook, pen, cup, bag, remote control, "
        "laptop, watch. Do not list furniture, walls, windows, people or pets.\n"
        if settings.detect_all_objects else
        "List ONLY the key items below that you can see.\n"
    )
    return (
        "You are the camera vision of an app that helps a student find misplaced belongings.\n"
        "Look carefully at this photo of a room.\n\n"
        + open_part +
        "\nAlways search carefully for these key items, even when they are small or partly hidden:\n"
        + "\n".join(keys) +
        "\n\nFor each object return:\n"
        f"- category: the key item name ({', '.join(supported_items(settings))}) if it is one of them, "
        "otherwise \"other\"\n"
        "- name: a short lowercase everyday name, e.g. \"phone\", \"water bottle\", \"face mask\". "
        "Always use the most common name and the same name for the same kind of item.\n"
        "- location: where it is, as a short phrase a person can act on, relative to furniture "
        "or nearby things, e.g. \"on the desk next to the laptop\", \"on the bed near the pillow\", "
        "\"on the floor by the chair\". Start with a preposition. Never mention people or pets.\n"
        "- confidence: your honest probability from 0.0 to 1.0 that this really is that object. "
        "Use a value below 0.75 only when you are really unsure WHAT it is (too blurry, mostly hidden, "
        "or it could be something else). Being small or far from the camera is NOT a reason for low "
        "confidence: a clearly recognisable item far away can still be 0.9. "
        "Never use 1.0.\n"
        "Also give, whenever you can:\n"
        "- box_2d: [ymin, xmin, ymax, xmax] normalized to 0-1000\n"
        "- appearance: a short phrase (at most 6 words) that tells this item apart from others with the same name, "
        "made of size, colour, material or shape plus the name, e.g. \"large silver laptop\", "
        "\"small black leather wallet\", \"tall clear water bottle\"\n"
        "- color: its main colour in one or two words, e.g. \"black\", \"light blue\"\n"
        "- size: small, medium or large compared with other objects of that kind\n"
        "- shape: one word, e.g. rectangular, round, square, triangular, cylindrical, irregular\n"
        "- name_ko: the same short name in natural Korean, e.g. \"휴대폰\", \"물병\", \"마스크\"\n"
        "- location_ko: the same place in natural Korean as a short noun phrase WITHOUT a final "
        "particle, e.g. \"책상 위 노트북 옆\", \"침대 위 베개 근처\", \"의자 옆 바닥\"\n"
        "- appearance_ko: the appearance phrase in Korean, e.g. \"큰 은색 노트북\", \"흰색 물병\"\n\n"
        "If two or more objects of the same kind are visible (for example two laptops), list EACH one "
        "separately with its own box, and make their appearance phrases different (colour, size, shape).\n"
        f"Search the WHOLE picture, including the far side of the room, corners, edges and the "
        f"background: small items up to about {settings.gemini_max_distance_m:g} metres from the camera "
        f"(on far tables, shelves, beds, chairs and the floor) must be found too.\n"
        + (tile_note(settings.gemini_tiles) if settings.gemini_tiles > 1 else "") +
        "Only report objects that are actually visible. If there are none, return an empty list."
    )


def tile_note(n: int) -> str:
    return (f"You get {n * n + 1} images of the SAME photo. Image 1 is the whole photo. Images 2-{n * n + 1} "
            f"are zoomed-in, slightly overlapping parts of it ({n} x {n} grid, left to right, top to bottom) "
            "so you can see small and far-away things. Use the zoomed parts to find items, but list each real "
            "object ONCE, and give box_2d relative to image 1 (the whole photo).\n")


def crops(image, n: int, overlap: float = 0.12) -> list:
    """n x n overlapping parts of the full-resolution photo (zoomed views)."""
    h, w = image.shape[:2]
    out = []
    for r in range(n):
        for c in range(n):
            x1 = max(0, int((c / n - overlap) * w)); x2 = min(w, int(((c + 1) / n + overlap) * w))
            y1 = max(0, int((r / n - overlap) * h)); y2 = min(h, int(((r + 1) / n + overlap) * h))
            out.append(image[y1:y2, x1:x2])
    return out


def supported_items(settings: Settings) -> list[str]:
    """The 7 key objects from config.yaml (SPEC 4.3)."""
    return list(settings.objects)


def response_schema(settings: Settings) -> dict:
    """The shape of the answer we want back from Gemini (JSON Schema).
    The four required fields are the core answer; the rest are optional extras."""
    return {
        "type": "object",
        "properties": {
            "detections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": supported_items(settings) + ["other"]},
                        "name": {"type": "string"},
                        "location": {"type": "string"},
                        "confidence": {"type": "number"},
                        # optional extras
                        "box_2d": {"type": "array", "items": {"type": "integer"}},
                        "appearance": {"type": "string"},
                        "color": {"type": "string"},
                        "size": {"type": "string", "enum": ["small", "medium", "large"]},
                        "shape": {"type": "string"},
                        "name_ko": {"type": "string"},
                        "location_ko": {"type": "string"},
                        "appearance_ko": {"type": "string"},
                    },
                    "required": ["category", "name", "location", "confidence"],
                },
            }
        },
        "required": ["detections"],
    }


def _cut(text: str, limit: int) -> str:
    """Shorten to `limit` characters without cutting a word in half."""
    return text if len(text) <= limit else text[:limit + 1].rsplit(" ", 1)[0]


def clean_label(text: str, limit: int = 40) -> str:
    text = re.sub(r"[^a-z0-9 \-]", " ", str(text).lower())
    return _cut(re.sub(r"\s+", " ", text).strip(), limit)


def clean_location(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip().rstrip(".")
    if text and text[0].isupper() and not text[:2].isupper():
        text = text[0].lower() + text[1:]
    return text[:90]


def clean_ko(text, limit: int = 40) -> str | None:
    """Korean text from Gemini: one line, no final full stop. None if empty or not Korean."""
    text = re.sub(r"\s+", " ", str(text or "")).strip().rstrip(".")
    return _cut(text, limit) if re.search(r"[\uac00-\ud7a3]", text) else None


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


MAX_SAME_NAME = 5     # most copies of one kind kept from a photo


def parse_response(text: str, settings: Settings):
    """Turn Gemini's {"detections": [...]} into Detection objects. Several items with
    the same name (two laptops) are all kept, each with its own appearance; the same
    item listed twice (boxes overlapping > 80%) is kept once. Optional fields may be
    missing: without box_2d the location comes from Gemini's words only."""
    from .detector import Detection

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            items = data["detections"] if "detections" in data else data["objects"]
        else:
            items = data
    except (ValueError, KeyError, TypeError) as e:
        raise DetectionUnavailable(f"Gemini returned an unreadable answer: {e}") from e

    found: list[Detection] = []
    for it in items[: settings.gemini_max_objects]:
        try:
            conf = max(0.0, min(0.99, float(it.get("confidence", 0))))
        except (ValueError, TypeError, AttributeError):
            continue
        box = None                                  # optional: [ymin, xmin, ymax, xmax] / 1000
        try:
            ymin, xmin, ymax, xmax = (max(0.0, min(1000.0, float(v))) / 1000 for v in it["box_2d"][:4])
            if xmax > xmin and ymax > ymin:
                box = (xmin, ymin, xmax, ymax)
        except (ValueError, KeyError, TypeError):
            pass
        name = clean_label(it.get("name") or it.get("label") or "")
        name = item_name(name, settings.same_items) if name else name   # "facial mask" -> "face mask"
        cat = str(it.get("category", "other")).lower()
        if cat not in settings.objects:          # "airpods" sent as "other" -> earphones
            cat = next((k for k, o in settings.objects.items()
                        if name and name in {k, o.display.lower(), *(a.lower() for a in o.aliases)}), cat)
        if cat in settings.objects:
            key = cat
        elif settings.detect_all_objects:
            key = name
            if not key:
                continue
        else:
            continue
        if conf < settings.store_threshold:
            continue
        size = str(it.get("size", "")).lower()
        det = Detection(key, conf, box,
                        label=name or key,
                        where=clean_location(it.get("location", "")) or None,
                        appearance=clean_label(it.get("appearance", ""), 60) or None,
                        color=clean_label(it.get("color", "")) or None,
                        size=size if size in ("small", "medium", "large") else None,
                        shape=clean_label(it.get("shape", "")) or None,
                        name_ko=clean_ko(it.get("name_ko")),
                        where_ko=clean_ko(it.get("location_ko"), 60),
                        appearance_ko=clean_ko(it.get("appearance_ko"), 50))
        same = [d for d in found if d.object == key]
        if det.box and all(d.box for d in same):    # same item listed twice: boxes overlap
            dup = next((d for d in same if _iou(d.box, det.box) > 0.8), None)
        else:                                       # no boxes: same description in the same place
            dup = next((d for d in same if (d.appearance, d.where) == (det.appearance, det.where)), None)
        if dup is not None:
            if det.confidence > dup.confidence:
                found[found.index(dup)] = det
            continue
        if len(same) >= MAX_SAME_NAME:
            continue
        found.append(det)
    return found


class GeminiDetector:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        self.name = f"gemini:{settings.gemini_model}" + ("" if self.api_key else " (GEMINI_API_KEY missing)")
        self._client = None
        self._lock = threading.Lock()
        self.prompt = build_prompt(settings)
        self.schema = response_schema(settings)
        if not self.api_key:
            log.error("GEMINI_API_KEY is not set — add it to .env and restart")

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=int(self.settings.gemini_timeout_s * 1000)),
            )
        return self._client

    @staticmethod
    def _jpeg(image, max_side: int) -> bytes:
        import cv2

        h, w = image.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            raise DetectionUnavailable("could not encode image")
        return buf.tobytes()

    def call_gemini(self, jpeg) -> str:
        """`jpeg`: one photo, or a list (whole photo first, then the zoomed parts)."""
        images = jpeg if isinstance(jpeg, list) else [jpeg]
        from google.genai import errors, types

        res_map = {"low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
                   "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
                   "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH}
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=self.schema,
            thinking_config=types.ThinkingConfig(thinking_level=self.settings.gemini_thinking_level),
            media_resolution=res_map.get(self.settings.gemini_media_resolution),
        )
        try:
            resp = self._get_client().models.generate_content(
                model=self.settings.gemini_model,
                contents=[types.Part.from_bytes(data=j, mime_type="image/jpeg") for j in images] + [self.prompt],
                config=config,
            )
        except errors.APIError as e:
            code = getattr(e, "code", None)
            hint = {429: "rate limit or free-tier quota reached — use a longer photo interval",
                    403: "API key not allowed for this model",
                    400: "request rejected (check the model name)"}.get(code, "Gemini API error")
            raise DetectionUnavailable(f"{hint} ({code})") from e
        except Exception as e:  # network errors, timeouts
            raise DetectionUnavailable(f"could not reach Gemini: {type(e).__name__}") from e
        if not resp.text:
            raise DetectionUnavailable("Gemini returned no answer (the photo may have been blocked)")
        return resp.text

    def detect(self, image):
        if not self.api_key:
            raise DetectionUnavailable("GEMINI_API_KEY is not set on the server")
        side = self.settings.gemini_max_image_side
        jpeg = self._jpeg(image, side)
        if self.settings.gemini_tiles > 1:      # whole photo + zoomed parts, each from full resolution
            jpeg = [jpeg] + [self._jpeg(part, side) for part in crops(image, self.settings.gemini_tiles)]
        with self._lock:          # one call at a time keeps quota use predictable
            text = self.call_gemini(jpeg)
        dets = parse_response(text, self.settings)
        log.info("Gemini found %d objects", len(dets))
        return dets
