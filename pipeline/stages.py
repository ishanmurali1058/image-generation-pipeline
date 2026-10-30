import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pipeline.understand import understand
from routes import ROUTE_MODULES

def draw_placeholder(question, png_path): #draws a placeholder image for a question when the route is not built yet or an error occurs
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(0.5, 0.5, f"Placeholder image\n{question['id']}", ha="center", va="center", fontsize=16)
    ax.axis("off")
    fig.savefig(png_path, dpi=100)
    plt.close(fig)


def generate(plan, question, out_dir): #used to find the route module and call its render function, returning the paths to the generated images and any errors
    png_path = out_dir / f"{question['id']}.png"
    svg_path = out_dir / f"{question['id']}.svg"
    svg_path.unlink(missing_ok=True)

    route = ROUTE_MODULES.get(plan["route"])
    if route is None:
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "placeholder": True}

    try:
        spec_checks = route.check_spec(plan, question)
    except Exception as error:
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "error": f"Spec could not be checked: {error!r}"}

    if any(check["result"] == "fail" for check in spec_checks):
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "spec_checks": spec_checks, "skipped_drawing": True}

    try:
        details = route.render(plan["spec"], png_path, svg_path)
    except Exception as error:
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "spec_checks": spec_checks,
                "error": f"Drawing failed: {error!r}"}

    cost = details.pop("cost", 0.0)
    svg = str(svg_path) if svg_path.exists() else None
    return {"png": str(png_path), "svg": svg, "cost": cost, "spec_checks": spec_checks, **details}


def verify(plan, question, files): #used to check the plan and the generated files, returning a summary of the checks and their costs
    if "error" in plan:
        return {"passed": False, "checks": [{"name": "plan", "result": "fail", "detail": plan["error"]}], "cost": 0.0}

    if files.get("placeholder"):
        detail = f"route '{plan['route']}' is not built yet"
        return {"passed": False, "checks": [{"name": "route", "result": "fail", "detail": detail}],
                "cost": 0.0, "retryable": False}

    checks = list(files.get("spec_checks", []))

    if "error" in files:
        checks.append({"name": "generate", "result": "fail", "detail": files["error"]})
    elif not files.get("skipped_drawing"):
        route = ROUTE_MODULES[plan["route"]]
        try:
            checks.extend(route.check_render(plan, files, question))
        except Exception as error:
            checks.append({"name": "image_checks", "result": "fail", "fix": "redraw",
                           "detail": f"the image checks could not run: {error!r}"})

    failed = [check for check in checks if check["result"] == "fail"]
    return {
        "passed": not failed,
        "checks": checks,
        "cost": sum(check.get("cost", 0.0) for check in checks),
        "redraw": bool(failed) and all(check.get("fix") == "redraw" for check in failed),
    }