"""Measure the detector against SPEC 6.3 on a labelled test set from YOUR room.

Test set = a folder of photos + a CSV, one row per (image, object):

    image,object,present,zone
    img_001.jpg,glasses,1,bedside_table
    img_001.jpg,wallet,0,
    img_002.jpg,phone,1,desk

Include rows with present=0 (object NOT in the photo) — they measure false positives.
Leave `zone` empty (it is only checked with location.mode: zones).

  python tools/evaluate.py --csv eval/labels.csv --images eval/images
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.detector import build_detector  # noqa: E402
from app.zones import assign_zone  # noqa: E402

TARGETS = {"accuracy": ("> 90%", lambda v: v > 0.90), "false_positive_rate": ("< 5%", lambda v: v < 0.05),
           "false_certainty_rate": ("< 2%", lambda v: v < 0.02),
           "p95_detect_seconds": ("< 2 s", lambda v: v < 2.0)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--images", required=True)
    args = p.parse_args()

    s = load_settings()
    detector = build_detector(s)
    thr = s.confirm_threshold
    rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))

    cache, times = {}, []
    tp = fp = tn = fn = 0
    confirmed = false_certain = 0
    per_obj: dict[str, list[int]] = {}

    for r in rows:
        name = r["image"]
        if name not in cache:
            img = cv2.imread(str(Path(args.images) / name))
            if img is None:
                print(f"skip unreadable {name}")
                cache[name] = None
                continue
            t0 = time.perf_counter()
            cache[name] = {d.object: d for d in detector.detect(img)}
            times.append(time.perf_counter() - t0)
        dets = cache[name]
        if dets is None:
            continue
        obj, present = r["object"], r["present"].strip() == "1"
        d = dets.get(obj)
        is_conf = d is not None and d.confidence >= thr
        correct = is_conf == present
        per_obj.setdefault(obj, []).append(int(correct))
        if present and is_conf: tp += 1
        elif present: fn += 1
        elif is_conf: fp += 1
        else: tn += 1
        if is_conf:
            confirmed += 1
            # The place is only checked when you drew zones (/zones page) and filled the
            # zone column; with Gemini's own descriptions, presence is what is measured.
            zone, _ = assign_zone(d.box, s.zones, s.fallback_location)
            wrong_zone = (bool(r.get("zone", "").strip()) and s.location_mode == "zones"
                          and zone != r["zone"].strip())
            if not present or wrong_zone:
                false_certain += 1   # we stated a fact that was wrong

    total = tp + fp + tn + fn
    times.sort()
    results = {
        "accuracy": (tp + tn) / total if total else 0,
        "false_positive_rate": fp / (fp + tn) if (fp + tn) else 0,
        "false_certainty_rate": false_certain / confirmed if confirmed else 0,
        "p95_detect_seconds": times[int(0.95 * (len(times) - 1))] if times else 0,
    }
    print(f"\nEvaluated {total} labels on {len(times)} images (confirm threshold {thr:.0%})")
    print(f"TP={tp} FP={fp} TN={tn} FN={fn}  recall={tp / (tp + fn) if tp + fn else 0:.1%}\n")
    for k, v in results.items():
        target, ok = TARGETS[k]
        shown = f"{v:.2f} s" if "seconds" in k else f"{v:.1%}"
        print(f"  {k:<22} {shown:>8}   target {target:<6} {'PASS' if ok(v) else 'FAIL'}")
    print("\nPer-object accuracy:")
    for obj, c in sorted(per_obj.items()):
        print(f"  {obj:<10} {sum(c) / len(c):.1%}  ({len(c)} labels)")


if __name__ == "__main__":
    main()
