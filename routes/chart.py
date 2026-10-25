import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


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