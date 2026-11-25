import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

INPUT = BASE / "live_candidates.jsonl"
OUTPUT = BASE / "live_reviewed.jsonl"

records = [
    json.loads(line)
    for line in INPUT.read_text(encoding="utf-8").splitlines()
    if line.strip()
]

# Resume from previously reviewed records
if OUTPUT.exists():
    records = [
        json.loads(line)
        for line in OUTPUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def save():
    with OUTPUT.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


for index, record in enumerate(records, start=1):

    if record.get("expect"):
        continue

    print("\n" + "=" * 60)
    print(f"CASE {index}/{len(records)}")
    print("ID:", record["id"])
    print("QUERY:", record.get("query"))

    print("\nAI ANSWER:")
    print(json.dumps(
        record.get("answer"),
        indent=2,
        ensure_ascii=False
    ))

    print("\nCAMERA RECORDS:")
    print(json.dumps(
        record.get("camera_saw"),
        indent=2,
        ensure_ascii=False
    ))

    print("\nEnter independently verified expected conditions.")
    print('Example: {"status":"current","location":"on the desk"}')
    print("Type 'skip' if ground truth is unavailable.")
    print("Type 'quit' to save and exit.")

    while True:
        value = input("\nEXPECT > ").strip()

        if value.lower() == "quit":
            save()
            print(f"Saved to {OUTPUT}")
            raise SystemExit

        if value.lower() == "skip":
            record["review_status"] = "needs_ground_truth"
            break

        try:
            expected = json.loads(value)

            if not isinstance(expected, dict) or not expected:
                print("Please enter a non-empty JSON object.")
                continue

            record["expect"] = expected
            record["graders"] = ["code", "human"]

            decision = input(
                "Human result (PASS/FAIL/UNSURE): "
            ).strip().upper()

            if decision not in {"PASS", "FAIL", "UNSURE"}:
                decision = "UNSURE"

            record["human_result"] = {
                "decision": decision,
                "reason": input("Reason: ").strip()
            }

            break

        except json.JSONDecodeError:
            print("Invalid JSON. Please try again.")

    save()

print("\nReview completed.")
print(f"Saved to: {OUTPUT}")