"""Create two demo cameras with different sample records, to try the app (and show
that rooms are kept separate) without a real camera.

  python tools/seed_demo.py            (uses config.yaml's db_path)

Prints a room link for each demo room.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402
from app.db import Database  # noqa: E402


def det(obj, label, conf):
    return {"object": obj, "location": "ai", "location_label": label, "confidence": conf,
            "box": (0.1, 0.1, 0.2, 0.2)}


def main() -> None:
    s = load_settings()
    db = Database(s.db_path)
    now = datetime.now(timezone.utc)

    a, _, a_key = db.create_device("Demo room A")
    db.add_frame(now - timedelta(hours=3), [det("glasses", "on the bedside table", 0.91),
                                            det("wallet", "on the desk", 0.88)], device_id=a.id, interval_s=20)
    db.add_frame(now - timedelta(hours=1), [det("wallet", "on the desk", 0.86),
                                            det("charger", "on the bed", 0.58)], device_id=a.id, interval_s=20)
    db.add_frame(now - timedelta(seconds=20), [det("phone", "on the desk next to the laptop", 0.94)],
                 device_id=a.id, interval_s=20)

    b, _, b_key = db.create_device("Demo room B")
    db.add_frame(now - timedelta(seconds=15), [det("glasses", "on the shelf above the desk", 0.89),
                                               det("water bottle", "on the floor by the chair", 0.9)],
                 device_id=b.id, interval_s=20)

    print(f"Seeded demo data into {s.db_path}.")
    print(f"  Room A link:  http://localhost:8080/#room={a_key}")
    print(f"  Room B link:  http://localhost:8080/#room={b_key}")
    print("Ask both rooms 'Where are my glasses?' — each answers only from its own camera.")


if __name__ == "__main__":
    main()
