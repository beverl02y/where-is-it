"""Loads config.yaml into typed settings objects."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Zone:
    name: str
    label: str
    polygon: list[tuple[float, float]]


@dataclass
class ObjectClass:
    key: str
    display: str
    plural: bool
    hint: str            # what Gemini should look for, e.g. "earphones (earbuds, AirPods case ...)"
    aliases: list[str]   # words a user may type in a question


@dataclass
class Settings:
    db_path: str = "data/whereisit.db"
    api_key: str = ""
    timezone: str = "Asia/Seoul"
    save_frames: bool = False
    retention_days: int = 30
    model_type: str = "gemini"       # gemini | none (demo/tests)
    store_threshold: float = 0.15
    confirm_threshold: float = 0.75
    detect_all_objects: bool = True  # also find/answer about items beyond the 7 key objects
    current_window_seconds: int = 120
    objects: dict[str, ObjectClass] = field(default_factory=dict)
    ambiguous_terms: dict[str, list[str]] = field(default_factory=dict)
    same_items: dict[str, str] = field(default_factory=dict)   # other name -> one name ("facial mask" -> "face mask")
    location_mode: str = "auto"      # auto | zones
    zones: list[Zone] = field(default_factory=list)   # example zones (location.mode: zones)
    fallback_location: str = "in the room, outside the marked areas"
    gemini_model: str = "gemini-3.8-flash"
    gemini_thinking_level: str = "low"
    gemini_media_resolution: str = "high"
    gemini_max_image_side: int = 1600
    gemini_tiles: int = 2                 # 2 = also send 4 zoomed-in parts (sees far/small items)
    gemini_max_distance_m: float = 3.0    # look for items up to about this far from the camera
    gemini_timeout_s: float = 30
    rag_enabled: bool = True              # hybrid RAG fallback for questions the rules can't answer
    rag_model: str = ""                   # "" = same as gemini_model
    rag_lookback_days: int = 7
    rag_max_records: int = 40
    rag_max_items: int = 60
    rag_timeout_s: float = 15
    rag_thinking_level: str = "minimal"   # minimal = fastest answers; low = the earlier setting
    rag_max_output_tokens: int = 400      # an answer is 1-4 sentences
    gemini_max_objects: int = 40
    invite_code: str = ""            # needed to set up a new camera (WIIA_INVITE_CODE)
    max_devices: int = 20


def parse_same_items(raw: dict) -> dict[str, str]:
    """config.yaml same_items: {"face mask": ["mask", "facial mask", ...]} -> {"mask": "face mask", ...}.
    Each name is stored as typed, singular, and without spaces ("facemask")."""
    from .appearance import name_forms
    out: dict[str, str] = {}
    for main, others in raw.items():
        main = " ".join(str(main).lower().split())
        for name in [main, *(others or [])]:
            for form in name_forms(str(name)):
                out.setdefault(form, main)
    return out


def load_settings(path: str | os.PathLike | None = None) -> Settings:
    path = Path(path or os.environ.get("WIIA_CONFIG", "config.yaml"))
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    server = raw.get("server", {}) or {}
    det = raw.get("detection", {}) or {}
    gem = raw.get("gemini", {}) or {}
    rag = raw.get("rag", {}) or {}
    search = raw.get("search", {}) or {}
    loc = raw.get("location", {}) or {}
    devices = raw.get("devices", {}) or {}

    objects = {}
    for key, o in (raw.get("objects") or {}).items():
        display = o.get("display", key)
        objects[key] = ObjectClass(
            key=key,
            display=display,
            plural=bool(o.get("plural", False)),
            hint=str(o.get("hint", display)),
            aliases=list(o.get("aliases", [key])),
        )

    s = Settings(
        db_path=os.environ.get("WIIA_DB_PATH", server.get("db_path", "data/whereisit.db")),
        api_key=os.environ.get("WIIA_API_KEY", server.get("api_key", "")),
        timezone=server.get("timezone", "Asia/Seoul"),
        save_frames=bool(server.get("save_frames", False)),
        retention_days=int(server.get("retention_days", 30)),
        model_type=os.environ.get("WIIA_MODEL_TYPE", det.get("model_type", "gemini")),
        store_threshold=float(det.get("store_threshold", 0.15)),
        confirm_threshold=float(det.get("confirm_threshold", 0.75)),
        detect_all_objects=bool(det.get("detect_all_objects", True)),
        current_window_seconds=int(search.get("current_window_seconds", 120)),
        objects=objects,
        ambiguous_terms={k.lower(): list(v) for k, v in (raw.get("ambiguous_terms") or {}).items()},
        same_items=parse_same_items(raw.get("same_items") or {}),
        location_mode=str(loc.get("mode", "auto")),
        zones=parse_zones(raw.get("zones") or []),
        fallback_location=raw.get("fallback_location", "in the room, outside the marked areas"),
        gemini_model=os.environ.get("WIIA_GEMINI_MODEL", gem.get("model", "gemini-3.8-flash")),
        gemini_thinking_level=str(gem.get("thinking_level", "low")),
        gemini_media_resolution=str(gem.get("media_resolution", "high")),
        gemini_max_image_side=int(gem.get("max_image_side", 1600)),
        gemini_tiles=max(1, min(3, int(gem.get("tiles", 2)))),
        gemini_max_distance_m=float(gem.get("max_distance_m", 3.0)),
        gemini_timeout_s=float(gem.get("timeout_seconds", 30)),
        rag_enabled=bool(rag.get("enabled", True)),
        rag_model=str(rag.get("model") or ""),
        rag_lookback_days=int(rag.get("lookback_days", 7)),
        rag_max_records=int(rag.get("max_records", 40)),
        rag_max_items=int(rag.get("max_items", 60)),
        rag_timeout_s=float(rag.get("timeout_seconds", 15)),
        rag_thinking_level=str(rag.get("thinking_level", "minimal")),
        rag_max_output_tokens=int(rag.get("max_output_tokens", 400)),
        gemini_max_objects=int(gem.get("max_objects", 40)),
        invite_code=os.environ.get("WIIA_INVITE_CODE", str(devices.get("invite_code", ""))),
        max_devices=int(devices.get("max_devices", 20)),
    )
    if s.model_type not in ("gemini", "none"):
        raise ValueError("detection.model_type must be 'gemini' or 'none'")
    if s.location_mode not in ("auto", "zones"):
        raise ValueError("location.mode must be 'auto' or 'zones'")
    if s.store_threshold > s.confirm_threshold:
        raise ValueError("store_threshold must be <= confirm_threshold")
    return s


def parse_zones(items: list) -> list[Zone]:
    zones = []
    for z in items:
        name = str(z["name"]).strip()
        if not re.fullmatch(r"[a-z0-9_]{1,40}", name):
            raise ValueError(f"bad zone name: {name!r}")
        poly = [(float(x), float(y)) for x, y in z["polygon"]]
        if len(poly) < 3 or not all(0 <= v <= 1 for p in poly for v in p):
            raise ValueError(f"zone {name}: needs 3+ points inside the image")
        label = str(z.get("label") or f"on the {name.replace('_', ' ')}").strip()[:60]
        zones.append(Zone(name=name, label=label, polygon=poly))
    return zones
