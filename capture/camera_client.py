"""Camera client: grabs a frame from the room camera every N seconds and sends it
to the Where-Is-It AI server for detection.

Runs on the machine the camera is plugged into (laptop, mini-PC, Raspberry Pi).

  # first time: set this computer up as a camera (prints its camera token and room link)
  python capture/camera_client.py --server https://… --register "Lae's room" --invite CODE
  # then:
  python capture/camera_client.py --server https://… --camera-token cam_… --interval 900
  python capture/camera_client.py --image test.jpg --once     # send a photo file
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import cv2
import requests


def open_camera(device: str):
    src = int(device) if device.isdigit() else device   # index or RTSP/HTTP URL
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        sys.exit(f"Could not open camera '{device}'. Try --device 1, or check permissions.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    for _ in range(5):          # let auto-exposure settle
        cap.read()
    return cap


def grab(cap):
    for _ in range(3):          # drop buffered stale frames
        cap.grab()
    ok, frame = cap.read()
    return frame if ok else None


def send(frame, args) -> None:
    ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        print("JPEG encoding failed", file=sys.stderr)
        return
    t0 = time.perf_counter()
    r = requests.post(
        f"{args.server.rstrip('/')}/api/frames",
        headers={"X-Camera-Token": args.camera_token},
        files={"file": ("frame.jpg", jpg.tobytes(), "image/jpeg")},
        data={"captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "camera_id": args.camera_id, "interval_s": str(int(args.interval))},
        timeout=60,
    )
    r.raise_for_status()
    res = r.json()
    found = ", ".join(
        f"{d['object']} {d['location']} {round(d['confidence'] * 100)}%{'' if d['confirmed'] else ' (unconfirmed)'}"
        for d in res["detections"]) or "nothing"
    print(f"[{datetime.now():%H:%M:%S}] frame {res['frame_id']}: {found} "
          f"(server {res['processing_ms']} ms, round-trip {round((time.perf_counter() - t0) * 1000)} ms)")


def main() -> None:
    p = argparse.ArgumentParser(description="Where-Is-It AI camera client")
    p.add_argument("--server", default=os.environ.get("WIIA_SERVER", "http://localhost:8000"))
    p.add_argument("--camera-token", default=os.environ.get("WIIA_CAMERA_TOKEN", ""),
                   help="this camera's secret token (from --register or the camera page)")
    p.add_argument("--register", metavar="ROOM_NAME", help="set this computer up as a new camera")
    p.add_argument("--invite", default=os.environ.get("WIIA_INVITE_CODE", ""), help="invite code for --register")
    p.add_argument("--device", default=os.environ.get("WIIA_CAMERA", "0"), help="camera index or stream URL")
    p.add_argument("--interval", type=float, default=float(os.environ.get("WIIA_INTERVAL", 10)))
    p.add_argument("--camera-id", default="cam1")
    p.add_argument("--image", help="send this image file instead of using a camera")
    p.add_argument("--once", action="store_true", help="send one frame and exit")
    args = p.parse_args()

    if args.register:
        r = requests.post(f"{args.server.rstrip('/')}/api/devices/register",
                          json={"name": args.register, "invite_code": args.invite}, timeout=30)
        if not r.ok:
            sys.exit(f"Set-up failed: {r.json().get('detail', r.status_code)}")
        j = r.json()
        print(f"Camera '{j['device']['name']}' set up (ID {j['device']['id']}).")
        print(f"  Camera token (keep secret, use with --camera-token): {j['camera_token']}")
        print(f"  Room link (open on your phone to ask questions):      {args.server.rstrip('/')}/#room={j['room_key']}")
        return
    if not args.camera_token:
        sys.exit("Give --camera-token (or set WIIA_CAMERA_TOKEN). First time? Use --register.")

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            sys.exit(f"Cannot read {args.image}")
        send(frame, args)
        return

    cap = open_camera(args.device)
    backoff = args.interval
    print(f"Sending a frame every {args.interval}s to {args.server}. Ctrl+C to stop.")
    try:
        while True:
            frame = grab(cap)
            if frame is None:
                print("Camera read failed; reopening...", file=sys.stderr)
                cap.release()
                time.sleep(2)
                cap = open_camera(args.device)
                continue
            try:
                send(frame, args)
                backoff = args.interval
            except requests.RequestException as e:
                backoff = min(backoff * 2, 300)
                print(f"Server unreachable ({e}); retrying in {backoff:.0f}s", file=sys.stderr)
            if args.once:
                break
            time.sleep(backoff)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()


if __name__ == "__main__":
    main()
