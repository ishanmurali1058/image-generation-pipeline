import json

def build_feedback(plan, verification):
    failed = [check for check in verification["checks"] if check["result"] == "fail"]
    problems = "\n".join(f"- {check['name']}: {check['detail']}" for check in failed)

    previous = {key: plan[key] for key in ["route", "spec", "answer_check"] if key in plan}

    return (
        "Your previous plan for this question failed these checks:\n"
        f"{problems}\n\n"
        "Your previous plan was:\n"
        f"{json.dumps(previous, ensure_ascii=False, indent=2)}\n\n"
        "Write a corrected plan that fixes these problems. "
        "Never change values given in the image notes just to make a check pass. "
        "Reply with the full JSON plan only."
    )