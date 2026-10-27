import difflib
from pathlib import Path
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .common import check, make_check

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "india_states.geojson"
REQUIRED_FIELDS = ["shaded", "labelled", "title", "unknown"]
SHADE_COLOUR = "#E8A33D"
OTHER_COLOUR = "#F2F2F2"
_states = None

def load_states():
    global _states
    if _states is None:
        _states = gpd.read_file(DATA_PATH)
    return _states

def simplify_name(name):
    return name.lower().replace("&", "and").replace(" ", "")

def find_state(name, states):
    for real_name in states["name"]:
        if simplify_name(real_name) == simplify_name(name):
            return real_name
    return None

def check_spec(plan, question):
    spec = plan["spec"]
    missing = [key for key in REQUIRED_FIELDS if key not in spec]
    if missing:
        return [make_check("spec_format", "fail", f"the spec is missing the fields {missing}; use the map spec format")]
    if not spec["shaded"] and not spec["labelled"]:
        return [make_check("spec_format", "fail", "the map shades and labels nothing")]

    states = load_states()
    unknown_names = []
    for name in spec["shaded"] + spec["labelled"]:
        if find_state(name, states) is None:
            close = difflib.get_close_matches(name, list(states["name"]), n=1)
            hint = f" (did you mean {close[0]}?)" if close else ""
            unknown_names.append(f"{name}{hint}")
    if unknown_names:
        return [make_check("spec_format", "fail", f"these are not Indian states or union territories: {unknown_names}")]

    checks = [make_check("spec_format", "pass", "every shaded and labelled name is a state or union territory")]

    notes = question.get("image_notes")
    if notes:
        not_in_notes = [name for name in spec["shaded"] + spec["labelled"] if simplify_name(name) not in simplify_name(notes)]
        checks.append(check("names_match_notes", not not_in_notes,
                            "every shaded and labelled state appears in the image notes",
                            f"{not_in_notes} are not in the image notes"))
    else:
        checks.append(make_check("names_match_notes", "skipped", "no image notes given"))

    checks.append(check_answer(spec, question))
    checks.append(check_unknown_hidden(spec))
    return checks

def check_answer(spec, question):
    unknown = spec["unknown"]
    if not unknown:
        return make_check("answer_consistency", "skipped", "the map has no unknown state")
    if simplify_name(unknown) not in [simplify_name(n) for n in spec["shaded"]]:
        return make_check("answer_consistency", "fail", f"the unknown state {unknown} is not shaded")

    answer = question.get("answer")
    if answer:
        return check("answer_consistency", simplify_name(answer) == simplify_name(unknown),
                     f"the shaded unknown state is {unknown}, matching the answer",
                     f"the shaded unknown state is {unknown}, but the answer is '{answer}'")

    options = [simplify_name(o) for o in question.get("options", [])]
    if options:
        return check("answer_consistency", simplify_name(unknown) in options,
                     f"no answer given; the shaded state {unknown} is one of the options",
                     f"no answer given; the shaded state {unknown} is not one of the options")
    return make_check("answer_consistency", "skipped", "no answer or options given")

def check_unknown_hidden(spec):
    unknown = spec["unknown"]
    if not unknown:
        return make_check("unknown_hidden", "skipped", "the map has no unknown state")
    labelled = [simplify_name(n) for n in spec["labelled"]]
    in_title = simplify_name(unknown) in simplify_name(spec.get("title") or "")
    return check("unknown_hidden", simplify_name(unknown) not in labelled and not in_title,
                 f"{unknown} is shaded but not named",
                 f"{unknown} is named on the map, which shows the answer")

def check_render(plan, files, question = None):
    spec = plan["spec"]
    states = load_states()
    expected = sorted(find_state(name, states) for name in spec["shaded"])
    drawn = sorted(files.get("drawn_shaded", []))
    return [check("drawn_matches_spec", drawn == expected,
                  f"exactly the states {expected} are shaded",
                  f"the map shades {drawn} but the spec needs {expected}")]

def render(spec, png_path, svg_path):
    states = load_states()
    shaded = [find_state(name, states) for name in spec["shaded"]]
    labelled = [find_state(name, states) for name in spec["labelled"]]

    fig, ax = plt.subplots(figsize=(7, 8))
    states.plot(ax=ax, color=OTHER_COLOUR, edgecolor="#555555", linewidth=0.4)

    shaded_rows = states[states["name"].isin(shaded)]
    shaded_rows.plot(ax=ax, color=SHADE_COLOUR, edgecolor="#333333", linewidth=0.6)

    for _, row in states[states["name"].isin(labelled)].iterrows():
        point = row.geometry.representative_point()
        ax.annotate(row["name"], (point.x, point.y), ha="center", va="center", fontsize=9)

    ax.set_title(spec.get("title") or "", fontsize=14)
    ax.set_axis_off()
    fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {"drawn_shaded": list(shaded_rows["name"])}