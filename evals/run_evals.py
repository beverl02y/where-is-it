"""Evals runner for where-is-it AI — the statistical layer next to the pytest golden tests.

What it does
  1. Builds a fresh, throw-away database from evals/seed_rooms.json
     (stored camera detections = what Gemini "saw"; one room per camera).
  2. Asks every question in evals/evalset.jsonl to that case's room.
  3. Scores each answer:
       common checks (every case) -> answer format, never "100%", no blaming a person/pet,
                                     no false certainty (< 75% stated as fact),
                                     no invented place, no place leaked from another room,
                                     answer time < 2 s
       code  (graders has "code") -> every key in the case's `expect`
       judge (graders has "judge") -> only with --judge: Gemini grades the wording with
                                     evals/judge_prompt.md (one call per case)
  4. Prints a report and saves evals/results/<run_id>.json + one line in
     evals/results/history.csv.

Usage
  python evals/run_evals.py --change "baseline"
  python evals/run_evals.py --change "parser v2" --golden "67/67 passed"
  python evals/run_evals.py --judge          # also run the LLM judge (needs GEMINI_API_KEY)
  python evals/run_evals.py --only isolation # one category, for debugging (not saved to history)

Rules for this file (see the course guide): it must not read case ids to decide anything,
must not change the dataset, seed, judge prompt or targets, and must not change app/.
Unknown `expect` keys and judge replies that can't be read are ERRORS: they count as
failures and are never dropped from the totals.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.config import load_settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.search import SearchEngine  # noqa: E402

EVALSET = EVALS / "evalset.jsonl"
SEED = EVALS / "seed_rooms.json"
JUDGE_PROMPT = EVALS / "judge_prompt.md"
RESULTS = EVALS / "results"

# ---------------------------------------------------------------------------
# Pass lines — PROPOSED. The team must decide these (course rule: humans set the
# pass lines and can explain why). Absolute rules are counts that must be 0.
# Move the final values into evals/EVAL_DESIGN.md section 1 and keep them in sync.
# ---------------------------------------------------------------------------
TARGETS = {
    "status_accuracy":      (">= 0.90", lambda v: v >= 0.90),   # right kind of answer (AC-02..06, 6.2)
    "location_accuracy":    (">= 0.90", lambda v: v >= 0.90),   # right place (AC-03..05)
    "wording_accuracy":     (">= 0.90", lambda v: v >= 0.90),   # time / confidence / required phrases
    "false_certainty":      ("0",       lambda v: v == 0),      # absolute: < 75% stated as a fact
    "invented_location":    ("0",       lambda v: v == 0),      # absolute: place not in this room's records
    "cross_room_leak":      ("0",       lambda v: v == 0),      # absolute: another room's place in the answer
    "claims_100_percent":   ("0",       lambda v: v == 0),      # absolute: SPEC 6.2
    "blames_person_or_pet": ("0",       lambda v: v == 0),      # absolute: SPEC 6.2
    "p95_answer_ms":        ("< 6000",  lambda v: v < 6000),    # SPEC 6.3 response time
    "explanation_quality":  (">= 0.80", lambda v: v >= 0.80),   # judge (only with --judge)
}

ANSWER_FIELDS = {"status", "message", "object", "location", "seen_at", "confidence",
                 "confirmed", "suggestion", "elapsed_ms"}
STATUSES = {"current", "last_seen", "possible", "not_found", "clarify", "unsupported"}
BLAME_WORDS = ("someone", "somebody", "roommate", "stole", "stolen", "your cat", "your dog",
               "the cat", "the dog", "pet moved", "person moved")
EXPECT_KEYS = {"status", "location", "confirmed", "mentions", "forbidden",
               "suggestion_contains", "suggestion"}


# ---------------------------------------------------------------- loading
def parse_ago(text: str) -> timedelta:
    m = re.fullmatch(r"(\d+)\s*([smhd])", text.strip())
    if not m:
        raise ValueError(f"bad 'ago' value in seed: {text!r} (use e.g. 30s, 20m, 3h, 1d)")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(**{{"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}[unit]: n})


def load_cases() -> list[dict]:
    cases = []
    for n, line in enumerate(EVALSET.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"evalset.jsonl line {n} is not valid JSON: {e}")
    return cases


def build_rooms(settings, seed: dict) -> tuple[Database, dict, dict]:
    """Fresh DB with one device per seed room. Returns (db, room -> device id, room -> labels)."""
    db = Database(settings.db_path)
    now = datetime.fromisoformat(seed["now"])
    devices, labels = {}, {}
    for room, spec in seed["rooms"].items():
        dev, _, _ = db.create_device(spec.get("name", room))
        devices[room] = dev.id
        labels[room] = set()
        for frame in sorted(spec["frames"], key=lambda f: parse_ago(f["ago"]), reverse=True):
            dets = []
            for d in frame["detections"]:
                dets.append({"object": d["object"], "location": "auto", "location_label": d["location_label"],
                             "confidence": d["confidence"], "box": (0.1, 0.1, 0.2, 0.2),
                             "appearance": d.get("appearance"), "color": d.get("color"),
                             "size": d.get("size"), "shape": d.get("shape")})
                labels[room].add(d["location_label"])
            db.add_frame(now - parse_ago(frame["ago"]), dets, interval_s=spec.get("interval_s"),
                         device_id=dev.id)
    return db, devices, labels


# ---------------------------------------------------------------- checks
def has(text: str, phrase: str) -> bool:
    return phrase.lower() in (text or "").lower()


def leaked_places(text: str, own: set[str], others: set[str]) -> list[str]:
    """Places from OTHER rooms that appear in the answer, as whole phrases.
    The room's own places are blanked out first, and longer phrases are checked first,
    so 'on the bed' is not reported just because 'on the bedside table' was mentioned."""
    t = text.lower()
    for p in sorted(own, key=len, reverse=True):
        t = t.replace(p.lower(), " ")
    found = []
    for p in sorted(others, key=len, reverse=True):
        pat = re.compile(rf"(?<!\w){re.escape(p.lower())}(?!\w)")
        if pat.search(t):
            found.append(p)
            t = pat.sub(" ", t)
    return sorted(found)


def common_checks(ans: dict, room: str, labels: dict) -> dict:
    """Applied to every case, whatever its graders say."""
    text = f"{ans.get('message') or ''} {ans.get('suggestion') or ''}"
    own = labels[room]
    others = set().union(*(v for k, v in labels.items() if k != room)) - own
    loc = ans.get("location")
    out = {
        "schema": set(ans) >= ANSWER_FIELDS and ans.get("status") in STATUSES and bool(ans.get("message")),
        "claims_100_percent": "100%" in text,
        "blames_person_or_pet": [w for w in BLAME_WORDS if has(text, w)],
        # a confirmed answer must rest on a >= 75% sighting; a possibility must say so
        "false_certainty": bool(
            (ans.get("confirmed") and (ans.get("confidence") or 0) < 0.75)
            or (ans.get("status") == "possible" and (ans.get("confirmed") or not has(text, "not confirmed")))
        ),
        "invented_location": bool(loc) and loc not in own,
        "cross_room_leak": leaked_places(text, own, others),
        "fast": (ans.get("elapsed_ms") or 0) < 2000,
    }
    out["pass"] = (out["schema"] and not out["claims_100_percent"] and not out["blames_person_or_pet"]
                   and not out["false_certainty"] and not out["invented_location"]
                   and not out["cross_room_leak"] and out["fast"])
    return out


def code_checks(ans: dict, expect: dict) -> dict:
    """One result per expect key. Unknown keys are errors (never silently ignored)."""
    text = ans.get("message") or ""
    out: dict = {}
    for key, want in expect.items():
        if key not in EXPECT_KEYS:
            out[key] = {"error": f"runner can't check expect key '{key}'"}
        elif key == "status":
            ok = ans.get("status") in (want if isinstance(want, list) else [want])
            out[key] = {"pass": ok, "got": ans.get("status")}
        elif key == "location":
            out[key] = {"pass": ans.get("location") == want, "got": ans.get("location")}
        elif key == "confirmed":
            out[key] = {"pass": bool(ans.get("confirmed")) == want, "got": ans.get("confirmed")}
        elif key == "mentions":
            missing = [p for p in want if not has(f"{text} {ans.get('suggestion') or ''}", p)]
            out[key] = {"pass": not missing, "missing": missing}
        elif key == "forbidden":
            found = [p for p in want if has(f"{text} {ans.get('suggestion') or ''}", p)]
            out[key] = {"pass": not found, "found": found}
        elif key == "suggestion_contains":
            out[key] = {"pass": has(ans.get("suggestion") or "", want), "got": ans.get("suggestion")}
        elif key == "suggestion":
            out[key] = {"pass": ans.get("suggestion") == want, "got": ans.get("suggestion")}
    out["error"] = any("error" in v for v in out.values() if isinstance(v, dict))
    out["pass"] = not out["error"] and all(v.get("pass") for v in out.values() if isinstance(v, dict))
    return out


# ---------------------------------------------------------------- judge
def judge_version() -> str:
    if not JUDGE_PROMPT.exists():
        return "none"
    text = JUDGE_PROMPT.read_text(encoding="utf-8")
    m = re.search(r"version:\s*([\w.\-]+)", text)
    return (m.group(1) if m else "unversioned") + "-" + hashlib.sha1(text.encode()).hexdigest()[:7]


def judge_instructions() -> str:
    """The part of judge_prompt.md between the markers is sent; the rest is team notes."""
    text = JUDGE_PROMPT.read_text(encoding="utf-8")
    m = re.search(r"<!--\s*JUDGE_PROMPT_START\s*-->(.*?)<!--\s*JUDGE_PROMPT_END\s*-->", text, re.S)
    return (m.group(1) if m else text).strip()


def run_judge(case: dict, ans: dict, settings) -> dict:
    """One independent Gemini call per case. Reply must be JSON: {"c1": {"reason", "pass"}, ...}."""
    try:
        from google import genai
        from google.genai import types
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            return {"error": "GEMINI_API_KEY is not set"}
        client = genai.Client(api_key=key)
        payload = {"question": case["query"], "category": case["category"], "case_note": case.get("note", ""),
                   "answer_status": ans["status"], "answer": ans["message"], "suggestion": ans.get("suggestion")}
        resp = client.models.generate_content(
            model=os.environ.get("WIIA_JUDGE_MODEL", settings.gemini_model),
            contents=json.dumps(payload, ensure_ascii=False),
            config=types.GenerateContentConfig(system_instruction=judge_instructions(),
                                               response_mime_type="application/json", temperature=0),
        )
        verdict = json.loads(resp.text)
        crit = {k: v for k, v in verdict.items() if isinstance(v, dict) and "pass" in v}
        if not crit:
            return {"error": f"judge reply has no criteria: {resp.text[:200]}"}
        return {**crit, "pass": all(bool(v["pass"]) for v in crit.values())}
    except json.JSONDecodeError as e:
        return {"error": f"judge reply is not JSON ({e})"}
    except Exception as e:   # network, quota, missing package ...
        return {"error": f"judge call failed: {type(e).__name__}: {e}"}


# ---------------------------------------------------------------- metrics
def rate(cases: list[dict], key: str) -> dict:
    scored = [c for c in cases if key in c.get("code", {})]
    ok = sum(1 for c in scored if c["code"][key].get("pass"))
    return {"value": round(ok / len(scored), 3) if scored else None, "passed": ok, "total": len(scored)}


def summarize(results: list[dict], judged: bool) -> dict:
    m: dict = {
        "status_accuracy": rate(results, "status"),
        "location_accuracy": rate(results, "location"),
    }
    wording = [c for c in results if any(k in c.get("code", {}) for k in ("mentions", "forbidden", "suggestion_contains", "suggestion"))]
    ok = sum(1 for c in wording if all(c["code"][k].get("pass") for k in ("mentions", "forbidden", "suggestion_contains", "suggestion") if k in c["code"]))
    m["wording_accuracy"] = {"value": round(ok / len(wording), 3) if wording else None, "passed": ok, "total": len(wording)}
    for k in ("false_certainty", "invented_location", "cross_room_leak", "claims_100_percent", "blames_person_or_pet"):
        m[k] = {"count": sum(1 for c in results if c.get("common", {}).get(k))}
    times = sorted(c["output"]["elapsed_ms"] for c in results if c.get("output"))
    m["p95_answer_ms"] = {"value": round(times[max(0, int(len(times) * 0.95) - 1)], 1) if times else None}
    if judged:
        jc = [c for c in results if isinstance(c.get("judge"), dict) and not c["judge"].get("skipped")]
        ok = sum(1 for c in jc if c["judge"].get("pass"))
        m["explanation_quality"] = {"value": round(ok / len(jc), 3) if jc else None, "passed": ok, "total": len(jc),
                                    "errors": sum(1 for c in jc if "error" in c["judge"])}
    for k, v in m.items():
        target, test = TARGETS[k]
        val = v.get("count", v.get("value"))
        v["target"], v["met"] = target, (test(val) if val is not None else None)
    m["case_pass_rate"] = {"value": round(sum(c["pass"] for c in results) / len(results), 3) if results else None,
                           "passed": sum(c["pass"] for c in results), "total": len(results)}
    return m


# ---------------------------------------------------------------- run info
def file_hash(*paths: Path) -> str:
    h = hashlib.sha1()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:7]


def git_commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "no-git"
    except Exception:
        return "no-git"


def new_run_id(tz) -> str:
    base = datetime.now(tz).strftime("%Y-%m-%dT%H%M")
    run_id, n = base, 2
    while (RESULTS / f"{run_id}.json").exists():
        run_id, n = f"{base}-{n}", n + 1
    return run_id


# ---------------------------------------------------------------- main
def main() -> int:
    p = argparse.ArgumentParser(description="Run the where-is-it AI evals")
    p.add_argument("--change", default="", help="what changed since the last run, e.g. 'parser v2'")
    p.add_argument("--golden", default="not run", help="golden test result, e.g. '67/67 passed'")
    p.add_argument("--judge", action="store_true", help="also run the LLM judge (needs GEMINI_API_KEY)")
    p.add_argument("--only", help="run one category only (result is not added to history.csv)")
    args = p.parse_args()

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cases = load_cases()
    if args.only:
        cases = [c for c in cases if c["category"] == args.only]
        if not cases:
            sys.exit(f"no cases with category '{args.only}'")
    if args.judge and not JUDGE_PROMPT.exists():
        print(f"! --judge given but {JUDGE_PROMPT.relative_to(ROOT)} is missing: judge cases will be errors")

    settings = load_settings(ROOT / "config.yaml")
    settings.model_type = "none"            # answers come from the stored detections only
    now = datetime.fromisoformat(seed["now"])

    results = []
    with tempfile.TemporaryDirectory() as tmp:
        settings.db_path = str(Path(tmp) / "evals.db")
        db, devices, labels = build_rooms(settings, seed)
        engine = SearchEngine(settings, db)
        for case in cases:
            row = {"id": case["id"], "category": case["category"], "room": case.get("room"),
                   "query": case["query"], "graders": case.get("graders", ["code"])}
            try:
                room = case["room"]
                if room not in devices:
                    raise ValueError(f"room '{room}' is not in seed_rooms.json")
                ans = engine.ask(case["query"], now=now, device_id=devices[room]).to_dict()
                row["output"] = ans
                row["common"] = common_checks(ans, room, labels)
                if "code" in row["graders"]:
                    row["code"] = code_checks(ans, case.get("expect", {}))
                if "judge" in row["graders"]:
                    row["judge"] = run_judge(case, ans, settings) if args.judge else {"skipped": True}
                parts = [row["common"]["pass"]]
                if "code" in row:
                    parts.append(row["code"]["pass"])
                if args.judge and "judge" in row:
                    parts.append(bool(row["judge"].get("pass")) and "error" not in row["judge"])
                row["error"] = bool(row.get("code", {}).get("error")) or "error" in row.get("judge", {})
                row["pass"] = all(parts)
            except Exception as e:   # a broken case is a failure, never dropped
                row.update(error=True, pass_=False, exception=f"{type(e).__name__}: {e}")
                row["pass"] = False
                row.pop("pass_", None)
            results.append(row)

    metrics = summarize(results, args.judge)
    tz = engine.tz
    run = {
        "run_id": new_run_id(tz),
        "commit": git_commit(),
        "change": args.change,
        "evalset_version": f"{len(load_cases())} cases, {file_hash(EVALSET, SEED)}",
        "judge_version": judge_version() if args.judge else "not run",
        "golden_tests": args.golden,
        "only": args.only,
        "metrics": metrics,
        "cases": results,
    }
    report(run)
    if args.only:
        print("\n(--only: not saved)")
        return 0
    save(run)
    return 0 if all(v.get("met") is not False for k, v in metrics.items() if k != "case_pass_rate") else 1


def why_failed(c: dict) -> str:
    if c.get("exception"):
        return c["exception"]
    bits = []
    com = c.get("common", {})
    for k in ("claims_100_percent", "blames_person_or_pet", "false_certainty", "invented_location", "cross_room_leak"):
        if com.get(k):
            bits.append(f"{k}={com[k]}" if isinstance(com[k], list) else k)
    if com and not com.get("schema"):
        bits.append("bad answer format")
    if com and not com.get("fast"):
        bits.append("slow")
    for k, v in c.get("code", {}).items():
        if isinstance(v, dict) and not v.get("pass"):
            detail = v.get("error") or v.get("missing") or v.get("found") or f"got {v.get('got')!r}"
            bits.append(f"{k}: {detail}")
    j = c.get("judge", {})
    if j and not j.get("skipped") and not j.get("pass"):
        bits.append("judge: " + (j.get("error") or ", ".join(k for k, v in j.items() if isinstance(v, dict) and not v.get("pass"))))
    return "; ".join(bits)


def report(run: dict) -> None:
    print(f"\nwhere-is-it AI evals — run {run['run_id']}  ({run['evalset_version']}, judge {run['judge_version']})")
    print("\nCase results")
    for c in run["cases"]:
        mark = "PASS" if c["pass"] else ("ERROR" if c.get("error") else "FAIL")
        line = f"  {mark:<5} {c['id']:<4} {c['category']:<13} {c['query'][:46]:<46}"
        if not c["pass"]:
            line += "  <- " + why_failed(c)
        elif c.get("judge", {}).get("skipped"):
            line += "  (judge not run)"
        print(line)
    print("\nMetrics")
    for k, v in run["metrics"].items():
        val = v.get("count", v.get("value"))
        frac = f" ({v['passed']}/{v['total']})" if "total" in v else ""
        met = {True: "ok", False: "MISSED", None: "-"}[v.get("met")] if "met" in v else ""
        print(f"  {k:<22} {str(val):<7}{frac:<10} target {v.get('target', '-'):<8} {met}")
    by_cat: dict = {}
    for c in run["cases"]:
        s = by_cat.setdefault(c["category"], [0, 0])
        s[0] += c["pass"]; s[1] += 1
    print("\nBy category: " + ", ".join(f"{k} {p}/{t}" for k, (p, t) in by_cat.items()))


def save(run: dict) -> None:
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{run['run_id']}.json"
    out.write_text(json.dumps(run, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    hist = RESULTS / "history.csv"
    cols = ["run_id", "commit", "change", "evalset_version", "judge_version", "golden_tests",
            "case_pass_rate", "status_accuracy", "location_accuracy", "wording_accuracy",
            "false_certainty", "invented_location", "cross_room_leak", "claims_100_percent",
            "blames_person_or_pet", "p95_answer_ms", "explanation_quality"]
    m = run["metrics"]
    row = {k: run[k] for k in cols[:6]}
    for k in cols[6:]:
        row[k] = "" if k not in m else m[k].get("count", m[k].get("value"))
    new = not hist.exists()
    with hist.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerow(row)
    print(f"\nSaved {out.relative_to(ROOT)} and a line in {hist.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
