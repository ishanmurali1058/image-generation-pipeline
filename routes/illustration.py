import json
import re

from pipeline.images import generate_image
from pipeline.llm import call_llm

from .common import check, make_check, matches

REQUIRED_FIELDS = ["prompt", "style", "must_contain", "answer_from_image"]
NO_TEXT = "No text, letters, numbers, labels, signs or writing anywhere in the image."

JUDGE_PROMPT = """You check pictures used in school assessment questions for Grades 3 to 10.
Look carefully at the picture and reply with ONLY a JSON object, no other text:
{
  "description": "two or three sentences describing what the picture shows",
  "checklist": [true or false for each checklist item, in the same order],
  "visible_text": "any letters, words or numbers you can see, or an empty string",
  "suitable_for_children": true or false,
  "defects": ["only serious drawing errors a student would notice, such as extra limbs or badly distorted faces; ignore small imperfections"],
  "chosen_option": "the option a student would choose from the picture alone, or null"
}
Mark a checklist item true if a student would clearly recognise it in the picture, even if it is small or partly hidden. Be honest."""

def check_spec(plan, question): #the checks done on the illustration spec before drawing the image
    spec = plan["spec"]
    missing = [key for key in REQUIRED_FIELDS if key not in spec]
    if missing:
        return [make_check("spec_format", "fail", f"the spec is missing the fields {missing}; use the illustration spec format")]

    problems = []
    if not isinstance(spec["prompt"], str) or not spec["prompt"].strip():
        problems.append("prompt must be a description of the scene")
    items = spec["must_contain"]
    if not isinstance(items, list) or not 1 <= len(items) <= 5:
        problems.append("must_contain must list 1 to 5 things")
    if problems:
        return [make_check("spec_format", "fail", "; ".join(problems))]

    quoted = re.findall(r'["“”][^"“”]+["“”]', spec["prompt"])
    return [make_check("spec_format", "pass", "the spec is a valid illustration"),
            check("no_quoted_text", not quoted,
                  "the prompt asks for no written words",
                  f"the prompt asks for written words {quoted}, which image models misspell")]

def render(spec, png_path, svg_path): #builds the full prompt and generates the image using FLUX
    full_prompt = f"{spec['prompt']} Style: {spec['style']}. {NO_TEXT}"
    try:
        result = generate_image(full_prompt, png_path)
    except Exception as error:
        raise ValueError(f"image generation failed: {error}") from error
    return {"cost": result["cost"], "safety_flagged": result["safety_flagged"]}

def judge_message(spec, question): #writes the message to send to the judge LLM (Claude Haiku 5.5) 
    lines = ["Checklist:"]
    for number, item in enumerate(spec["must_contain"], start=1):
        lines.append(f"{number}. {item}")

    options = question.get("options")
    if spec["answer_from_image"] and options:
        lines.append(f"Question: {question['question']}")
        lines.append(f"Options: {json.dumps(options, ensure_ascii=False)}")
    else:
        lines.append("There is no question to answer, so set chosen_option to null.")
    return "\n".join(lines)

def redraw_check(name, ok, pass_detail, fail_detail): #adds a fix field to the check result to indicate that the image should be redrawn if the check fails
    result = check(name, ok, pass_detail, fail_detail)
    result["fix"] = "redraw"
    return result

def check_render(plan, files, question=None): #calls the judge LLM to verify the generated image against the spec and question with a numbers of checks
    spec = plan["spec"]
    question = question or {}
    result = call_llm(JUDGE_PROMPT, judge_message(spec, question), max_tokens=1500, image_path=files["png"])

    text = result["text"]
    try:
        report = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except json.JSONDecodeError:
        failed = redraw_check("judge", False, "", "the judge's reply was not valid JSON")
        failed["cost"] = result["cost"]
        return [failed]

    checks = [make_check("judge_description", "pass", report.get("description", ""))]
    checks[0]["cost"] = result["cost"]

    checks.append(redraw_check("safety", not files.get("safety_flagged"),
                               "the image model's safety filter found nothing",
                               "the image model's safety filter flagged the image"))

    seen = report.get("checklist") or []
    missing = [item for item, ok in zip(spec["must_contain"], seen) if not ok]
    if len(seen) != len(spec["must_contain"]):
        missing = spec["must_contain"]
    checks.append(redraw_check("must_contain", not missing,
                               "the judge sees everything on the checklist",
                               f"the judge does not see {missing}"))

    visible_text = (report.get("visible_text") or "").strip()
    checks.append(redraw_check("no_text_in_image", not visible_text,
                               "the judge sees no text in the image",
                               f"the judge sees text in the image: '{visible_text}'"))

    checks.append(redraw_check("suitable_for_children", report.get("suitable_for_children") is True,
                               "the judge finds the image suitable for children",
                               "the judge finds the image unsuitable for children"))

    defects = report.get("defects") or []
    checks.append(redraw_check("no_visible_defects", not defects,
                               "the judge sees no drawing errors",
                               f"the judge sees drawing errors: {defects}"))

    checks.append(option_check(spec, question, report.get("chosen_option")))
    return checks

def option_check(spec, question, chosen): #checks that the option chosen by the judge matches the answer or one of the options in the question
    options = question.get("options")
    if not spec["answer_from_image"] or not options:
        return make_check("answer_consistency", "skipped", "the answer does not depend on the picture")
    if not chosen:
        return redraw_check("answer_consistency", False, "", "the judge could not choose an option from the picture")

    answer = question.get("answer")
    if answer:
        return redraw_check("answer_consistency", matches(chosen, answer),
                            f"from the picture alone the judge chose '{chosen}', matching the answer",
                            f"from the picture alone the judge chose '{chosen}', but the answer is '{answer}'")
    return redraw_check("answer_consistency", any(matches(chosen, o) for o in options),
                        f"no answer given; the judge chose '{chosen}', which is one of the options",
                        f"no answer given; the judge chose '{chosen}', which is not one of the options")