import json
import math
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Rectangle
from PIL import Image

from pipeline.images import generate_image
from pipeline.llm import call_llm

from .common import check, check_answer, check_values_in_notes, make_check

WIDTH, HEIGHT, GROUND_Y, WALL_X = 100, 75, 12, 72
RED = "#B03A2E"
LABEL_BOX = {"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "none", "alpha": 0.9}
COMMON_FIELDS = ["overlay", "scene", "background", "units", "unknown"]
OVERLAY_FIELDS = {"right_triangle": ["vertical_object", "base", "height", "slant", "angle"],
                  "grid": ["columns", "rows", "square_size"]}

JUDGE_PROMPT = """You check pictures for school questions. The picture is a scene with measurement lines and labels drawn on top.
Reply with ONLY a JSON object, no other text:
{"description": "two sentences on what you see", "aligned": true or false,
 "other_text": "any text in the scene itself, ignoring the measurement labels, or an empty string",
 "defects": ["visible drawing errors in the scene, such as distorted people or merged objects"]}"""


def solve_triangle(spec):
    base, height, slant, angle = (spec[key] for key in ("base", "height", "slant", "angle"))
    if angle is not None:
        if not 0 < angle < 90:
            raise ValueError("the angle must be between 0 and 90 degrees")
        radians = math.radians(angle)
        if slant:
            base, height = slant * math.cos(radians), slant * math.sin(radians)
        elif base:
            height = base * math.tan(radians)
        elif height:
            base = height / math.tan(radians)
        else:
            raise ValueError("an angle alone does not fix the triangle's size; give a length too")
    elif base and slant and slant > base:
        height = math.sqrt(slant ** 2 - base ** 2)
    elif height and slant and slant > height:
        base = math.sqrt(slant ** 2 - height ** 2)
    elif not (base and height):
        raise ValueError("need the angle and one length, or two lengths with the slant the longest")

    if base <= 0 or height <= 0:
        raise ValueError("lengths must be positive")
    return {"base": base, "height": height, "slant": math.hypot(base, height),
            "angle": math.degrees(math.atan2(height, base))}


def grid_size(spec):
    return spec["columns"] * spec["square_size"], spec["rows"] * spec["square_size"]


def unknown_value(spec):
    unknown = spec["unknown"]
    if spec["overlay"] == "right_triangle":
        values = solve_triangle(spec)
    else:
        width, length = grid_size(spec)
        if width <= 0 or length <= 0:
            raise ValueError("columns, rows and square_size must be positive")
        values = {"area": width * length, "perimeter": 2 * (width + length)}
    if unknown is not None and unknown not in values:
        raise ValueError(f"unknown must be one of {list(values)} or null")
    return values.get(unknown)


def check_spec(plan, question):
    spec = plan["spec"]
    missing = [key for key in COMMON_FIELDS + OVERLAY_FIELDS.get(spec.get("overlay"), []) if key not in spec]
    if spec.get("overlay") not in OVERLAY_FIELDS or missing or spec.get("background") not in ("generated", "drawn"):
        return [make_check("spec_format", "fail", "use the layered spec format: overlay right_triangle or grid, "
                                                  f"background generated or drawn; missing fields {missing}")]
    if "dashed" in spec and not isinstance(spec["dashed"], bool):
        return [make_check("spec_format", "fail", "dashed must be true or false")]
    try:
        value = unknown_value(spec)
    except (ValueError, TypeError) as error:
        return [make_check("spec_format", "fail", str(error))]

    checks = [make_check("spec_format", "pass", "the spec is a valid layered figure")]
    unknown = spec["unknown"]
    if unknown is None:
        checks.append(make_check("answer_consistency", "skipped", "the figure has no unknown"))
    else:
        if spec["overlay"] == "right_triangle":
            checks.append(check("unknown_hidden", spec[unknown] is None,
                                f"the unknown {unknown} has no value, so it is labelled '?'",
                                f"the unknown {unknown} is given the value {spec[unknown]}, which would show the answer"))
        checks.append(check_answer(question, value, f"the {unknown} worked out from the figure"))

    if spec["overlay"] == "right_triangle":
        given = [spec[key] for key in ("base", "height", "slant", "angle") if spec[key] is not None]
    else:
        given = list(grid_size(spec))
    checks.append(check_values_in_notes(given, question))
    return checks


def draw_scene(ax, spec):
    triangle = spec["overlay"] == "right_triangle"
    if spec["background"] == "drawn":
        ax.add_patch(Rectangle((0, 0), WIDTH, HEIGHT, color="#E3F1FB" if triangle else "#CDE8B5"))
        if triangle:
            ax.add_patch(Rectangle((0, 0), WIDTH, GROUND_Y, color="#B9D98C"))
            ax.add_patch(Rectangle((WALL_X, GROUND_Y), 7, HEIGHT - GROUND_Y - 4, facecolor="#D9C2A7", edgecolor="#7A6650"))
        return 0.0

    if triangle:
        layout = (f"A {spec['vertical_object']} stands upright about seven tenths of the way across the picture, "
                  "rising from flat ground that fills the bottom sixth, with open space to its left and nothing leaning on it.")
    else:
        layout = "A top-down view, with the area filling the middle of the picture."
    prompt = (f"{spec['scene']} {layout} Flat, colourful children's book illustration. "
              "No text, letters, numbers, signs or writing anywhere.")

    with tempfile.TemporaryDirectory() as folder:
        scene_path = Path(folder) / "scene.png"
        try:
            result = generate_image(prompt, scene_path)
        except Exception as error:
            raise ValueError(f"image generation failed: {error}") from error
        ax.imshow(Image.open(scene_path), extent=[0, WIDTH, 0, HEIGHT], aspect="auto")
    return result["cost"]


def label(ax, x, y, text):
    ax.text(x, y, text, ha="center", va="center", fontsize=14, bbox=LABEL_BOX)


def label_text(spec, key):
    if spec["unknown"] == key:
        return "?"
    if spec[key] is None:
        return None
    return f"{spec[key]:g}°" if key == "angle" else f"{spec[key]:g} {spec['units']}"


def draw_triangle(ax, spec):
    solved = solve_triangle(spec)
    scale = min((WALL_X - 8) / solved["base"], (HEIGHT - GROUND_Y - 9) / solved["height"])
    foot = (WALL_X - solved["base"] * scale, GROUND_Y)
    top = (WALL_X, GROUND_Y + solved["height"] * scale)

    ax.plot([foot[0], WALL_X, WALL_X], [GROUND_Y, GROUND_Y, top[1]], color=RED, linewidth=3)
    if spec.get("dashed") is True:
        ax.plot([foot[0], top[0]], [foot[1], top[1]], color=RED, linewidth=2.5, linestyle="--")
    else:
        ax.plot([foot[0], top[0]], [foot[1], top[1]], color="#6E4B2A", linewidth=5)
    ax.plot([WALL_X - 3, WALL_X - 3, WALL_X], [GROUND_Y, GROUND_Y + 3, GROUND_Y + 3], color=RED, linewidth=1.5)

    if label_text(spec, "angle"):
        ax.add_patch(Arc(foot, 14, 14, theta1=0, theta2=solved["angle"], color=RED, linewidth=2))
        middle = math.radians(solved["angle"] / 2)
        label(ax, foot[0] + 12 * math.cos(middle), foot[1] + 12 * math.sin(middle), label_text(spec, "angle"))

    positions = {"base": ((foot[0] + WALL_X) / 2, GROUND_Y - 5),
                 "height": (WALL_X + 7, (GROUND_Y + top[1]) / 2),
                 "slant": ((foot[0] + top[0]) / 2 - 4, (foot[1] + top[1]) / 2 + 4)}
    for key, (x, y) in positions.items():
        if label_text(spec, key):
            label(ax, x, y, label_text(spec, key))
    return {"foot": list(foot), "top": list(top)}


def draw_grid(ax, spec):
    columns, rows = spec["columns"], spec["rows"]
    cell = min(80 / columns, 58 / rows)
    left, bottom = (WIDTH - columns * cell) / 2, (HEIGHT - rows * cell) / 2 + 3
    for i in range(columns + 1):
        ax.plot([left + i * cell] * 2, [bottom, bottom + rows * cell], color="#333333", linewidth=1.2)
    for j in range(rows + 1):
        ax.plot([left, left + columns * cell], [bottom + j * cell] * 2, color="#333333", linewidth=1.2)
    ax.add_patch(Rectangle((left, bottom), columns * cell, rows * cell, fill=False, edgecolor=RED, linewidth=3))
    size = f"{spec['square_size']:g} {spec['units']}"
    label(ax, WIDTH / 2, bottom - 5, f"Each square is {size} × {size}")


def render(spec, png_path, svg_path):
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, WIDTH)
    ax.set_ylim(0, HEIGHT)
    ax.axis("off")
    try:
        details = {"cost": draw_scene(ax, spec)}
        if spec["overlay"] == "right_triangle":
            details["drawn_points"] = draw_triangle(ax, spec)
        else:
            draw_grid(ax, spec)
        fig.savefig(png_path, dpi=128)
        if spec["background"] == "drawn":
            fig.savefig(svg_path)
    finally:
        plt.close(fig)
    return details


def check_render(plan, files, question=None):
    spec = plan["spec"]
    checks = []
    if spec["overlay"] == "right_triangle":
        foot, top = files["drawn_points"]["foot"], files["drawn_points"]["top"]
        drawn = math.degrees(math.atan2(top[1] - foot[1], top[0] - foot[0]))
        expected = solve_triangle(spec)["angle"]
        checks.append(check("drawn_matches_spec", abs(drawn - expected) < 0.5,
                            f"the drawn angle is {drawn:.1f}°, matching the figure",
                            f"the drawn angle is {drawn:.1f}°, but the figure needs {expected:.1f}°"))
    if spec["background"] == "generated":
        checks.extend(judge_checks(spec, files))
    return checks


def judge_checks(spec, files):
    target = f"the {spec['vertical_object']} and the ground" if spec["overlay"] == "right_triangle" else "the area shown"
    result = call_llm(JUDGE_PROMPT, f"Set aligned to whether the drawn figure lines up with {target}.",
                      max_tokens=1500, image_path=files["png"])
    text = result["text"]
    try:
        report = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except json.JSONDecodeError:
        report = None

    described = make_check("judge_description", "pass" if report else "fail",
                           report["description"] if report else f"the judge's reply was not valid JSON: {text[:200]!r}")
    described.update({"cost": result["cost"], "fix": "redraw"})
    if not report:
        return [described]

    scene_checks = [
        check("no_text_in_scene", not (report.get("other_text") or "").strip(),
              "the judge sees no text in the scene", f"the judge sees text in the scene: '{report.get('other_text')}'"),
        check("no_visible_defects", not report.get("defects"),
              "the judge sees no drawing errors", f"the judge sees drawing errors: {report.get('defects')}"),
    ]
    for item in scene_checks:
        item["fix"] = "redraw"
    aligned = check("overlay_aligned", report.get("aligned") is True, "the figure lines up with the scene",
                    "the figure does not line up with the scene; set background to drawn to use a plain drawn scene")
    return [described, aligned] + scene_checks