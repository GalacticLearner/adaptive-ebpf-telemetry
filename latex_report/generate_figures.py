from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT = Path(__file__).parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)


def box(ax, xy, width, height, text, color):
    patch = FancyBboxPatch(
        xy, width, height, boxstyle="round,pad=0.03,rounding_size=0.04",
        facecolor=color, edgecolor="#25364a", linewidth=1.0,
    )
    ax.add_patch(patch)
    ax.text(xy[0] + width / 2, xy[1] + height / 2, text,
            ha="center", va="center", fontsize=8, wrap=True)


def arrow(ax, start, end, label=None):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10,
                                 linewidth=1.0, color="#425466"))
    if label:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.07,
                label, ha="center", va="bottom", fontsize=7, color="#263746")


def architecture():
    fig, ax = plt.subplots(figsize=(7.1, 3.0))
    ax.set_xlim(0, 7.1)
    ax.set_ylim(0, 3.05)
    ax.axis("off")

    box(ax, (0.15, 2.08), 1.45, 0.65, "Workload +\nincident truth", "#e7f0fb")
    box(ax, (2.12, 2.08), 1.55, 0.65, "sched_switch\nsentinel bins", "#d9eee8")
    box(ax, (2.12, 0.76), 1.55, 0.74, "sys_enter/exit\ndetail probes", "#fbe7d5")
    box(ax, (4.28, 2.08), 1.25, 0.65, "Detector +\npolicy", "#ece2f6")
    box(ax, (4.28, 0.76), 1.25, 0.74, "Ring buffer +\nbounded sink", "#f6e8d2")
    box(ax, (5.98, 1.42), 0.98, 0.72, "Validated\nmetrics", "#e5ebf0")

    arrow(ax, (1.60, 2.38), (2.12, 2.38), "target TIDs")
    arrow(ax, (1.60, 2.18), (2.12, 1.32), "syscalls")
    arrow(ax, (3.67, 2.40), (4.28, 2.40), "5 ms bins")
    arrow(ax, (4.90, 2.08), (3.42, 1.50), "GATE threshold / SWITCH links")
    arrow(ax, (3.67, 1.12), (4.28, 1.12), "selected pairs")
    arrow(ax, (5.53, 1.10), (5.98, 1.58), "records + counters")
    ax.plot([0.88, 0.88, 6.46], [2.08, 0.42, 0.42], color="#425466", linewidth=1.0)
    arrow(ax, (6.46, 0.42), (6.46, 1.42), "application work + truth")
    ax.text(3.55, 0.17, "Always-on low-cost signal; detailed collection changes with policy",
            ha="center", va="center", fontsize=8, color="#34495e")
    fig.tight_layout(pad=0.4)
    fig.savefig(OUT / "architecture.pdf", bbox_inches="tight")
    fig.savefig(OUT / "architecture.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def frontier():
    fig, ax = plt.subplots(figsize=(5.4, 3.5))
    points = [
        ("CPU", 1.8463823016315772, -0.6311400864173589, 5.597566597504555,
         1.1685868562858989, 1.022461279140551, 1.3494949007520315, "#2676a8"),
        ("I/O", 11.207998707865663, 10.85332675596087, 11.463425426409268,
         1.0024151288151758, 0.8812479558196548, 1.1551779623992967, "#cc6d32"),
    ]
    for label, x, xlo, xhi, y, ylo, yhi, color in points:
        ax.errorbar(x, y, xerr=[[x - xlo], [xhi - x]],
                    yerr=[[y - ylo], [yhi - y]], fmt="o", ms=5,
                    capsize=3, color=color, ecolor=color, label=label)
        ax.annotate(label, (x, y), xytext=(5, 6), textcoords="offset points",
                    fontsize=8, color=color)
    ax.axvline(5, color="#555555", linestyle="--", linewidth=1,
               label="5% declared budget")
    ax.set_xlabel("Application throughput loss (%)")
    ax.set_ylabel("Common-cutoff incident capture (%)")
    ax.set_title("FIX_Q01 pilot (4 paired blocks; exploratory)")
    ax.grid(True, linewidth=0.4, alpha=0.35)
    ax.set_xlim(-2.2, 14)
    ax.set_ylim(0.65, 1.55)
    ax.legend(loc="upper left", fontsize=7, frameon=False)
    ax.text(0.98, 0.02, "All blocks carry external-CPU noise flag",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5,
            color="#555555")
    fig.tight_layout(pad=0.6)
    fig.savefig(OUT / "pilot_frontier.pdf", bbox_inches="tight")
    fig.savefig(OUT / "pilot_frontier.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    architecture()
    frontier()
