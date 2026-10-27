import re

import matplotlib
matplotlib.use("Agg")
import schemdraw
import schemdraw.elements as elm

from .common import check, check_answer, check_values_in_notes, make_check

UNIT = 3
BRANCH_GAP = 3.6
SYMBOLS = {"cell": elm.BatteryCell, "battery": elm.Battery, "bulb": elm.Lamp2, "resistor": elm.Resistor,
           "ammeter": elm.MeterA, "voltmeter": elm.MeterV, "switch": elm.Switch}
COMPONENT_TYPES = ["bulb", "resistor", "switch", "ammeter", "voltmeter"]


def components(spec):
    every = list(spec["series"])
    for branch in spec["branches"]:
        every += branch
    return every


def conducts(component, removed, switches):
    if component.get("label") in removed or component["type"] == "voltmeter":
        return False
    if component["type"] == "switch":
        return switches.get(component.get("label"), component.get("state")) == "closed"
    return True


def path_complete(parts, removed, switches):
    for component in parts:
        if not conducts(component, removed, switches):
            return False
    return True


def is_lit(spec, target, removed, switches):
    series_ok = path_complete(spec["series"], removed, switches)
    branch_ok = []
    for branch in spec["branches"]:
        branch_ok.append(path_complete(branch, removed, switches))

    if not series_ok or (branch_ok and not any(branch_ok)) or target in removed:
        return False
    for branch, ok in zip(spec["branches"], branch_ok):
        if target in [c.get("label") for c in branch]:
            return ok
    return True


def resistance_of(parts):
    resistors = [c for c in parts if c["type"] in ("bulb", "resistor")]
    missing = [c.get("label") or c["type"] for c in resistors if c.get("ohms") is None]
    if missing:
        raise ValueError(f"{missing} have no resistance value")
    return sum(c["ohms"] for c in resistors)


def total_resistance(spec):
    branch_values = []
    for branch in spec["branches"]:
        has_voltmeter = any(c["type"] == "voltmeter" for c in branch)
        if not has_voltmeter:
            branch_values.append(resistance_of(branch))

    if 0 in branch_values:
        raise ValueError("a branch has no resistance, so it would short the circuit")

    total = resistance_of(spec["series"])
    if branch_values:
        total += 1 / sum(1 / r for r in branch_values)
    return total


def check_spec(plan, question):
    spec = plan["spec"]
    missing = [key for key in ["source", "series", "branches"] if key not in spec]
    if missing:
        return [make_check("spec_format", "fail", f"the spec is missing the fields {missing}; use the circuit spec format")]

    parts = components(spec)
    labels = [c["label"] for c in parts if c.get("label")]

    problems = []
    if spec["source"].get("type") not in ("cell", "battery"):
        problems.append("the source must be a cell or battery")
    if not parts:
        problems.append("the circuit has no components")
    for c in parts:
        if c.get("type") not in COMPONENT_TYPES:
            problems.append(f"unknown component type '{c.get('type')}'")
        elif c["type"] == "switch" and c.get("state") not in ("open", "closed"):
            problems.append(f"switch {c.get('label')} needs a state of open or closed")
    if len(labels) != len(set(labels)):
        problems.append("two components share a label")
    if problems:
        return [make_check("spec_format", "fail", "; ".join(problems))]

    checks = [make_check("spec_format", "pass", "the spec is a valid circuit")]
    notes = (question.get("image_notes") or "").lower()
    if notes:
        missing_labels = [label for label in labels if label.lower() not in notes]
        checks.append(check("labels_match_notes", not missing_labels,
                            "every component label appears in the image notes",
                            f"labels {missing_labels} are not in the image notes"))
        said = [word for word in ("series", "parallel") if word in notes]
        if len(said) == 1:
            parallel = len(spec["branches"]) >= 2
            checks.append(check("arrangement_matches_notes", parallel == (said[0] == "parallel"),
                                f"the notes say {said[0]} and the circuit matches",
                                f"the notes say {said[0]} but the circuit does not match"))

    values = []
    for c in parts + [spec["source"]]:
        for key in ("ohms", "volts"):
            if c.get(key) is not None:
                values.append(c[key])

    checks.append(check_values_in_notes(values, question))
    checks.append(circuit_answer_check(plan, question))
    checks.append(check_answer_not_shown(spec, question))
    return checks


def circuit_answer_check(plan, question):
    spec = plan["spec"]
    answer_check = plan.get("answer_check") or {}
    operation = answer_check.get("operation")
    try:
        if operation == "lit":
            target = answer_check["target"]
            lit = is_lit(spec, target, answer_check.get("removed", []), answer_check.get("switches", {}))
            state = "glows" if lit else "does not glow"
            return check("answer_consistency", lit == answer_check["expected"],
                         f"in the drawn circuit {target} {state}, which matches the answer",
                         f"in the drawn circuit {target} {state}, which contradicts the answer")
        if operation == "total_resistance":
            return check_answer(question, total_resistance(spec), "the total resistance of the drawn circuit")
        if operation == "current":
            if spec["source"].get("volts") is None:
                raise ValueError("the source has no voltage")
            current = spec["source"]["volts"] / total_resistance(spec)
            return check_answer(question, current, "the current in the drawn circuit")
    except (KeyError, ValueError, ZeroDivisionError) as error:
        return make_check("answer_consistency", "fail", f"could not work out the answer from the circuit: {error!r}")
    return make_check("answer_consistency", "skipped", f"operation '{operation}' cannot be checked")


def check_answer_not_shown(spec, question):
    answer = (question.get("answer") or "").strip()
    if not answer or answer in [c.get("label") for c in components(spec)]:
        return make_check("answer_not_shown", "skipped", "no answer given, or the answer is a component name")

    pattern = rf"(?<!\w){re.escape(answer)}(?!\w)"
    shown = []
    for component in components(spec) + [spec["source"]]:
        text = label_text(component)
        if re.search(pattern, text, re.IGNORECASE):
            shown.append(text)

    return check("answer_not_shown", not shown, "the answer does not appear in any label",
                 f"the answer '{answer}' appears in the labels {shown}")


def check_render(plan, files, question = None):
    spec = plan["spec"]
    expected = []
    for component in components(spec) + [spec["source"]]:
        expected.append(SYMBOLS[component["type"]].__name__)
    expected.sort()
    drawn = sorted(files.get("drawn_symbols", []))
    return [check("drawn_matches_spec", drawn == expected,
                  f"the drawing has exactly the {len(expected)} symbols in the spec",
                  f"the drawing has symbols {drawn} but the spec needs {expected}")]


def label_text(component):
    lines = []
    if component.get("label"):
        lines.append(component["label"])
    if component.get("ohms") is not None:
        lines.append(f"{component['ohms']:g} Ω")
    if component.get("volts") is not None:
        lines.append(f"{component['volts']:g} V")
    return "\n".join(lines)


def symbol(component):
    if component["type"] == "switch":
        element = elm.Switch(nc=component.get("state") == "closed")
    else:
        element = SYMBOLS[component["type"]]()
    text = label_text(component)
    return element.label(text) if text else element


def wire(d, start, end):
    if start != end:
        d.add(elm.Line().at(start).to(end))


def render(spec, png_path, svg_path):
    branches = spec["branches"] or [[]]
    longest = max(len(branch) for branch in branches)
    height = UNIT * max(1, longest)

    with schemdraw.Drawing(show=False) as d:
        d.config(unit=UNIT, fontsize=13)
        d.add(symbol(spec["source"]).at((0, 0)).up().length(UNIT))
        wire(d, (0, UNIT), (0, height))

        x = 0
        for component in spec["series"]:
            d.add(symbol(component).at((x, height)).right().length(UNIT))
            x += UNIT

        if spec["branches"]:
            columns = [x + UNIT + i * BRANCH_GAP for i in range(len(branches))]
        else:
            columns = [x]

        for i, (bx, branch) in enumerate(zip(columns, branches)):
            y = height
            for component in branch:
                d.add(symbol(component).at((bx, y)).down().length(UNIT))
                y -= UNIT
            wire(d, (bx, y), (bx, 0))
            if i < len(branches) - 1:
                d.add(elm.Dot().at((bx, height)))
                d.add(elm.Dot().at((bx, 0)))
        wire(d, (x, height), (columns[-1], height))
        wire(d, (columns[-1], 0), (0, 0))

        d.save(str(png_path), transparent = False, dpi=150)
        d.save(str(svg_path), transparent = False)

        names = [s.__name__ for s in SYMBOLS.values()]
        drawn = []
        for element in d.elements:
            if type(element).__name__ in names:
                drawn.append(type(element).__name__)

    return {"drawn_symbols": drawn}