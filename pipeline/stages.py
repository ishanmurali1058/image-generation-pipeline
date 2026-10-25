import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pipeline.understand import understand
from routes import ROUTE_MODULES


def draw_placeholder(question, png_path):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(0.5, 0.5, f"Placeholder image\n{question['id']}", ha="center", va="center", fontsize=16)
    ax.axis("off")
    fig.savefig(png_path, dpi=100)
    plt.close(fig)


def generate(plan, question, out_dir):
    png_path = out_dir / f"{question['id']}.png"
    svg_path = out_dir / f"{question['id']}.svg"

    route = ROUTE_MODULES.get(plan["route"])
    if route is None:
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "placeholder": True}

    try:
        details = route.render(plan["spec"], png_path, svg_path)
    except (KeyError, ValueError, TypeError) as error:
        draw_placeholder(question, png_path)
        return {"png": str(png_path), "svg": None, "cost": 0.0, "error": f"Drawing failed: {error}"}

    return {"png": str(png_path), "svg": str(svg_path), "cost": 0.0, **details}


def verify(plan, question, files):
    if "error" in plan:
        return {"passed": False, "checks": [f"plan error: {plan['error']}"], "cost": 0.0}

    if "error" in files:
        return {"passed": False, "checks": [files["error"]], "cost": 0.0}

    if files.get("placeholder"):
        return {"passed": False, "checks": [f"route '{plan['route']}' is not built yet"], "cost": 0.0}

    return {"passed": True, "checks": ["no real checks yet"], "cost": 0.0}