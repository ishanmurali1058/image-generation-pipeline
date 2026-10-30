import argparse
import csv
import json
import re
import sys
from pathlib import Path

from pipeline.repair import build_feedback
from pipeline.stages import understand, generate, verify, draw_placeholder

MAX_ATTEMPTS = 3


def process_question(question, out_dir): #takes each question and processes it through the pipeline, returning the metadata for the question
    attempts = []
    total_cost = 0.0
    status = "flagged"
    feedback = None
    plan = None

    for attempt_number in range(1, MAX_ATTEMPTS + 1):
        reuse_plan = plan is not None and feedback is None
        if not reuse_plan:
            plan = understand(question, feedback)
        plan_cost = 0.0 if reuse_plan else plan["cost"]

        files = generate(plan, question, out_dir)
        check = verify(plan, question, files)

        cost = plan_cost + files["cost"] + check["cost"]
        total_cost += cost
        attempts.append({
            "attempt": attempt_number,
            "plan_reused": reuse_plan,
            "repair_feedback": feedback,
            "verification": check,
            "cost_usd": cost,
        })

        if check["passed"]:
            status = "accepted"
            break

        if not check.get("retryable", True):
            break

        if check.get("redraw"):
            feedback = None
        else:
            feedback = build_feedback(plan, check)

    flag_reason = None
    if status == "flagged":
        flag_reason = [c["detail"] for c in check["checks"] if c["result"] == "fail"]

    metadata = {
        "id": question["id"],
        "route": plan["route"],
        "route_reason": plan["route_reason"],
        "must_show": plan.get("must_show", ""),
        "must_not_show": plan.get("must_not_show", []),
        "spec": plan["spec"],
        "attempts": len(attempts),
        "attempt_log": attempts,
        "status": status,
        "flag_reason": flag_reason,
        "cost_usd": round(total_cost, 6),
    }

    with open(out_dir / f"{question['id']}.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return metadata


def safe_process(question, out_dir, number): #used to safely process a question and handle any errors that may occur during processing
    if not isinstance(question, dict):
        question = {"question": str(question)}
    raw_id = str(question.get("id") or f"Q-{number:03d}")
    question["id"] = re.sub(r"[^\w\-]", "_", raw_id)
    try:
        return process_question(question, out_dir)
    except Exception as error:
        return flag_after_error(question, out_dir, error)


def flag_after_error(question, out_dir, error): #used to draw a placeholder image and create a metadata file for a question that encountered an error during processing
    try:
        draw_placeholder(question, out_dir / f"{question['id']}.png")
    except Exception:
        pass
    metadata = {
        "id": question["id"],
        "route": None,
        "route_reason": "",
        "spec": {},
        "attempts": 0,
        "attempt_log": [],
        "status": "flagged",
        "flag_reason": [f"unexpected error: {error!r}"],
        "cost_usd": 0.0,
    }
    with open(out_dir / f"{question['id']}.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    return metadata


def load_questions(path): #used to read the questions from questions.json
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as error:
        sys.exit(f"Could not read the input file {path}: {error}")
    if isinstance(data, dict) and isinstance(data.get("questions"), list):
        data = data["questions"]
    if not isinstance(data, list):
        sys.exit("The input file must contain a list of questions.")
    return data


def write_summary(results, out_dir): #used to write a summary of the results to a CSV file (summary.csv)
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


def main(): #runs every part of the pipeline, from reading the questions to writing the summary
    parser = argparse.ArgumentParser(description="Generate and verify images for assessment questions.")
    parser.add_argument("--input", required=True, help="Path to the questions JSON file")
    parser.add_argument("--out", required=True, help="Folder to write outputs into")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    questions = load_questions(args.input)

    results = []
    for number, question in enumerate(questions, start=1):
        print(f"Processing question {number} of {len(questions)}...")
        results.append(safe_process(question, out_dir, number))

    write_summary(results, out_dir)
    print(f"Done. {len(results)} questions processed.")


if __name__ == "__main__":
    main()