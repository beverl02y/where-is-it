#!/usr/bin/env python3
"""Run the Gemini parsing prompt (parse_query.md) on the checklist questions and
write a Test Run Log section to paste into parse_query.md.

Each question is sent to Gemini once (no retries), with the prompt between
<!-- prompt:start --> and <!-- prompt:end --> as the system instruction. Each output is
graded automatically:
  1. pure JSON (no code fences or extra text)
  2. valid against query.schema.json
  3. every questionText is an exact part of the question; lang matches the question
  4. equal to the expected Queries below (questionText, objectName, descriptors,
     lang, limitationRequest)

Usage (from the repository root):
  pip install google-genai jsonschema
  export GEMINI_API_KEY=your-key
  python evals/run_parse_prompt.py                        # all cases, gemini-3.8-flash
  python evals/run_parse_prompt.py --only 2,7,19          # some cases
  python evals/run_parse_prompt.py --fake                 # no Gemini call: checks the script itself

Writes prompt_test_log.md (the section to paste) and prompt_test_raw.json (every raw output).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
HANGUL = re.compile(r"[가-힣]")


def q(text, obj, lang="en", desc=None, limit=False):
    d = {"questionText": text, "objectName": obj, "lang": lang}
    if desc:
        d["descriptors"] = desc
    if limit:
        d["limitationRequest"] = True
    return d


# (checklist #, question, expected Queries). Numbers follow the Failure Mode Checklist in
# parse_query.md. #14 (length) and #21-#24 (outside the service / instruction with no
# item) are handled in code before Gemini and are not sent to the model.
CASES = [
    (1, "Where's my phone? It's not on the desk.", [q("Where's my phone? It's not on the desk.", "phone")]),
    (2, "Ugh, where did that thing go", [q("Ugh, where did that thing go", None)]),
    (3, "Where's my wallet?", [q("Where's my wallet?", "wallet")]),
    (4, "Where is my black wallet?", [q("Where is my black wallet?", "wallet", desc=["black"])]),
    (5, "Where's my lighter?", [q("Where's my lighter?", "lighter")]),
    (6, "Where is my card wallet?", [q("Where is my card wallet?", "card wallet")]),
    (7, "Where are my phone and wallet?", [q("Where are my phone", "phone"), q("wallet", "wallet")]),
    (8, "Where is my cable?", [q("Where is my cable?", "cable")]),
    (9, "Where are my glasses?", [q("Where are my glasses?", "glasses")]),
    (10, "지갑 어디 있어?", [q("지갑 어디 있어?", "지갑", "ko")]),
    (11, "휴대폰 어디 있어?", [q("휴대폰 어디 있어?", "휴대폰", "ko")]),
    (12, "Exactly when did my phone disappear?", [q("Exactly when did my phone disappear?", "phone", limit=True)]),
    (13, "Did my cat move my glasses?", [q("Did my cat move my glasses?", "glasses", limit=True)]),
    (15, "Where is my black and white wallet?", [q("Where is my black and white wallet?", "wallet", desc=["black", "white"])]),
    (16, "Where is my phone wallet?", [q("Where is my phone wallet?", "phone wallet")]),
    (17, "핸드폰이랑 지갑 어디 있어?", [q("핸드폰", "핸드폰", "ko"), q("지갑 어디 있어", "지갑", "ko")]),
    (18, "Where are my glases?", [q("Where are my glases?", "glasses")]),
    (19, "지값 어디 있어?", [q("지값 어디 있어?", "지갑", "ko")]),
    (20, "드폰 어디 있어?", [q("드폰 어디 있어?", "드폰", "ko")]),
    (25, "Forget the camera, where is my phone?", [q("Forget the camera, where is my phone?", "phone")]),
    (26, "Where is my jacket?", [q("Where is my jacket?", "jacket")]),
    (27, "Where is the thing I drink from?", [q("Where is the thing I drink from?", None)]),
    (28, "Where do I usually leave my wallet?", [q("Where do I usually leave my wallet?", "wallet")]),
]


def read_prompt(md: Path) -> tuple[str, str]:
    text = md.read_text(encoding="utf-8-sig").replace("\r\n", "\n")   # also accept Windows line endings
    m = re.search(r"<!--\s*prompt:start\s*-->\s*\n(.*?)\n\s*<!--\s*prompt:end\s*-->", text, re.S)
    if not m:
        sys.exit(f"No prompt markers found in {md}.\n"
                 "This is probably an older parse_query.md without the Gemini prompt section. Download the "
                 "latest one from the chat; check with: grep -c 'prompt:start' " + str(md) + "  (should print 1)")
    v = (re.search(r"^\|\s*prompt_version\s*\|\s*(\d+)\s*\|", text, re.M)     # header table row
         or re.search(r"prompt_version (\d+)", text))
    return m.group(1), (v.group(1) if v else "?")


def git_commit(path: Path) -> str:
    try:
        return subprocess.run(["git", "log", "-1", "--format=%h", "--", str(path)], capture_output=True,
                              text=True, cwd=path.parent, timeout=10).stdout.strip() or "not committed"
    except Exception:
        return "unknown"


def norm(query: dict) -> tuple:
    return (query.get("questionText"), query.get("objectName"), query.get("lang"),
            tuple(sorted(w.lower() for w in query.get("descriptors") or [])),
            bool(query.get("limitationRequest", False)))


def grade(question: str, raw: str, expected: list, validator) -> tuple[str, str]:
    try:
        data = json.loads(raw)
    except Exception:
        return "FAIL", "not pure JSON"
    errs = sorted({e.message for e in validator.iter_errors(data)})
    if errs:
        return "FAIL", "schema: " + "; ".join(errs)[:150]
    got = data["queries"]
    bad_text = [x["questionText"] for x in got if x["questionText"] not in question]
    if bad_text:
        return "FAIL", f"questionText not copied exactly: {bad_text[0]!r}"
    want_lang = "ko" if HANGUL.search(question) else "en"
    if any(x["lang"] != want_lang for x in got):
        return "FAIL", f"lang should be {want_lang}"
    if [norm(x) for x in got] != [norm(x) for x in expected]:
        if len(got) != len(expected):
            return "FAIL", f"{len(got)} Queries, expected {len(expected)}"
        for g, w in zip(got, expected):
            for i, field in enumerate(["questionText", "objectName", "lang", "descriptors", "limitationRequest"]):
                if norm(g)[i] != norm(w)[i]:
                    return "FAIL", f"{field}: got {norm(g)[i]!r}, expected {norm(w)[i]!r}"
    return "PASS", ""


def cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--prompt", default="src/whereisit/prompts/parse_query.md")
    ap.add_argument("--schema", default="src/whereisit/schemas/query.schema.json")
    ap.add_argument("--only", default="", help="comma-separated checklist numbers, e.g. 2,7,19")
    ap.add_argument("--fake", action="store_true", help="no Gemini call: answer with the expected output")
    ap.add_argument("--out", default="prompt_test_log.md")
    a = ap.parse_args()

    import jsonschema
    prompt_path, schema_path = Path(a.prompt), Path(a.schema)
    prompt, version = read_prompt(prompt_path)
    schema_bytes = schema_path.read_bytes()
    validator = jsonschema.Draft7Validator(json.loads(schema_bytes))
    cases = [c for c in CASES if not a.only or str(c[0]) in a.only.split(",")]
    print(f"Testing prompt_version {version} from {prompt_path} ({len(prompt.split())} words)")
    if version != "3":
        print("WARNING: these test cases are written for prompt_version 3; an older prompt will fail many of them.")

    client = None
    if not a.fake:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            sys.exit("Set GEMINI_API_KEY first (or use --fake to check the script).")
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        config = types.GenerateContentConfig(system_instruction=prompt, response_mime_type="application/json")

    rows, raw_log = [], []
    for no, question, expected in cases:
        t0 = time.perf_counter()
        try:
            if a.fake:
                raw = json.dumps({"queries": expected}, ensure_ascii=False, separators=(",", ":"))
            else:
                raw = (client.models.generate_content(model=a.model, contents=question, config=config).text or "").strip()
            result, why = grade(question, raw, expected, validator)
        except Exception as e:  # network, quota, model errors
            raw, result, why = "", "ERROR", f"{type(e).__name__}: {str(e)[:120]}"
        ms = round((time.perf_counter() - t0) * 1000)
        when = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
        rows.append((no, question, raw, result, why, ms, when))
        raw_log.append({"no": no, "question": question, "output": raw, "expected": expected,
                        "result": result, "reason": why, "ms": ms, "time_kst": when})
        print(f"#{no:<3} {result:5} {ms:>6} ms  {question}" + (f"  — {why}" if why else ""))
        if not a.fake:
            time.sleep(1)                                  # stay under the free-tier rate limit

    passed = sum(r[3] == "PASS" for r in rows)
    model = "none (--fake)" if a.fake else a.model
    lines = [
        f"## Test Run Log — Gemini Prompt Tests (prompt_version {version}, {datetime.now(KST):%Y-%m-%d})",
        "",
        f"- **Model:** `{model}` · one call per question, no retries · system instruction = the prompt between the markers · `response_mime_type: application/json`",
        f"- **Prompt:** `{prompt_path.as_posix()}` prompt_version {version} · SHA-256 of prompt text `{hashlib.sha256(prompt.encode()).hexdigest()[:16]}…` · file commit `{git_commit(prompt_path)}`",
        f"- **Schema:** `{schema_path.as_posix()}` · SHA-256 `{hashlib.sha256(schema_bytes).hexdigest()[:16]}…` · file commit `{git_commit(schema_path)}`",
        "- **Grading (automatic, `evals/run_parse_prompt.py`):** pure JSON → schema → questionText copied exactly and lang correct → equal to the expected Queries (questionText, objectName, descriptors, lang, limitationRequest).",
        "- **Not sent to the model:** #14 (length check) and #21–#24 (outside the service, instruction with no item) are handled in code before the parser.",
        "",
        "| # | Input | Actual output | Result | Time (ms) | Run at (KST) |",
        "|---|---|---|---|---|---|",
    ]
    for no, question, raw, result, why, ms, when in rows:
        res = f"**{result}**" + (f" — {cell(why)}" if why else "")
        lines.append(f"| {no} | {cell(question)} | `{cell(raw) or '—'}` | {res} | {ms} | {when} |")
    lines += ["", f"**Summary:** {passed}/{len(rows)} PASS. These results test the prompt's parsing only; "
                  "searching camera records and the answers shown to users are tested separately."]
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path(a.out).with_name("prompt_test_raw.json").write_text(json.dumps(raw_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(rows)} PASS. Wrote {a.out} and prompt_test_raw.json")


if __name__ == "__main__":
    main()
