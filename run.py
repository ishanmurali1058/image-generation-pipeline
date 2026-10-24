import argparse
import csv
import json
from pathlib import Path

from pipeline.stages import understand, generate, verify

MAX_ATTEMPTS = 3

def process_question(question, out_dir):
    attempts = []
    total_cost = 0.0
    status = "flagged"

    for attempt_number in range(1, MAX_ATTEMPTS + 1):
        plan = understand(question)
        files = generate(plan, question, out_dir)
        check = verify(plan, question, files)

        cost = plan["cost"] + files["cost"] + check["cost"]
        total_cost += cost
        attempts.append({
            "attempt": attempt_number,
            "verification": check,
            "cost_usd": cost,
        })

        if check["passed"]:
            status = "accepted"
            break

    metadata = {
        "id": question["id"],
        "route": plan["route"],
        "route_reason": plan["route_reason"],
        "spec": plan["spec"],
        "attempts": len(attempts),
        "attempt_log": attempts,
        "status": status,
        "cost_usd": round(total_cost, 6),
    }

    with open(out_dir / f"{question['id']}.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return metadata

def write_summary(results, out_dir):
    total = sum(r["cost_usd"] for r in results)
    average = total / len(results) if results else 0.0

    with open(out_dir / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "status", "route", "attempts", "cost_usd"])
        for r in results:
            writer.writerow([r["id"], r["status"], r["route"], r["attempts"], r["cost_usd"]])
        writer.writerow([])
        writer.writerow(["total_cost_usd", round(total, 6)])
        writer.writerow(["average_cost_usd", round(average, 6)])

def main():
    parser = argparse.ArgumentParser(description="Generate and verify images for assessment questions.")
    parser.add_argument("--input", required=True, help="Path to the questions JSON file")
    parser.add_argument("--out", required=True, help="Folder to write outputs into")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.input, encoding="utf-8") as f:
        questions = json.load(f)

    results = []
    for question in questions:
        print(f"Processing {question['id']}...")
        results.append(process_question(question, out_dir))

    write_summary(results, out_dir)
    print(f"Done. {len(results)} questions processed.")

if __name__ == "__main__":
    main()