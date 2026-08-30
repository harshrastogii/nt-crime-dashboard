"""
make_notebook.py — generate the public Kaggle starter notebook.

Kept as a generator rather than a checked-in .ipynb so the notebook's numbers
and prose stay tied to the dataset that ships alongside it.

    python scripts/make_notebook.py
"""

import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "kaggle", "notebook")
NB = os.path.join(OUT_DIR, "nt-crime-getting-started.ipynb")
META = os.path.join(OUT_DIR, "kernel-metadata.json")

DATASET = "harshrastogiii/northern-territory-crime-statistics-2008-2026"
KERNEL_ID = "harshrastogiii/nt-crime-2008-2026-getting-started"


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(*lines):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in lines]}


CELLS = [
    md("# Northern Territory Crime Statistics, 2008–2026 — Getting Started",
       "",
       "222 consecutive months of recorded crime in the Northern Territory of Australia,",
       "with no gaps. This notebook loads the data, verifies its coverage, and walks",
       "through a trend analysis that respects the one thing that makes this dataset",
       "tricky.",
       "",
       "**The catch:** NT Police changed recording systems between **November 2023 and",
       "December 2023** (PROMIS → SerPro). The NT Government advises that data from",
       "December 2023 onward should not be compared directly with earlier data. Every row",
       "carries a `Data era` tag so you can keep the two apart — this notebook shows how."),

    code("import glob",
         "import pandas as pd",
         "import matplotlib.pyplot as plt",
         "",
         "# Locate the CSV wherever Kaggle mounted it, rather than hard-coding",
         "# the input path.",
         "matches = glob.glob('/kaggle/input/**/nt_crime_master.csv', recursive=True)",
         "PATH = matches[0] if matches else 'nt_crime_master.csv'",
         "print('reading:', PATH)",
         "",
         "df = pd.read_csv(PATH, low_memory=False)",
         "print(f'{len(df):,} rows x {df.shape[1]} columns')",
         "df.head()"),

    md("## 1. Verify the coverage",
       "",
       "The dataset claims 222 months with no gaps. Never take that on trust — check it."),

    code("months = pd.PeriodIndex(sorted(df['Date'].unique()), freq='M')",
         "expected = pd.period_range(months.min(), months.max(), freq='M')",
         "missing = sorted(set(expected) - set(months))",
         "",
         "print(f'range      : {months.min()} to {months.max()}')",
         "print(f'months     : {len(months)} (expected {len(expected)})')",
         "print(f'missing    : {missing if missing else \"none\"}')",
         "print(f'offences   : {df[\"Number of offences\"].sum():,}')",
         "print(f'locations  : {df[\"Location\"].nunique()}')",
         "print()",
         "print(df.groupby('Data era')['Number of offences'].agg(['size', 'sum']))"),

    md("## 2. Where the crime is recorded",
       "",
       "`Location` is the field to group by. The government's own `Reporting Region`",
       "lumps roughly twenty remote localities under a single `NT Balance` label;",
       "`Location` resolves those back into named places, giving 27 distinct locations."),

    code("loc = (df.groupby(['Location', 'Location Type'])['Number of offences']",
         "         .sum().reset_index()",
         "         .sort_values('Number of offences', ascending=False))",
         "",
         "print(f\"{loc['Location'].nunique()} locations\")",
         "loc.head(15)"),

    code("top = loc.head(12).iloc[::-1]",
         "colours = {'Urban': '#C75B12', 'Regional': '#E8A33D', 'Remote': '#7A8CA0'}",
         "",
         "fig, ax = plt.subplots(figsize=(9, 5))",
         "ax.barh(top['Location'], top['Number of offences'],",
         "        color=[colours[t] for t in top['Location Type']])",
         "ax.set_xlabel('Recorded offences, 2008-2026')",
         "ax.set_title('Twelve locations with the most recorded offences')",
         "for s in ('top', 'right'):",
         "    ax.spines[s].set_visible(False)",
         "handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colours.values()]",
         "ax.legend(handles, colours.keys(), frameon=False, loc='lower right')",
         "plt.tight_layout()",
         "plt.show()"),

    md("## 3. The trend — plotted honestly",
       "",
       "A 12-month rolling total smooths the strong seasonality the NT Government warns",
       "about. The series is drawn as **two separate lines**, one per recording era,",
       "with a visible gap at the break. Drawing one continuous line across November 2023",
       "would imply a comparability the data does not have."),

    code("monthly = df.groupby('Date')['Number of offences'].sum().sort_index()",
         "monthly.index = pd.PeriodIndex(monthly.index, freq='M')",
         "rolling = monthly.rolling(12).sum()",
         "",
         "break_month = pd.Period('2023-11', freq='M')",
         "before = rolling[rolling.index <= break_month]",
         "after  = rolling[rolling.index >  break_month]",
         "",
         "fig, ax = plt.subplots(figsize=(11, 5))",
         "ax.plot(before.index.to_timestamp(), before.values, color='#0B1F33',",
         "        linewidth=2, label='PROMIS (to Nov 2023)')",
         "ax.plot(after.index.to_timestamp(), after.values, color='#C75B12',",
         "        linewidth=2, label='SerPro (from Dec 2023)')",
         "ax.axvline(break_month.to_timestamp(), color='grey', linestyle='--', linewidth=1)",
         "ax.annotate('recording system changed', xy=(break_month.to_timestamp(), ax.get_ylim()[1]),",
         "            xytext=(-10, -14), textcoords='offset points', ha='right',",
         "            fontsize=9, color='grey')",
         "ax.set_ylabel('Offences, 12-month rolling total')",
         "ax.set_title('NT recorded offences — the two eras are plotted separately')",
         "ax.legend(frameon=False)",
         "for s in ('top', 'right'):",
         "    ax.spines[s].set_visible(False)",
         "plt.tight_layout()",
         "plt.show()"),

    md("### Why that gap matters",
       "",
       "Compare the crime mix either side of the break. If the change were purely",
       "real-world, the proportions would drift gently. They don't — assault jumps and",
       "theft falls by several percentage points at the boundary, which is a signature of",
       "the classification and recording change, not of behaviour."),

    code("mix = (df.pivot_table(index='Crime Type', columns='Data era',",
         "                     values='Number of offences', aggfunc='sum'))",
         "mix = mix.div(mix.sum()).mul(100).round(1)",
         "mix['shift (pp)'] = (mix['Current / SerPro'] - mix['Historical / PROMIS']).round(1)",
         "mix.sort_values('shift (pp)', key=abs, ascending=False)"),

    md("## 4. Per-capita rates — only where they're valid",
       "",
       "The `Population (ABS 2021 reference)` column is a **single 2021 Census figure**,",
       "not a population time series. It is deliberately blank for every historical row",
       "and for the 18 locations without a confidently sourced figure.",
       "",
       "So a rate is only defensible for the current era, for the nine locations that",
       "have a population. Blank means unknown — never treat it as zero."),

    code("pop_col = 'Population (ABS 2021 reference)'",
         "cur = df[(df['Data era'] == 'Current / SerPro') & df[pop_col].notna()]",
         "",
         "months_covered = cur['Date'].nunique()",
         "rates = (cur.groupby('Location')",
         "            .agg(offences=('Number of offences', 'sum'), population=(pop_col, 'first')))",
         "rates['per 1,000 residents per year'] = (",
         "    rates['offences'] / rates['population'] / (months_covered / 12) * 1000).round(1)",
         "rates.sort_values('per 1,000 residents per year', ascending=False)"),

    md("Ranked by raw counts, Darwin looks like the Territory's crime centre — it simply",
       "has the most people. Per 1,000 residents the ordering inverts, and the smaller",
       "regional centres come to the front. Which of those two views you use changes",
       "where resources appear to be needed.",
       "",
       "## 5. Alcohol and domestic violence — read the warning first",
       "",
       "These flags are recorded for assault offences only. **Alcohol involvement is not",
       "comparable across the full period:** historically \"unknown\" was a valid answer,",
       "and during migration every unknown was recoded to `No`. The NT metadata notes",
       "roughly 27% of assault offences previously carried \"unknown\".",
       "",
       "A 2008–2026 alcohol trend line would therefore partly measure a coding change.",
       "Restrict this to a single era."),

    code("assaults = df[(df['Crime Type'] == 'Assault & Violence') &",
         "              (df['Data era'] == 'Current / SerPro')]",
         "",
         "summary = (assaults.groupby(['Alcohol involvement', 'DV involvement'])",
         "                   ['Number of offences'].sum().unstack(fill_value=0))",
         "print('Assault offences, current era only (2023-12 onward)')",
         "summary"),

    md("## Where to go next",
       "",
       "- Group by `Crime Type` and `Location Type` to compare urban, regional and remote patterns",
       "- Use `Offence category` and `Offence type` for finer detail, but **only within one `Data era`**",
       "- The `is_break_month` flag and `Break note` column mark the two documented changes",
       "- `Source extract` records which official government file supplied each row",
       "",
       "`DATA_DICTIONARY.md` explains every column; `METHODOLOGY.md` covers how the three",
       "official extracts were combined and what the known limitations are.",
       "",
       "---",
       "",
       "Source: Northern Territory Government, Department of the Attorney-General and",
       "Justice — NT Crime Statistics, published on the NTG Open Data Portal",
       "(data.nt.gov.au). Offences recorded by NT Police. Licensed CC BY 4.0."),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    nb = {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    with open(NB, "w") as fh:
        json.dump(nb, fh, indent=1)

    meta = {
        "id": KERNEL_ID,
        "title": "NT Crime 2008-2026: Getting Started",
        "code_file": os.path.basename(NB),
        "language": "python",
        "kernel_type": "notebook",
        "is_private": False,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": False,
        "dataset_sources": [DATASET],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    with open(META, "w") as fh:
        json.dump(meta, fh, indent=2)

    print(f"wrote {NB} ({len(CELLS)} cells)")
    print(f"wrote {META}")


if __name__ == "__main__":
    main()
