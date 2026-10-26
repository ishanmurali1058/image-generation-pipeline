import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pipeline.understand import understand
from routes import ROUTE_MODULES

SPEC_ERRORS = (KeyError, ValueError, TypeError)

def draw_placeholder(question, png_path):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(0.5, 0.5, f"Placeholder image\n{question['id']}", ha="center", va="center", fontsize=16)
    ax.axis("off")
    fig.savefig(png_path, dpi=100)
    plt.close(fig)

def generate(plan, question, out_dir):
    png_path = out_dir / f"{question['id']}.png"
    svg_path = out_dir / f"{question['id']}.svg"
    svg_path.unlink(missing_ok=True)

    route = ROUTE_MODULES.get(plan["route"])
    if route is None:
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "placeholder": True}

    try:
        spec_checks = route.check_spec(plan, question)
    except SPEC_ERRORS as error:
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "error": f"Spec could not be checked: {error!r}"}

    if any(check["result"] == "fail" for check in spec_checks):
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "spec_checks": spec_checks, "skipped_drawing": True}

    try:
        details = route.render(plan["spec"], png_path, svg_path)
    except SPEC_ERRORS as error:
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "spec_checks": spec_checks,
                "error": f"Drawing failed: {error!r}"}

    return {"png": str(png_path), "svg": str(svg_path), "cost": 0.0, "spec_checks": spec_checks, **details}

def verify(plan, question, files):
    if "error" in plan:
        return {"passed": False, "checks": [{"name": "plan", "result": "fail", "detail": plan["error"]}], "cost": 0.0}

    if files.get("placeholder"):
        detail = f"route '{plan['route']}' is not built yet"
        return {"passed": False, "checks": [{"name": "route", "result": "fail", "detail": detail}], "cost": 0.0}

    checks = list(files.get("spec_checks", []))

    if "error" in files:
        checks.append({"name": "generate", "result": "fail", "detail": files["error"]})
    elif not files.get("skipped_drawing"):
        route = ROUTE_MODULES[plan["route"]]
        checks.extend(route.check_render(plan, files))

    passed = all(check["result"] != "fail" for check in checks)
    return {"passed": passed, "checks": checks, "cost": 0.0}