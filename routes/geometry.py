import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Polygon

from .common import check, check_answer, check_values_in_notes, make_check

DEFAULT_BASE = 6.0
ANGLE_TOLERANCE = 0.5
SIDE_TOLERANCE = 0.01
REQUIRED_FIELDS = ["shape", "vertices", "angles", "sides", "unknown"]

def get_side(sides, p, q):
    value = sides.get(p + q)
    return value if value is not None else sides.get(q + p)

def third_side(angle, s1, s2):
    return math.sqrt(s1 * s1 + s2 * s2 - 2 * s1 * s2 * math.cos(math.radians(angle)))

def angles_from_sides(a, b, c):
    A = math.degrees(math.acos((b * b + c * c - a * a) / (2 * b * c)))
    B = math.degrees(math.acos((a * a + c * c - b * b) / (2 * a * c)))
    return A, B, 180 - A - B

def solve_triangle(spec):
    v0, v1, v2 = spec["vertices"]
    angles = spec.get("angles") or {}
    sides = spec.get("sides") or {}
    A, B, C = angles.get(v0), angles.get(v1), angles.get(v2)
    a, b, c = get_side(sides, v1, v2), get_side(sides, v2, v0), get_side(sides, v0, v1)

    if any(x is not None and x <= 0 for x in [A, B, C, a, b, c]):
        raise ValueError("angles and sides must be positive")

    known = [x for x in [A, B, C] if x is not None]
    if len(known) >= 2:
        missing = 180 - sum(known)
        A, B, C = [x if x is not None else missing for x in [A, B, C]]
        if min(A, B, C) <= 0 or abs(A + B + C - 180) > ANGLE_TOLERANCE:
            raise ValueError(f"the angles {A}, {B}, {C} cannot form a triangle")

        sines = [math.sin(math.radians(x)) for x in [A, B, C]]
        scale = DEFAULT_BASE / sines[2]
        for side, sine in zip([a, b, c], sines):
            if side is not None:
                scale = side / sine
                break
        a, b, c = [scale * sine for sine in sines]
    else:
        lengths, corner_angles = [a, b, c], [A, B, C]
        for i in range(3):
            j, k = (i + 1) % 3, (i + 2) % 3
            if lengths[i] is None and None not in (corner_angles[i], lengths[j], lengths[k]):
                lengths[i] = third_side(corner_angles[i], lengths[j], lengths[k])
        if None in lengths:
            raise ValueError("the givens do not fix the triangle's shape "
                             "(need two angles, three sides, or two sides and the angle between them)")
        a, b, c = lengths
        if a + b <= c or b + c <= a or a + c <= b:
            raise ValueError(f"sides {a}, {b}, {c} cannot form a triangle")
        A, B, C = angles_from_sides(a, b, c)

    points = {
        v0: (0.0, 0.0),
        v1: (c, 0.0),
        v2: (b * math.cos(math.radians(A)), b * math.sin(math.radians(A))),
    }
    return {"angles": {v0: A, v1: B, v2: C},
            "sides": {v1 + v2: a, v2 + v0: b, v0 + v1: c},
            "points": points}

def find_unknown(spec, solution):
    unknown = spec.get("unknown")
    if unknown in spec["vertices"]:
        return "angle", unknown, solution["angles"][unknown]
    for side, length in solution["sides"].items():
        if unknown in (side, side[::-1]):
            return "side", side, length
    return None, unknown, None

def check_spec(plan, question):
    spec = plan["spec"]

    missing = [key for key in REQUIRED_FIELDS if key not in spec]
    if missing:
        return [make_check("spec_format", "fail", f"the spec is missing the fields {missing}; use the geometry spec format")]
    if spec["shape"] != "triangle" or not isinstance(spec["vertices"], list) or len(spec["vertices"]) != 3:
        return [make_check("spec_format", "fail", "only triangles are supported, with vertices as a list of three names")]

    try:
        solution = solve_triangle(spec)
    except ValueError as error:
        return [make_check("spec_format", "pass", "the spec is a triangle in the geometry format"),
                make_check("triangle_solvable", "fail", str(error))]

    checks = [make_check("spec_format", "pass", "the spec is a triangle in the geometry format"),
              make_check("triangle_solvable", "pass", "the givens fix the triangle's shape")]

    angles = spec.get("angles") or {}
    sides = spec.get("sides") or {}
    conflicts = [f"angle {v} is given as {given} but must be {solution['angles'][v]:.1f}"
                 for v, given in angles.items()
                 if given is not None and abs(solution["angles"][v] - given) > ANGLE_TOLERANCE]
    for side, length in solution["sides"].items():
        given = get_side(sides, side[0], side[1:])
        if given is not None and abs(length - given) > SIDE_TOLERANCE * given:
            conflicts.append(f"side {side} is given as {given} but must be {length:.2f}")
    checks.append(check("givens_consistent", not conflicts,
                        "all given angles and sides agree with each other", "; ".join(conflicts)))

    kind, name, unknown_value = find_unknown(spec, solution)
    if spec["unknown"] is None:
        checks.append(make_check("unknown_hidden", "skipped", "the figure has no unknown"))
    elif kind is None:
        checks.append(make_check("unknown_hidden", "fail", f"unknown '{name}' is not a vertex or side of the triangle"))
    else:
        given = angles.get(name) if kind == "angle" else get_side(sides, name[0], name[1:])
        checks.append(check("unknown_hidden", given is None,
                            f"the unknown {kind} {name} has no value, so it is labelled '?'",
                            f"the unknown {kind} {name} is given the value {given}, which would show the answer"))

    given_values = [v for v in list(angles.values()) + list(sides.values()) if v is not None]
    checks.append(check_values_in_notes(given_values, question))

    if unknown_value is None:
        checks.append(make_check("answer_consistency", "skipped", "the figure has no unknown to compare with the answer"))
    else:
        checks.append(check_answer(question, unknown_value, f"{kind} {name} in the figure"))
    return checks

def angle_at(points, vertex, p, q):
    vx, vy = points[vertex]
    ux, uy = points[p][0] - vx, points[p][1] - vy
    wx, wy = points[q][0] - vx, points[q][1] - vy
    cosine = (ux * wx + uy * wy) / (math.hypot(ux, uy) * math.hypot(wx, wy))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

def check_render(plan, files):
    spec = plan["spec"]
    v0, v1, v2 = spec["vertices"]
    points = files.get("drawn_points", {})
    neighbours = {v0: (v1, v2), v1: (v0, v2), v2: (v0, v1)}

    problems = []
    for vertex, given in (spec.get("angles") or {}).items():
        if given is not None:
            drawn = angle_at(points, vertex, *neighbours[vertex])
            if abs(drawn - given) > ANGLE_TOLERANCE:
                problems.append(f"angle {vertex} is labelled {given} but drawn at {drawn:.1f}")
    for p, q in [(v0, v1), (v1, v2), (v2, v0)]:
        given = get_side(spec.get("sides") or {}, p, q)
        if given is not None:
            drawn = math.dist(points[p], points[q])
            if abs(drawn - given) > SIDE_TOLERANCE * given:
                problems.append(f"side {p}{q} is labelled {given} but drawn as {drawn:.2f}")

    return [check("drawn_matches_labels", not problems,
                  "every labelled angle and side is drawn at its labelled size", "; ".join(problems))]

def label_outside(ax, point, centre, distance, text, **style):
    dx, dy = point[0] - centre[0], point[1] - centre[1]
    length = math.hypot(dx, dy)
    ax.text(point[0] + dx / length * distance, point[1] + dy / length * distance, text,
            ha="center", va="center", **style)

def draw_angle_mark(ax, points, vertex, p, q, label, given, size):
    vx, vy = points[vertex]
    t1 = math.degrees(math.atan2(points[p][1] - vy, points[p][0] - vx))
    t2 = math.degrees(math.atan2(points[q][1] - vy, points[q][0] - vx))
    sweep = (t2 - t1) % 360
    if sweep > 180:
        t1, sweep = t2, 360 - sweep

    shortest = min(math.dist(points[vertex], points[p]), math.dist(points[vertex], points[q]))
    radius = min(0.12 * size, 0.3 * shortest)

    if given is not None and abs(given - 90) < 1e-9 and label != "?":
        ux, uy = math.cos(math.radians(t1)), math.sin(math.radians(t1))
        wx, wy = math.cos(math.radians(t1 + sweep)), math.sin(math.radians(t1 + sweep))
        r = radius * 0.7
        ax.plot([vx + r * ux, vx + r * (ux + wx), vx + r * wx],
                [vy + r * uy, vy + r * (uy + wy), vy + r * wy], color="black", linewidth=1.2)
        return

    ax.add_patch(Arc((vx, vy), 2 * radius, 2 * radius, theta1=t1, theta2=t1 + sweep, color="black", linewidth=1.2))
    middle = math.radians(t1 + sweep / 2)
    ax.text(vx + 1.9 * radius * math.cos(middle), vy + 1.9 * radius * math.sin(middle), label,
            ha="center", va="center", fontsize=13)

def render(spec, png_path, svg_path):
    solution = solve_triangle(spec)
    points = solution["points"]
    vertices = spec["vertices"]
    v0, v1, v2 = vertices
    angles = spec.get("angles") or {}
    sides = spec.get("sides") or {}
    unknown = spec.get("unknown")
    units = spec.get("units", "")
    size = max(solution["sides"].values())
    centre = (sum(points[v][0] for v in vertices) / 3, sum(points[v][1] for v in vertices) / 3)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.add_patch(Polygon([points[v] for v in vertices], closed=True, fill=False, edgecolor="black", linewidth=2))

    neighbours = {v0: (v1, v2), v1: (v0, v2), v2: (v0, v1)}
    for vertex in vertices:
        label_outside(ax, points[vertex], centre, 0.08 * size, vertex, fontsize=16, fontweight="bold")
        given = angles.get(vertex)
        if vertex == unknown or given is not None:
            label = "?" if vertex == unknown else f"{given:g}°"
            draw_angle_mark(ax, points, vertex, *neighbours[vertex], label, given, size)

    for p, q in [(v0, v1), (v1, v2), (v2, v0)]:
        given = get_side(sides, p, q)
        if unknown in (p + q, q + p) or given is not None:
            label = "?" if unknown in (p + q, q + p) else f"{given:g} {units}".strip()
            midpoint = ((points[p][0] + points[q][0]) / 2, (points[p][1] + points[q][1]) / 2)
            label_outside(ax, midpoint, centre, 0.07 * size, label, fontsize=13)

    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.margins(0.15)
    ax.axis("off")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)

    return {"drawn_points": {v: [float(points[v][0]), float(points[v][1])] for v in vertices}}