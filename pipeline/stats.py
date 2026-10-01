"""
stats.py — the headline figures, computed from the master dataset.

Every number that appears on a published page (Kaggle title, subtitle and
description, the cover image, DATA_DICTIONARY.md, METHODOLOGY.md, README.md)
comes from here. When a new month is added, those pages move with it instead of
describing the previous release.

Some figures are documented as fixed facts rather than refreshed: 27 locations,
9 Crime Type values. If the data ever disagrees with them, `check_documented`
stops the run, because the prose around those numbers would need a human to
rewrite it.
"""

from __future__ import annotations

import pandas as pd

DOCUMENTED_LOCATIONS = 27
DOCUMENTED_CRIME_TYPES = 9


def month_name(ym: str) -> str:
    return pd.Period(ym, freq="M").strftime("%B %Y")


def compute(df: pd.DataFrame) -> dict:
    months = sorted(df["Date"].unique())
    first, last = months[0], months[-1]
    rows = len(df)
    offences = int(df["Number of offences"].sum())
    return {
        "rows": rows,
        "rows_fmt": f"{rows:,}",
        "offences": offences,
        "offences_fmt": f"{offences:,}",
        "months": len(months),
        "first": first,
        "last": last,
        "first_name": month_name(first),
        "last_name": month_name(last),
        "first_year": int(first[:4]),
        "last_year": int(last[:4]),
        "locations": int(df["Location"].nunique()),
        "crime_types": int(df["Crime Type"].nunique()),
    }


def load(path: str) -> dict:
    return compute(pd.read_csv(path, low_memory=False))


def check_documented(s: dict) -> None:
    """Stop if a figure the docs state as fixed has changed."""
    problems = []
    if s["locations"] != DOCUMENTED_LOCATIONS:
        problems.append(f"{s['locations']} locations (docs say {DOCUMENTED_LOCATIONS})")
    if s["crime_types"] != DOCUMENTED_CRIME_TYPES:
        problems.append(f"{s['crime_types']} Crime Types (docs say {DOCUMENTED_CRIME_TYPES})")
    if problems:
        raise SystemExit(
            "STOP: the data no longer matches figures the documentation states as "
            "fixed: " + "; ".join(problems) + ". The prose needs a human rewrite.")
