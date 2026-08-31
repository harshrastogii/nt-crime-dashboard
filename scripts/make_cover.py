"""
make_cover.py — build the Kaggle cover image from the published dataset.

Canvas is 560x280 for a reason. Kaggle does not scale the upload: its API
crops a fixed rectangle in SOURCE pixels, (0, 0, 560, 280) for the cover and
(140, 0, 280, 280) for the square thumbnail. An image larger than that loses
everything outside the top-left 560x280. Authoring at exactly that size makes
the crop a no-op.

The artwork is the series itself: one bar per month, 222 of them, coloured by
recording era, with the two documented breaks marked. Drawn from the published
CSV, so it cannot drift out of step with the data.

    python scripts/make_cover.py
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(BASE, "kaggle", "nt_crime_master.csv")
OUT = os.path.join(BASE, "kaggle", "dataset-cover-image.png")

W, H, DPI = 560, 280, 100

INK = "#0C1B2A"        # ground
PROMIS = "#4A6B8A"     # older era, receded
SERPRO = "#E4813A"     # current era, forward
BREAK = "#F2F0EC"
PAPER = "#F2F0EC"
MUTED = "#8296AA"

BREAKS = {"2023-11": "system change", "2025-04": "ANZSOC"}


def main():
    df = pd.read_csv(CSV, low_memory=False)
    monthly = (df.groupby(["Date", "Data era"])["Number of offences"]
                 .sum().reset_index().sort_values("Date"))
    dates = monthly["Date"].tolist()
    vals = monthly["Number of offences"].tolist()
    eras = monthly["Data era"].tolist()
    colours = [SERPRO if e.startswith("Current") else PROMIS for e in eras]

    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
    fig.patch.set_facecolor(INK)

    # Chart occupies the lower half; type sits above it.
    ax = fig.add_axes([0.057, 0.10, 0.886, 0.46])
    ax.set_facecolor(INK)
    ax.bar(range(len(vals)), vals, width=0.86, color=colours, linewidth=0)

    # The two breaks fall close together on a 222-month axis, so the labels
    # are staggered and pushed to opposite sides of their rules.
    placement = {"2023-11": (-2.5, 0.99, "right"), "2025-04": (2.5, 0.80, "left")}
    for when, label in BREAKS.items():
        if when not in dates:
            continue
        x = dates.index(when)
        dx, y, ha = placement[when]
        ax.axvline(x, color=BREAK, linewidth=0.8, alpha=0.6)
        ax.text(x + dx, max(vals) * y, label, color=BREAK, alpha=0.75,
                fontsize=5.4, ha=ha, va="top")

    ax.set_xlim(-1.5, len(vals) + 0.5)
    ax.set_ylim(0, max(vals) * 1.06)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])

    # Year ticks, sparse enough to stay quiet at 280px wide.
    for yr in (2010, 2014, 2018, 2022, 2026):
        tag = f"{yr}-01"
        if tag in dates:
            ax.text(dates.index(tag), -max(vals) * 0.10, str(yr), color=MUTED,
                    fontsize=5.6, ha="center", va="top")

    # --- type ---------------------------------------------------------
    fig.text(0.057, 0.855, "NORTHERN TERRITORY, AUSTRALIA", color=SERPRO,
             fontsize=6.4, fontweight="bold")
    fig.text(0.057, 0.715, "Recorded crime, 2008–2026", color=PAPER,
             fontsize=17.5, fontweight="bold")
    fig.text(0.057, 0.635, "222 consecutive months  ·  567,438 offences  ·  27 locations",
             color=MUTED, fontsize=7.2)

    # Era key: a swatch and a label, so the bar colours are decodable.
    for i, (name, colour) in enumerate((("PROMIS", PROMIS), ("SerPro", SERPRO))):
        y = 0.862 - i * 0.072
        fig.patches.append(plt.Rectangle((0.868, y), 0.017, 0.030,
                                         facecolor=colour, edgecolor="none",
                                         transform=fig.transFigure))
        fig.text(0.943, y + 0.004, name, color=MUTED, fontsize=6.2, ha="right")

    fig.savefig(OUT, facecolor=INK, edgecolor="none")
    plt.close(fig)
    from PIL import Image
    w, h = Image.open(OUT).size
    print(f"wrote {OUT} — {w}x{h}px, {os.path.getsize(OUT)/1024:.0f} KB")
    if (w, h) != (W, H):
        raise SystemExit(f"STOP: expected {W}x{H}, got {w}x{h}")
if __name__ == "__main__":
    main()
