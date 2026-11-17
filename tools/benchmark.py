"""Measure end-to-end response time of a running server (SPEC 6.3: < 6 s total,
< 2 s current image search).

  python tools/benchmark.py --server https://… --room-key room_… [--camera-token cam_… --image photo.jpg]
"""
from __future__ import annotations

import argparse
import os
import statistics
import time

import requests

QUESTIONS = ["Where are my glasses?", "Where is my wallet?", "where's my phone",
             "I can't find my charger", "Where did I leave my earphones?", "where is my student card",
             "where is my hair tie"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--server", default=os.environ.get("WIIA_SERVER", "http://localhost:8000"))
    p.add_argument("--room-key", default=os.environ.get("WIIA_ROOM_KEY", ""), required=False,
                   help="room key (the part after #room= in your room link)")
    p.add_argument("--camera-token", default=os.environ.get("WIIA_CAMERA_TOKEN", ""),
                   help="camera token, needed only with --image")
    p.add_argument("--image", help="also time frame upload + detection with this image")
    p.add_argument("--rounds", type=int, default=5)
    a = p.parse_args()
    a.room_key = a.room_key.split("room=")[-1]
    h = {"X-Room-Key": a.room_key}
    cam = {"X-Camera-Token": a.camera_token}

    if a.image:
        up = []
        for _ in range(a.rounds):
            t0 = time.perf_counter()
            with open(a.image, "rb") as f:
                requests.post(f"{a.server}/api/frames", headers=cam, files={"file": f}, timeout=60).raise_for_status()
            up.append(time.perf_counter() - t0)
        print(f"Frame upload+detect: median {statistics.median(up):.2f}s  max {max(up):.2f}s  (target < 2 s)")

    times = []
    for _ in range(a.rounds):
        for q in QUESTIONS:
            t0 = time.perf_counter()
            r = requests.post(f"{a.server}/api/ask", headers=h, json={"question": q}, timeout=30)
            r.raise_for_status()
            times.append(time.perf_counter() - t0)
    times.sort()
    print(f"Ask: {len(times)} queries  median {statistics.median(times) * 1000:.0f} ms  "
          f"p95 {times[int(0.95 * (len(times) - 1))] * 1000:.0f} ms  (target total < 6 s)")


if __name__ == "__main__":
    main()
