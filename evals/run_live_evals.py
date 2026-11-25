import json
from pathlib import Path
from datetime import datetime, timezone

from run_evals import code_checks

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "live_candidates.jsonl"
RESULTS_DIR = BASE_DIR / "results"


def load_records():
    records = []

    with open(INPUT_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    return records


def run_live_evals():
    records = load_records()
    results = []

    passed = 0
    failed = 0
    skipped = 0

    for record in records:

        case_id = record["id"]
        actual = record.get("answer")
        expected = record.get("expect")

        if not expected or not isinstance(actual, dict):
            skipped += 1
            print(f"{case_id}: SKIPPED")
            continue

        # Reuse existing code grader
        checks = code_checks(actual, expected)

        code_passed = checks["pass"]

        if code_passed:
            passed += 1
        else:
            failed += 1

        results.append({
            "id": case_id,
            "query": record.get("query"),
            "expected": expected,
            "actual": actual,
            "code_result": checks,
            "human_note": record.get("note")
        })

        status = "PASS" if code_passed else "FAIL"

        print(f"{case_id}: {status}")

    total = passed + failed

    pass_rate = (
        passed / total * 100
        if total > 0 else 0
    )

    print("\n===== LIVE CODE EVALUATION =====")
    print(f"Total Records: {len(records)}")
    print(f"Evaluated: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"Pass Rate: {pass_rate:.2f}%")

    RESULTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    output_file = (
        RESULTS_DIR / f"live_{timestamp}.json"
    )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "mode": "live_record_replay",
                "timestamp": timestamp,
                "total": len(records),
                "evaluated": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "pass_rate": pass_rate,
                "results": results
            },
            f,
            indent=2,
            ensure_ascii=False
        )

    print(f"\nResults saved: {output_file}")


if __name__ == "__main__":
    run_live_evals()