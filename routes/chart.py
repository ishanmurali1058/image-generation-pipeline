import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .common import check, check_answer, check_values_in_notes, make_check

OPERATIONS = ["value", "sum", "difference", "average", "max_label", "min_label"]

def check_spec(plan, question):
    spec = plan["spec"]
    labels = spec["labels"]
    values = [float(v) for v in spec["values"]]

    checks = [check("labels_values_count", len(labels) == len(values),
                    f"{len(labels)} labels and {len(values)} values",
                    f"{len(labels)} labels but {len(values)} values")]

    if spec["chart_type"] != "pie":
        y_min, y_max, y_step = spec["y_min"], spec["y_max"], spec["y_step"]
        checks.append(check("axis_range", y_step > 0 and y_min <= min(values) and max(values) <= y_max,
                            f"axis {y_min} to {y_max} covers all values",
                            f"axis {y_min} to {y_max} in steps of {y_step} does not fit values {values}"))

    checks.append(check_values_in_notes(values, question))

    notes = question.get("image_notes")
    if notes:
        missing_labels = [label for label in labels if label.lower() not in notes.lower()]
        checks.append(check("labels_match_notes", not missing_labels,
                            "every label appears in the image notes",
                            f"labels {missing_labels} are not in the image notes"))

    checks.append(chart_answer_check(plan, question, labels, values))
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
        return abs(picked[0] - picked[1])
    if operation == "average":
        return sum(picked) / len(picked)
    if operation == "max_label":
        return max(chosen, key=lambda label: lookup[label])
    if operation == "min_label":
        return min(chosen, key=lambda label: lookup[label])

def chart_answer_check(plan, question, labels, values):
    answer_check = plan.get("answer_check")
    if not answer_check:
        return make_check("answer_consistency", "skipped", "plan gave no answer_check")

    try:
        result = compute_answer(answer_check, labels, values)
    except (KeyError, IndexError, ZeroDivisionError) as error:
        return make_check("answer_consistency", "fail", f"could not compute the answer from the chart: {error!r}")

    if result is None:
        return make_check("answer_consistency", "skipped", f"operation '{answer_check.get('operation')}' is not supported")

    return check_answer(question, result, "the answer worked out from the chart")

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
    same = len(drawn) == len(expected) and all(abs(d - e) < 1e-9 for d, e in zip(drawn, expected))
    return [check("drawn_matches_spec", same,
                  f"drawn values {drawn} match the spec",
                  f"drawn values {drawn} do not match the spec {expected}")]

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
        y_min, y_max, y_step = spec["y_min"], spec["y_max"], spec["y_step"]
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