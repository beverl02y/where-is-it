"""Create eval/labels.csv with one row per photo per object, ready to fill in.

  python tools/make_label_template.py --images data/eval/images --out data/eval/labels.csv

Open the CSV in Google Sheets or Excel, set `present` to 1 where the object is
visible in that photo (leave 0 where it isn't), fill `zone` for present objects
(desk, bed, ...), and save it back as CSV.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--images", default="data/eval/images")
    p.add_argument("--out", default="data/eval/labels.csv")
    a = p.parse_args()

    images = sorted(x.name for x in Path(a.images).glob("*.jpg"))
    if not images:
        raise SystemExit(f"No .jpg photos in {a.images}")
    objects = list(load_settings().objects)
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} already exists — rename it first so your labels aren't overwritten")
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image", "object", "present", "zone"])
        for img in images:
            for obj in objects:
                w.writerow([img, obj, 0, ""])
    print(f"Wrote {len(images) * len(objects)} rows for {len(images)} photos to {out}")


if __name__ == "__main__":
    main()
