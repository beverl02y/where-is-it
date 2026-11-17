"""LLM-as-a-judge for where-is-it AI, following evals/judge_prompt.md.

It judges SAVED product answers (the live recordings), never new ones, so the judge and
the human look at exactly the same outputs.

Steps (the order is the rule in judge_prompt.md: humans label BEFORE seeing the judge)
  1. python3 evals/run_judge.py labels
        Adds one row per judge case to evals/judge_labels.jsonl with the question, the
        saved answer and what the camera had recorded. You fill c1..c4 with true/false
        (null = not applicable) and your name in labeled_by. Existing rows are kept.
  2. python3 evals/run_judge.py run
        Refuses until at least 20 cases are labeled. Calls the judge once per case
        (needs GEMINI_API_KEY) and saves evals/results/judge-<run_id>.json.
  3. python3 evals/run_judge.py agree
        Compares the latest judge run with your labels: agreement per criterion and the
        list of disagreements. Target from judge_prompt.md: >= 80%.

  python3 evals/run_judge.py show e21     prints what would be sent for one case (no API call)

Where the saved answer for a case comes from (first match wins)
  - a record in evals/live_candidates.jsonl whose source is "evalset:<case id>"
    (made by: record_live.py --from-evalset); the latest one is used
  - "live#N" in the case note -> line N of evals/live_candidates.jsonl
    (several numbers, e.g. "live#7 and live#8" -> the first one)
  - the latest record in evals/live_candidates.jsonl with exactly the same question text
Cases with no saved answer are reported as "no saved output" and are not judged.

Which criteria apply to a case
  - the case's own "judge_criteria" list, e.g. "judge_criteria": ["c1", "c3"], if present
  - otherwise CRITERIA_BY_CATEGORY below (PROPOSED: the team decides)

This script does not change evalset.jsonl, the judge prompt, the targets or app/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

EVALS = Path(__file__).resolve().parent
EVALSET = EVALS / "evalset.jsonl"
LIVE = EVALS / "live_candidates.jsonl"
PROMPT = EVALS / "judge_prompt.md"
LABELS = EVALS / "judge_labels.jsonl"
RESULTS = EVALS / "results"

CRITERIA = ("c1", "c2", "c3", "c4")
MIN_LABELED = 20          # judge_prompt.md: at least 20 labeled outputs before viewing verdicts
AGREEMENT_TARGET = 0.80   # judge_prompt.md: at least 80%

# PROPOSED defaults: the team decides. A case's own "judge_criteria" overrides this.
#   c1 observation limits, c2 possibility distinction, c3 unsupported claims, c4 conflict/scope
CRITERIA_BY_CATEGORY = {
    "constraint":    ["c1", "c3"],
    "conflict":      ["c1", "c3", "c4"],
    "injection":     ["c3", "c4"],
    "clarify":       ["c4"],
    "hallucination": ["c3"],
    "out_of_scope":  ["c4"],
    "possibility":   ["c1", "c2", "c3"],
}


# ---------------------------------------------------------------- loading
def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"{path.name} line {n} is not valid JSON: {e}")
    return rows


def judge_cases() -> list[dict]:
    return [c for c in read_jsonl(EVALSET) if "judge" in c.get("graders", [])]


def criteria_for(case: dict) -> list[str]:
    crit = case.get("judge_criteria") or CRITERIA_BY_CATEGORY.get(case.get("category"), [])
    bad = [c for c in crit if c not in CRITERIA]
    if bad:
        sys.exit(f"case {case['id']}: unknown judge criteria {bad} (use {', '.join(CRITERIA)})")
    return list(crit)


def saved_output(case: dict, live: list[dict]) -> tuple[dict | None, str]:
    """(live record, where it came from) or (None, reason)."""
    tagged = [r for r in live if r.get("source") == f"evalset:{case['id']}"]
    if tagged:
        return tagged[-1], f"source evalset:{case['id']}"
    same_id = [r for r in live if r.get("id") == case["id"]]     # case id = recorded answer id
    if same_id:
        return same_id[-1], f"id {case['id']}"
    m = re.search(r"live#(\d+)", case.get("note", ""))
    if m:
        n = int(m.group(1))
        if 1 <= n <= len(live):
            return live[n - 1], f"live#{n}"
        return None, f"note says live#{n} but live_candidates.jsonl has {len(live)} lines"
    same = [r for r in live if (r.get("query") or "").strip() == case["query"].strip()]
    if same:
        return same[-1], "same question text"
    return None, "no saved output"


def judge_input(case: dict, rec: dict) -> dict:
    """What the judge sees (judge_prompt.md 'Input'). Everything here is data, not instructions."""
    return {
        "query": case["query"],
        "category": case["category"],
        "fixture": {
            "asked_at": rec.get("asked_at"),
            "camera_records": rec.get("camera_saw"),
            "case_requirements": case.get("note", ""),
            "expected": case.get("expect"),
        },
        "output": rec.get("answer"),
        "applicable_criteria": criteria_for(case),
    }


def system_prompt() -> str:
    text = PROMPT.read_text(encoding="utf-8")
    m = re.search(r"<!--\s*JUDGE_SYSTEM_START\s*-->(.*?)<!--\s*JUDGE_SYSTEM_END\s*-->", text, re.S)
    if not m:
        sys.exit("judge_prompt.md has no JUDGE_SYSTEM_START / JUDGE_SYSTEM_END markers")
    return m.group(1).strip()


def prompt_version() -> str:
    text = PROMPT.read_text(encoding="utf-8")
    m = re.search(r"Judge Prompt\s+(v[\w.\-]+)", text)
    return f"{m.group(1) if m else 'unversioned'}-{hashlib.sha1(text.encode()).hexdigest()[:7]}"


def model_name() -> str:
    if os.environ.get("WIIA_JUDGE_MODEL"):
        return os.environ["WIIA_JUDGE_MODEL"]
    cfg = EVALS.parent / "config.yaml"
    if cfg.exists():
        m = re.search(r"^gemini:\s*\n(?:[ \t]+.*\n)*?[ \t]+model:\s*\"?([\w.\-]+)", cfg.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    return "gemini-2.5-flash"


# ---------------------------------------------------------------- judging
def validate(verdict: dict, applicable: list[str]) -> str | None:
    """Error text, or None. Missing criteria, empty reasons and wrong types are grading errors."""
    if not isinstance(verdict, dict):
        return "reply is not a JSON object"
    for c in CRITERIA:
        v = verdict.get(c)
        if not isinstance(v, dict):
            return f"{c} missing"
        if not str(v.get("reason", "")).strip():
            return f"{c} has an empty reason"
        if c in applicable and not isinstance(v.get("pass"), bool):
            return f"{c} is applicable but pass is {v.get('pass')!r}"
        if c not in applicable and v.get("pass") is not None:
            return f"{c} is not applicable but pass is {v.get('pass')!r}"
    return None


def call_judge(client, types, model: str, system: str, payload: dict) -> dict:
    try:
        resp = client.models.generate_content(
            model=model,
            contents=json.dumps(payload, ensure_ascii=False),
            config=types.GenerateContentConfig(system_instruction=system, temperature=0,
                                               response_mime_type="application/json"),
        )
        verdict = json.loads(resp.text)
    except json.JSONDecodeError as e:
        return {"error": f"reply is not JSON ({e})"}
    except Exception as e:   # network, quota, bad key ...
        return {"error": f"call failed: {type(e).__name__}: {e}"}
    err = validate(verdict, payload["applicable_criteria"])
    if err:
        return {"error": err, "raw": verdict}
    out = {c: verdict[c] for c in CRITERIA}
    out["pass"] = all(verdict[c]["pass"] for c in payload["applicable_criteria"])
    return out


# ---------------------------------------------------------------- labels
def labeled(rows: list[dict]) -> list[dict]:
    """Rows where every applicable criterion has true/false."""
    return [r for r in rows if r.get("applicable_criteria")
            and all(isinstance(r.get("labels", {}).get(c), bool) for c in r["applicable_criteria"])]


def cmd_labels() -> int:
    live = read_jsonl(LIVE)
    existing = {r["id"]: r for r in read_jsonl(LABELS)}
    added, missing = 0, []
    with LABELS.open("a", encoding="utf-8") as f:
        for case in judge_cases():
            if case["id"] in existing:
                continue
            rec, where = saved_output(case, live)
            if rec is None:
                missing.append(f"{case['id']} ({where})")
                continue
            crit = criteria_for(case)
            ans = rec.get("answer") or {}
            f.write(json.dumps({
                "id": case["id"],
                "query": case["query"],
                "answer_message": ans.get("message"),
                "answer_status": ans.get("status"),
                "saved_output_from": where,
                "applicable_criteria": crit,
                "labels": {c: (None if c in crit else "n/a") for c in CRITERIA},   # <- you: true / false
                "labeled_by": "",
                "note": "",
            }, ensure_ascii=False) + "\n")
            added += 1
    print(f"Added {added} rows to {LABELS.relative_to(EVALS.parent)} ({len(existing)} were already there).")
    if missing:
        print("Not added, no saved answer: " + ", ".join(missing))
    print("Fill labels with true/false for each applicable criterion (see judge_prompt.md c1..c4).")
    print(f"Labeled so far: {len(labeled(read_jsonl(LABELS)))} (need {MIN_LABELED} before 'run').")
    return 0


# ---------------------------------------------------------------- commands
def cmd_show(case_id: str) -> int:
    case = next((c for c in judge_cases() if c["id"] == case_id), None)
    if not case:
        sys.exit(f"no judge case '{case_id}' in evalset.jsonl")
    rec, where = saved_output(case, read_jsonl(LIVE))
    if rec is None:
        sys.exit(f"{case_id}: {where}")
    print(f"# saved output from {where}; prompt {prompt_version()}; model {model_name()}")
    print(json.dumps(judge_input(case, rec), ensure_ascii=False, indent=2))
    return 0


def cmd_run(force: bool) -> int:
    n_labeled = len(labeled(read_jsonl(LABELS)))
    if n_labeled < MIN_LABELED and not force:
        print(f"Only {n_labeled} cases are labeled in {LABELS.name}; judge_prompt.md requires "
              f"{MIN_LABELED} before viewing judge verdicts. Run 'labels' and fill them first.")
        return 1
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("GEMINI_API_KEY is not set (use a NEW key, not one that was ever shown in a photo).")
        return 1
    from google import genai
    from google.genai import types
    client, model, system = genai.Client(api_key=key), model_name(), system_prompt()

    live, results = read_jsonl(LIVE), []
    for case in judge_cases():
        rec, where = saved_output(case, live)
        row = {"id": case["id"], "category": case["category"], "query": case["query"], "saved_output_from": where}
        if rec is None:
            row["skipped"] = where
        else:
            payload = judge_input(case, rec)
            row["applicable_criteria"] = payload["applicable_criteria"]
            row["judge"] = call_judge(client, types, model, system, payload)
        results.append(row)
        status = row.get("skipped") or ("ERROR " + row["judge"]["error"] if "error" in row["judge"]
                                        else ("pass" if row["judge"]["pass"] else "fail"))
        print(f"  {case['id']:<4} {status}")

    judged = [r for r in results if "judge" in r]
    errors = sum(1 for r in judged if "error" in r["judge"])
    passed = sum(1 for r in judged if r["judge"].get("pass") and "error" not in r["judge"])
    RESULTS.mkdir(exist_ok=True)
    run_id = datetime.now().astimezone().strftime("%Y-%m-%dT%H%M%S")
    out = RESULTS / f"judge-{run_id}.json"
    out.write_text(json.dumps({
        "run_id": run_id, "prompt_version": prompt_version(), "model": model,
        "criteria_by_category": CRITERIA_BY_CATEGORY,
        "explanation_quality": {"passed": passed, "total": len(judged), "errors": errors,
                                "value": round(passed / len(judged), 3) if judged else None},
        "cases": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nexplanation_quality {passed}/{len(judged)} (errors count as fails: {errors}); "
          f"skipped {len(results) - len(judged)}")
    print(f"Saved {out.relative_to(EVALS.parent)}. Next: python3 evals/run_judge.py agree")
    return 0


def cmd_agree() -> int:
    runs = sorted(RESULTS.glob("judge-*.json"))
    if not runs:
        sys.exit("no judge run yet: python3 evals/run_judge.py run")
    run = json.loads(runs[-1].read_text(encoding="utf-8"))
    if run["prompt_version"] != prompt_version():
        print(f"! judge_prompt.md changed since that run ({run['prompt_version']} -> {prompt_version()}): run again.")
    labels = {r["id"]: r for r in labeled(read_jsonl(LABELS))}
    per = {c: [0, 0] for c in CRITERIA}
    diffs = []
    for row in run["cases"]:
        lab, j = labels.get(row["id"]), row.get("judge")
        if not lab or not j or "error" in j:
            continue
        for c in lab["applicable_criteria"]:
            per[c][1] += 1
            if j[c]["pass"] == lab["labels"][c]:
                per[c][0] += 1
            else:
                diffs.append(f"  {row['id']:<4} {c}: you {lab['labels'][c]}, judge {j[c]['pass']} - {j[c]['reason']}")
    total = sum(t for _, t in per.values())
    ok = sum(a for a, _ in per.values())
    print(f"Judge run {run['run_id']} (prompt {run['prompt_version']}) vs {len(labels)} labeled cases\n")
    for c, (a, t) in per.items():
        if t:
            print(f"  {c}: {a}/{t} = {a / t:.0%}")
    if not total:
        print("Nothing to compare (no labeled case was judged without error).")
        return 1
    print(f"\n  overall {ok}/{total} = {ok / total:.0%}   target >= {AGREEMENT_TARGET:.0%}  "
          f"{'ok' if ok / total >= AGREEMENT_TARGET else 'MISSED'}")
    errs = [r["id"] for r in run["cases"] if "error" in (r.get("judge") or {})]
    if errs:
        print(f"  judge errors (not compared, count as fails in the run): {', '.join(errs)}")
    if diffs:
        print("\nDisagreements (decide who is right; if it's the judge's fault, revise the prompt and rerun):")
        print("\n".join(diffs))
    return 0 if ok / total >= AGREEMENT_TARGET else 1


def main() -> int:
    p = argparse.ArgumentParser(description="LLM judge for where-is-it AI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("labels", help="add label rows for you to fill")
    r = sub.add_parser("run", help="call the judge (after labeling)")
    r.add_argument("--force", action="store_true", help="run before 20 labels exist (breaks the blind-labeling rule)")
    sub.add_parser("agree", help="compare the latest judge run with your labels")
    s = sub.add_parser("show", help="print what the judge would see for one case")
    s.add_argument("case_id")
    a = p.parse_args()
    if a.cmd == "labels":
        return cmd_labels()
    if a.cmd == "run":
        return cmd_run(a.force)
    if a.cmd == "agree":
        return cmd_agree()
    return cmd_show(a.case_id)


if __name__ == "__main__":
    sys.exit(main())
