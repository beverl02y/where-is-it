"""Record questions asked to the LIVE server as eval-case candidates.

You type questions (or replay a list); each answer is shown and saved to
evals/live_candidates.jsonl together with what the camera had recorded at that moment.
`expect` is left empty: deciding the right answer is the team's job. Copy the cases
you judged into evals/evalset.jsonl by hand.

Nothing on the server changes. The PIN is only sent to the server you name and is
never written to a file; neither is the room key.

Usage
  python evals/record_live.py --url https://34-56-40-29.sslip.io --camera-id 40eb902c
  python evals/record_live.py --url ... --camera-id ... --questions my_questions.txt   (one per line)
  python evals/record_live.py --url ... --camera-id ... --from-evalset                 (the 30 eval queries)

While typing:  /note <text>  adds a note to the last recorded answer
               /quit         stops (Ctrl+C works too)
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EVALS = Path(__file__).resolve().parent
OUT = EVALS / "live_candidates.jsonl"


class Server:
    def __init__(self, url: str):
        self.base = url.rstrip("/")
        self.room_key = ""

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.room_key:
            req.add_header("X-Room-Key", self.room_key)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode()).get("detail")
            except Exception:
                detail = None
            raise RuntimeError(f"server said {e.code}: {detail or e.reason}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"can't reach {self.base} ({e.reason})") from None


def snapshot(server: Server) -> list[dict]:
    """What the camera had recorded when the question was asked (the evidence for judging)."""
    try:
        objs = server.call("GET", "/api/objects").get("objects", [])
        return [{k: o.get(k) for k in ("display", "location", "seen", "confidence")} for o in objs if o.get("location")]
    except RuntimeError as e:
        return [{"error": str(e)}]


def save(rec: dict) -> None:
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def add_note(text: str) -> bool:
    if not OUT.exists():
        return False
    lines = OUT.read_text(encoding="utf-8").splitlines()
    if not lines:
        return False
    last = json.loads(lines[-1])
    last["note"] = (last.get("note", "") + " " + text).strip()
    lines[-1] = json.dumps(last, ensure_ascii=False)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def ask_and_record(server: Server, info: dict, query: str, n: int, source: str) -> None:
    asked = datetime.now(timezone.utc).astimezone()
    try:
        ans = server.call("POST", "/api/ask", {"question": query})
        err = None
    except RuntimeError as e:
        ans, err = None, str(e)
    rec = {
        "id": f"live-{asked:%Y%m%d-%H%M%S}-{n}",
        "source": source,                       # typed | questions-file | evalset:<id>
        "asked_at": asked.isoformat(timespec="seconds"),
        "server": info["server"],
        "server_detector": info["detector"],
        "camera_id": info["camera_id"],
        "query": query,
        "answer": ans,
        "error": err,
        "camera_saw": snapshot(server),
        "category": None,                       # <- you fill in
        "expect": None,                         # <- you decide the right answer
        "note": "",
    }
    save(rec)
    if err:
        print(f"   ! {err}  (saved)")
    else:
        print(f"   [{ans.get('status')}] {ans.get('message')}")


def main() -> int:
    p = argparse.ArgumentParser(description="Record live-server answers as eval-case candidates")
    p.add_argument("--url", required=True, help="server link, e.g. https://34-56-40-29.sslip.io")
    p.add_argument("--camera-id", required=True, help="camera ID shown on the camera page")
    p.add_argument("--questions", help="text file with one question per line")
    p.add_argument("--from-evalset", action="store_true", help="ask every query in evals/evalset.jsonl")
    args = p.parse_args()

    server = Server(args.url)
    try:
        health = server.call("GET", "/api/health")
    except RuntimeError as e:
        print(f"Can't reach the server: {e}")
        return 1
    pin = getpass.getpass("PIN (not shown, not saved): ")
    try:
        conn = server.call("POST", "/api/room/connect", {"camera_id": args.camera_id.strip(), "pin": pin.strip()})
    except RuntimeError as e:
        print(f"Could not connect: {e}")
        return 1
    server.room_key = conn["room_key"]
    info = {"server": server.base, "detector": health.get("detector"), "camera_id": args.camera_id.strip()}
    print(f"Connected to room '{conn['device'].get('name')}' on {server.base}. Saving to {OUT.relative_to(EVALS.parent)}\n")

    n = 0
    if args.questions or args.from_evalset:
        if args.questions:
            qs = [(q.strip(), "questions-file") for q in Path(args.questions).read_text(encoding="utf-8").splitlines() if q.strip()]
        else:
            cases = [json.loads(l) for l in (EVALS / "evalset.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            qs = [(c["query"], f"evalset:{c['id']}") for c in cases]
        for q, src in qs:
            n += 1
            print(f"{n:>3}. {q}")
            ask_and_record(server, info, q, n, src)
        print(f"\nRecorded {n} answers.")
        return 0

    print("Type a question and press Enter.  /note <text> = note on the last answer,  /quit = stop\n")
    while True:
        try:
            q = input("? ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q in ("/quit", "/exit"):
            break
        if q.startswith("/note"):
            print("   note added" if add_note(q[5:].strip()) else "   nothing to add a note to yet")
            continue
        n += 1
        ask_and_record(server, info, q, n, "typed")
    print(f"Recorded {n} answers in {OUT.relative_to(EVALS.parent)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
