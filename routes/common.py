import math
import re

NUMBER_PATTERN = r"-?\d+(?:\.\d+)?"
SURD_PATTERN = r"(\d+(?:\.\d+)?)?\s*√\s*(\d+(?:\.\d+)?)"

def numbers_in(text): #finds all numbers in a text string, used to read the numbers in image notes
    return [float(n) for n in re.findall(NUMBER_PATTERN, text)]

def make_check(name, result, detail): #default structure for a check result
    return {"name": name, "result": result, "detail": detail}

def check(name, ok, pass_detail, fail_detail): #builds a pass or fail check result based on a boolean value
    if ok:
        return make_check(name, "pass", pass_detail)
    return make_check(name, "fail", fail_detail)

def parse_answer(text): #used to read numbers and surds from the answer string, returning its value and a tolerance
    surd = re.search(SURD_PATTERN, text)
    if surd:
        coefficient = float(surd.group(1)) if surd.group(1) else 1.0
        return coefficient * math.sqrt(float(surd.group(2))), 1e-6

    number = re.search(NUMBER_PATTERN, text)
    if number is None:
        return None
    written = number.group()
    decimals = len(written.split(".")[1]) if "." in written else 0
    return float(written), 0.5 * 10 ** -decimals

def matches(result, text): #compares a worked out result to the answer, returning True if they match within the tolerance, or False otherwise 
    if isinstance(result, str):
        return result.strip().lower() == text.strip().lower()
    parsed = parse_answer(text)
    if parsed is None:
        return False
    value, tolerance = parsed
    return abs(value - result) <= tolerance + 1e-9

def show(value): #used to format a value for display in a check result, rounding to 2 decimal places if it is a number
    if isinstance(value, str):
        return value
    return f"{round(value, 2):g}"

def check_values_in_notes(values, question): #checks whether all the values in the spec appear in the image notes
    notes = question.get("image_notes")
    if not notes:
        return make_check("values_match_notes", "skipped", "no image notes given")
    note_numbers = numbers_in(notes)
    missing = [v for v in values if float(v) not in note_numbers]
    return check("values_match_notes", not missing,
                 "every value appears in the image notes",
                 f"values {missing} are not in the image notes")

def check_answer(question, result, what): #uses the matches function to compare the worked out result to the answer or options in the question, returning a check result
    answer = question.get("answer")
    if answer:
        return check("answer_consistency", matches(result, answer),
                     f"{what} is {show(result)}, matching the answer '{answer}'",
                     f"{what} is {show(result)}, but the answer is '{answer}'")

    options = question.get("options", [])
    if options:
        return check("answer_consistency", any(matches(result, option) for option in options),
                     f"no answer given; {what} is {show(result)}, which is one of the options",
                     f"no answer given; {what} is {show(result)}, which is not one of the options")

    return make_check("answer_consistency", "skipped", "no answer or options given")