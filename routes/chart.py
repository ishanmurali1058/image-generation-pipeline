import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NUMBER_PATTERN = r"-?\d+(?:\.\d+)?"
OPERATIONS = ["value", "sum", "difference", "average", "max_label", "min_label"]

def numbers_in(text):
    return [float(n) for n in re.findall(NUMBER_PATTERN, text)]

def make_check(name, result, detail):
    return {"name": name, "result": result, "detail": detail}

def check_spec(plan, question):
    spec = plan["spec"]
    labels = spec["labels"]
    values = [float(v) for v in spec["values"]]
    checks = []

    if len(labels) == len(values):
        checks.append(make_check("labels_values_count", "pass", f"{len(labels)} labels and {len(values)} values"))
    else:
        checks.append(make_check("labels_values_count", "fail", f"{len(labels)} labels but {len(values)} values"))

    if spec["chart_type"] != "pie":
        y_min, y_max, y_step = spec["y_min"], spec["y_max"], spec["y_step"]
        if y_step <= 0:
            checks.append(make_check("axis_range", "fail", f"y_step must be positive, got {y_step}"))
        elif y_min <= min(values) and max(values) <= y_max:
            checks.append(make_check("axis_range", "pass", f"axis {y_min} to {y_max} covers all values"))
        else:
            checks.append(make_check("axis_range", "fail", f"axis {y_min} to {y_max} does not cover values {values}"))

    notes = question.get("image_notes")
    if notes:
        note_numbers = numbers_in(notes)
        missing_values = [v for v in values if v not in note_numbers]
        if missing_values:
            checks.append(make_check("values_match_notes", "fail", f"values {missing_values} are not in the image notes"))
        else:
            checks.append(make_check("values_match_notes", "pass", "every value appears in the image notes"))

        missing_labels = [label for label in labels if label.lower() not in notes.lower()]
        if missing_labels:
            checks.append(make_check("labels_match_notes", "fail", f"labels {missing_labels} are not in the image notes"))
        else:
            checks.append(make_check("labels_match_notes", "pass", "every label appears in the image notes"))
    else:
        checks.append(make_check("values_match_notes", "skipped", "no image notes given"))

    checks.append(check_answer(plan, question, labels, values))
    checks.append(check_answer_not_shown(spec, question))
    return checks

def compute_answer(answer_check, labels, values):
    operation = answer_check.get("operation")
    if operation not in OPERATIONS:
        return None

    lookup = dict(zip(labels, values))
    chosen = answer_check.get("labels") or labels
    picked = [lookup[label] for label in chosen]
    if operation == "value":
        return picked[0]
    if operation == "sum":
        return sum(picked)
    if operation == "difference":
        return picked[0] - picked[1]
    if operation == "average":
        return sum(picked) / len(picked)
    if operation == "max_label":
        return max(chosen, key=lambda label: lookup[label])
    if operation == "min_label":
        return min(chosen, key=lambda label: lookup[label])

def matches(result, text):
    if isinstance(result, str):
        return result.strip().lower() == text.strip().lower()
    numbers = numbers_in(text)
    return bool(numbers) and abs(numbers[0] - result) < 1e-6

def check_answer(plan, question, labels, values):
    answer_check = plan.get("answer_check")
    if not answer_check:
        return make_check("answer_consistency", "skipped", "plan gave no answer_check")

    try:
        result = compute_answer(answer_check, labels, values)
    except (KeyError, IndexError, ZeroDivisionError) as error:
        return make_check("answer_consistency", "fail", f"could not compute the answer from the chart: {error!r}")

    if result is None:
        return make_check("answer_consistency", "skipped", f"operation '{answer_check.get('operation')}' is not supported")

    answer = question.get("answer")
    if answer:
        if matches(result, answer):
            return make_check("answer_consistency", "pass", f"chart gives {result}, matching the answer '{answer}'")
        return make_check("answer_consistency", "fail", f"chart gives {result}, but the answer is '{answer}'")

    options = question.get("options", [])
    if options:
        if any(matches(result, option) for option in options):
            return make_check("answer_consistency", "pass", f"no answer given; chart gives {result}, which is one of the options")
        return make_check("answer_consistency", "fail", f"no answer given; chart gives {result}, which is not one of the options")

    return make_check("answer_consistency", "skipped", "no answer or options given")

def check_answer_not_shown(spec, question):
    answer = (question.get("answer") or "").strip()
    if not answer:
        return make_check("answer_not_shown", "skipped", "no answer given")

    pattern = rf"(?<!\w){re.escape(answer)}(?!\w)"
    for field in ["title", "x_label", "y_label"]:
        text = str(spec.get(field, ""))
        if re.search(pattern, text, flags=re.IGNORECASE):
            return make_check("answer_not_shown", "fail", f"the answer '{answer}' appears in the {field}: '{text}'")
    return make_check("answer_not_shown", "pass", "the answer does not appear in the title or axis labels")

def check_render(plan, files):
    expected = [float(v) for v in plan["spec"]["values"]]
    drawn = files.get("drawn_values", [])
    if len(drawn) == len(expected) and all(abs(d - e) < 1e-9 for d, e in zip(drawn, expected)):
        return [make_check("drawn_matches_spec", "pass", f"drawn values {drawn} match the spec")]
    return [make_check("drawn_matches_spec", "fail", f"drawn values {drawn} do not match the spec {expected}")]

def render(spec, png_path, svg_path):
    labels = spec["labels"]
    values = spec["values"]
    chart_type = spec["chart_type"]

    if len(labels) != len(values):
        raise ValueError(f"{len(labels)} labels but {len(values)} values")

    fig, ax = plt.subplots(figsize=(7, 5))
    if chart_type == "bar":
        bars = ax.bar(labels, values, color="#4C72B0", edgecolor="black", linewidth=0.8)
        drawn_values = [bar.get_height() for bar in bars]
    elif chart_type == "line":
        line, = ax.plot(labels, values, marker="o", color="#4C72B0", linewidth=2)
        drawn_values = list(line.get_ydata())
    elif chart_type == "pie":
        ax.pie(values, labels=labels, startangle=90, wedgeprops={"edgecolor": "white"})
        ax.axis("equal")
        drawn_values = list(values)
    else:
        plt.close(fig)
        raise ValueError(f"Unknown chart type: {chart_type}")

    if chart_type != "pie":
        y_min = spec["y_min"]
        y_max = spec["y_max"]
        y_step = spec["y_step"]
        ax.set_ylim(y_min, y_max)
        ax.set_yticks(np.arange(y_min, y_max + y_step / 2, y_step))
        ax.set_xlabel(spec.get("x_label", ""), fontsize=12)
        ax.set_ylabel(spec.get("y_label", ""), fontsize=12)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    ax.set_title(spec.get("title", ""), fontsize=14)
    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    fig.savefig(svg_path)
    plt.close(fig)

    return {"drawn_values": [float(v) for v in drawn_values]}