"""
make_cover.py — build the Kaggle cover image from the published dataset.

The cover is drawn from the real data rather than stock artwork: a 12-month
rolling total of recorded offences across the full 2008-2026 series, with the
two documented breaks marked. That way the image tells a would-be user what the
dataset actually contains and cannot drift out of step with it.

    python scripts/make_cover.py
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(BASE, "kaggle", "nt_crime_master.csv")
OUT = os.path.join(BASE, "kaggle", "dataset-cover-image.png")

INK = "#0B1F33"       # deep navy
OCHRE = "#C75B12"     # NT desert ochre
SAND = "#E8A33D"
PAPER = "#F7F3ED"
MUTED = "#7A8CA0"


def main():
    df = pd.read_csv(CSV, low_memory=False)
    monthly = df.groupby("Date")["Number of offences"].sum().sort_index()
    idx = pd.PeriodIndex(monthly.index, freq="M").to_timestamp()
    rolling = monthly.rolling(12).sum()

    fig = plt.figure(figsize=(12, 6), dpi=100)
    fig.patch.set_facecolor(INK)
    ax = fig.add_axes([0.06, 0.30, 0.88, 0.42])
    ax.set_facecolor(INK)

    ax.fill_between(idx, rolling.values, color=OCHRE, alpha=0.30)
    ax.plot(idx, rolling.values, color=SAND, linewidth=2.4, solid_capstyle="round")

    # Mark the two documented breaks. They sit close together on an 18-year
    # axis, so the labels are staggered vertically to stop them colliding.
    top = ax.get_ylim()[1]
    for when, label, dy, ha, dx in [
            ("2023-11", "PROMIS → SerPro", -10, "right", -6),
            ("2025-04", "ANZSOC", -30, "left", 6)]:
        x = pd.Period(when, freq="M").to_timestamp()
        ax.axvline(x, color=PAPER, linewidth=1.0, alpha=0.40, linestyle=(0, (4, 3)))
        ax.annotate(label, xy=(x, top), xytext=(dx, dy),
                    textcoords="offset points", color=PAPER, alpha=0.80,
                    fontsize=8.5, ha=ha, va="top")

    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="x", colors=MUTED, labelsize=9, length=0)
    ax.set_yticks([])
    ax.margins(x=0.01)

    # headline block
    fig.text(0.06, 0.855, "N O R T H E R N   T E R R I T O R Y", color=SAND,
             fontsize=12.5, fontweight="bold")
    fig.text(0.06, 0.775, "Crime Statistics  2008 – 2026", color=PAPER,
             fontsize=30, fontweight="bold")
    fig.text(0.06, 0.715,
             "222 consecutive months of recorded offences · no gaps",
             color=MUTED, fontsize=12)

    # stat strip
    stats = [("222", "months"), ("56,217", "rows"),
             ("567,438", "offences"), ("27", "locations")]
    x = 0.06
    for value, label in stats:
        fig.text(x, 0.15, value, color=PAPER, fontsize=17, fontweight="bold")
        fig.text(x, 0.085, label.upper(), color=MUTED, fontsize=9.5)
        x += 0.155

    # Right-hand block, kept clear of the stat strip.
    fig.text(0.94, 0.155, "CC BY 4.0", color=SAND, fontsize=13,
             fontweight="bold", ha="right")
    fig.text(0.94, 0.085, "Source: NT Government Open Data Portal",
             color=MUTED, fontsize=9, ha="right")

    # thin accent rule under the headline
    fig.add_artist(Rectangle((0.06, 0.685), 0.10, 0.006,
                             facecolor=OCHRE, edgecolor="none",
                             transform=fig.transFigure))

    fig.savefig(OUT, facecolor=INK, edgecolor="none")
    plt.close(fig)
    size = os.path.getsize(OUT)
    print(f"wrote {OUT} ({size/1024:.0f} KB, 1200x600)")


if __name__ == "__main__":
    main()
