"""Run the golden tests and save a result file.

Runs tests/test_golden_cases.py (the cases in tests/harness/golden_cases.yaml) with pytest
and writes:
  evals/results/golden-<run_id>.json   one entry per check: pass/fail, reason, case note
  evals/results/history_golden.csv     one line per run, for comparing versions

Usage (from the project folder):
  python3 evals/run_golden.py                      # golden cases only
  python3 evals/run_golden.py --change "GC-03 fix" # label this run
  python3 evals/run_golden.py --all                # whole tests/ folder (golden + other tests)

The printed "N/M passed" line can be passed to run_evals.py --golden.
Needs pytest:  pip install pytest
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

EVALS = Path(__file__).resolve().parent
ROOT = EVALS.parent
RESULTS = EVALS / "results"
GOLDEN_TEST = ROOT / "tests" / "test_golden_cases.py"
GOLDEN_YAML = ROOT / "tests" / "harness" / "golden_cases.yaml"


def file_hash(*paths: Path) -> str:
    h = hashlib.sha1()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:7]


def case_notes() -> dict[str, dict]:
    try:
        import yaml
        spec = yaml.safe_load(GOLDEN_YAML.read_text(encoding="utf-8"))
        return {c["name"]: c for c in spec.get("cases", [])}
    except Exception:
        return {}


def run_pytest(target: Path) -> tuple[ET.Element, str]:
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "golden.xml"
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(target),
             f"--junitxml={xml_path}"],
            cwd=ROOT, capture_output=True, text=True)
        if not xml_path.exists():
            sys.exit("pytest did not run:\n" + proc.stdout + proc.stderr)
        root = ET.parse(xml_path).getroot()
    summary = (proc.stdout.strip().splitlines() or [""])[-1]
    return root, summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--change", default="", help="what changed in this version, e.g. 'GC-03 fix'")
    p.add_argument("--all", action="store_true", help="run the whole tests/ folder, not only the golden cases")
    args = p.parse_args()

    notes = case_notes()
    root, pytest_summary = run_pytest(ROOT / "tests" if args.all else GOLDEN_TEST)

    checks = []
    for tc in root.iter("testcase"):
        name = tc.get("name", "")
        module = tc.get("classname", "").split(".")[-1]
        bad = tc.find("failure")
        if bad is None:
            bad = tc.find("error")
        skipped = tc.find("skipped")
        result = "fail" if bad is not None else "skip" if skipped is not None else "pass"
        case = name.split("[", 1)[1].rstrip("]") if "[" in name else ""
        entry = {"test": f"{module}::{name}", "result": result}
        if case in notes:
            entry["case"] = case
            entry["expect_record"] = notes[case].get("expect_record")
            entry["note"] = " ".join(str(notes[case].get("note", "")).split())
        if bad is not None:
            msg = (bad.get("message") or bad.text or "").strip()
            entry["reason"] = msg.splitlines()[0][:400] if msg else "failed"
        checks.append(entry)

    passed = sum(c["result"] == "pass" for c in checks)
    failed = sum(c["result"] == "fail" for c in checks)
    total = len(checks)
    now = datetime.now().astimezone()
    run_id = now.strftime("%Y-%m-%dT%H%M%S")
    app_files = sorted((ROOT / "app").glob("*.py"))
    run = {
        "run_id": run_id,
        "change": args.change,
        "scope": "tests/ (all)" if args.all else "golden cases",
        "golden_file": f"{GOLDEN_YAML.relative_to(ROOT)} ({file_hash(GOLDEN_YAML)})",
        "app_code": file_hash(*app_files) if app_files else "missing",
        "result": f"{passed}/{total} passed",
        "passed": passed, "failed": failed, "total": total,
        "pytest": pytest_summary,
        "checks": checks,
    }

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"golden-{run_id}.json"
    out.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    hist = RESULTS / "history_golden.csv"
    new = not hist.exists()
    with hist.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["run_id", "change", "scope", "golden_file", "app_code", "result", "failed_checks"])
        w.writerow([run_id, args.change, run["scope"], run["golden_file"], run["app_code"], run["result"],
                    "; ".join(c["test"] for c in checks if c["result"] == "fail")])

    print(f"\nwhere-is-it AI golden tests — run {run_id}  ({run['scope']}, app {run['app_code']})")
    for c in checks:
        mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[c["result"]]
        print(f"  {mark}  {c['test']}" + (f"\n        {c['reason']}" if "reason" in c else ""))
    print(f"\n{run['result']}   saved: {out.relative_to(ROOT)}  +  {hist.relative_to(ROOT)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
