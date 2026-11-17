"""Admin tool: list or remove cameras (run on the server, e.g. inside Docker).

  docker compose exec api python tools/devices.py list
  docker compose exec api python tools/devices.py remove 3f9a1c2e
  docker compose exec api python tools/devices.py add "Lae's room" --pin 2580   # prints the camera token + room key
  docker compose exec api python tools/devices.py pin 3f9a1c2e 2580             # set a forgotten PIN

Shows camera names and photo counts only — never anyone's records.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402
from app.db import Database  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    rm = sub.add_parser("remove"); rm.add_argument("device_id")
    add = sub.add_parser("add"); add.add_argument("name"); add.add_argument("--pin")
    pn = sub.add_parser("pin"); pn.add_argument("device_id"); pn.add_argument("new_pin")
    a = p.parse_args()

    s = load_settings()
    db = Database(s.db_path)
    if a.cmd == "list":
        devs = db.list_devices()
        if not devs:
            print("No cameras yet.")
        for d in devs:
            print(f"{d['id']}  {d['name']:<24} photos={d['photos']:<6} last photo={d['last_seen_at'] or '-'}"
                  f"  interval={d['interval_s'] or '-'}s")
    elif a.cmd == "remove":
        if db.get_device(a.device_id) is None:
            sys.exit(f"No camera with ID {a.device_id}")
        db.delete_device(a.device_id)
        shutil.rmtree(Path(s.db_path).parent / "devices" / a.device_id, ignore_errors=True)
        print(f"Removed camera {a.device_id} and all its records.")
    elif a.cmd == "add":
        dev, token, key = db.create_device(a.name, pin=a.pin)
        print(f"Camera '{dev.name}' (ID {dev.id})")
        print(f"  camera token: {token}")
        print(f"  room link:    https://<your address>/#room={key}")
    elif a.cmd == "pin":
        import re
        if db.get_device(a.device_id) is None:
            sys.exit(f"No camera with ID {a.device_id}")
        if not re.fullmatch(r"\d{4,6}", a.new_pin):
            sys.exit("The PIN must be 4-6 digits")
        db.set_pin(a.device_id, a.new_pin)
        print(f"PIN changed for camera {a.device_id}; phones using the old PIN are disconnected.")


if __name__ == "__main__":
    main()
