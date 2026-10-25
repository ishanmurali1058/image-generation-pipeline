import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pipeline.understand import understand

def generate(plan, question, out_dir):
    png_path = out_dir / f"{question["id"]}.png"
    fig, ax = plt.subplots(figsize = (6,4))
    ax.text(0.5, 0.5, f"Placeholder image \n{question["id"]}", ha = "center", va = "center", fontsize = 16)
    ax.axis("off")
    fig.savefig(png_path, dpi = 100)
    plt.close(fig)

    return {"png" : str(png_path), "svg" : None, "cost" : 0.0}

def verify(plan, question, files):
    if "error" in plan:
        return {"passed" : False, "checks" : [f"plan error: {plan["error"]}"], "cost" : 0.0}

    return {"passed" : True, "checks" : ["fake check for now"], "cost" : 0.0}
