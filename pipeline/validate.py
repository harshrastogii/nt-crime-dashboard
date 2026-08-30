"""
validate.py — the safety system. Nothing is committed or published unless
every CRITICAL check passes.

Design principle: prefer stopping over publishing something wrong. A missed
month costs a day; a silently corrupted public dataset costs trust.

ON THRESHOLDS
-------------
Two kinds of change are NOT equivalent, so they get different rules:

  New months      Adding a month is expected. Its size is bounded by what the
                  NT actually records: over 2008-2026 the monthly total has
                  ranged roughly 1,900-4,300 offences. We therefore accept a
                  new month within 1,000-6,000 and flag anything outside, which
                  is wide enough for real seasonal swings and growth but still
                  catches a duplicated or truncated file.

  Existing months Revisions to already-published months should be small. Across
                  the March->April 2024 historical extracts, the observed
                  revision was +0.023% of offences over a ten-year overlap, and
                  the largest single-month revision was +23 offences (0.7%).
                  We allow any single existing month to move by up to 5% or 150
                  offences (whichever is larger) - roughly 7x the largest
                  revision ever observed - and require the whole-history total
                  to move by no more than 0.5%. Beyond that, a human looks.

These numbers come from measured behaviour of this specific data, not from a
generic rule of thumb. They are deliberately loose enough to never block a
legitimate update and tight enough to catch a structural accident.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_COLUMNS = [
    "Date", "Year", "Month number", "Crime Type", "Offence category",
    "Offence type", "Reporting Region", "Location", "Location Type",
    "Population (ABS 2021 reference)", "Alcohol involvement", "DV involvement",
    "Data era", "Source extract", "is_break_month", "Break note",
    "Number of offences"]

KEY = ["Date", "Crime Type", "Offence category", "Offence type",
       "Reporting Region", "Location", "Alcohol involvement",
       "DV involvement", "Source extract"]

EXPECTED_CRIME_TYPES = {
    "Homicide", "Assault & Violence", "Sexual Offences", "Harassment & Threats",
    "Robbery & Extortion", "Residential B&E", "Commercial B&E", "General Theft",
    "Property Damage"}
EXPECTED_LOCATION_TYPES = {"Urban", "Regional", "Remote"}
EXPECTED_ERAS = {"Historical / PROMIS", "Current / SerPro"}
EXPECTED_YESNO = {"Yes", "No", "-"}

HISTORY_END = "2023-11"       # last month of the pinned historical period
SERIES_START = "2008-01"

# Thresholds - see module docstring for the evidence behind each.
NEW_MONTH_MIN = 1_000
NEW_MONTH_MAX = 6_000
REVISION_PCT_PER_MONTH = 5.0
REVISION_ABS_PER_MONTH = 150
HISTORY_TOTAL_PCT = 0.5


@dataclass
class Result:
    critical: list = field(default_factory=list)   # blocks publication
    warnings: list = field(default_factory=list)   # reported, does not block
    facts: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.critical

    def fail(self, msg): self.critical.append(msg)
    def warn(self, msg): self.warnings.append(msg)


def _months(df):
    return pd.PeriodIndex(sorted(set(df["Date"])), freq="M")


def validate(new: pd.DataFrame, old: pd.DataFrame | None = None) -> Result:
    r = Result()

    # 1-2. structure
    missing = [c for c in REQUIRED_COLUMNS if c not in new.columns]
    if missing:
        r.fail(f"missing required columns: {missing}")
        return r
    extra = [c for c in new.columns if c not in REQUIRED_COLUMNS]
    if extra:
        r.fail(f"unexpected new columns: {extra}")

    # 3-4. duplicates
    if int(new.duplicated().sum()):
        r.fail(f"{int(new.duplicated().sum())} fully duplicate rows")
    if int(new.duplicated(subset=KEY).sum()):
        r.fail(f"{int(new.duplicated(subset=KEY).sum())} duplicate dimension keys")

    # 5. counts
    n = pd.to_numeric(new["Number of offences"], errors="coerce")
    if n.isna().any():
        r.fail(f"{int(n.isna().sum())} non-numeric offence counts")
    if (n.fillna(0) < 0).any():
        r.fail(f"{int((n.fillna(0) < 0).sum())} negative offence counts")

    # 6. dates
    try:
        per = pd.PeriodIndex(new["Date"], freq="M")
    except Exception as exc:
        r.fail(f"unparseable Date values: {exc}")
        return r
    if not new["Month number"].between(1, 12).all():
        r.fail("Month number outside 1-12")
    if not (per.year == new["Year"]).all() or not (per.month == new["Month number"]).all():
        r.fail("Date disagrees with Year/Month number on some rows")

    months = _months(new)
    # 7. no unexplained gaps
    expected = pd.period_range(months.min(), months.max(), freq="M")
    gaps = [str(p) for p in expected if p not in set(months)]
    if gaps:
        r.fail(f"missing months in the series: {gaps}")
    if str(months.min()) != SERIES_START:
        r.fail(f"series no longer starts at {SERIES_START} (starts {months.min()})")

    # 11-12. vocabularies
    if set(new["Crime Type"]) - EXPECTED_CRIME_TYPES:
        r.fail(f"unexpected Crime Type values: {sorted(set(new['Crime Type']) - EXPECTED_CRIME_TYPES)}")
    if set(new["Location Type"]) - EXPECTED_LOCATION_TYPES:
        r.fail(f"unexpected Location Type values: {sorted(set(new['Location Type']) - EXPECTED_LOCATION_TYPES)}")
    if set(new["Data era"]) - EXPECTED_ERAS:
        r.fail(f"unexpected Data era values: {sorted(set(new['Data era']) - EXPECTED_ERAS)}")
    for col in ("Alcohol involvement", "DV involvement"):
        bad = set(new[col]) - EXPECTED_YESNO
        if bad:
            r.fail(f"unexpected {col} values: {sorted(bad)}")

    # 14. internal consistency of the break flags
    flagged = set(new.loc[new["is_break_month"], "Date"])
    if flagged != {"2023-11", "2025-04"}:
        r.fail(f"is_break_month should mark exactly 2023-11 and 2025-04, found {sorted(flagged)}")
    if not (new.loc[new["Data era"] == "Historical / PROMIS",
                    "Population (ABS 2021 reference)"].isna().all()):
        r.fail("Population is populated on historical rows; it must be blank there")

    r.facts.update({
        "rows": len(new),
        "offences": int(n.fillna(0).sum()),
        "months": len(months),
        "first_month": str(months.min()),
        "last_month": str(months.max()),
        "locations": int(new["Location"].nunique()),
    })

    if old is None:
        return r

    # ---- comparisons against the previously published dataset ----
    old_months = set(old["Date"])
    new_months_set = set(new["Date"])

    # 8. nothing may disappear
    vanished = sorted(old_months - new_months_set)
    if vanished:
        r.fail(f"months present before but missing now: {vanished}")

    added = sorted(new_months_set - old_months)
    r.facts["new_months"] = added

    # 10. locations
    lost_loc = sorted(set(old["Location"]) - set(new["Location"]))
    gained_loc = sorted(set(new["Location"]) - set(old["Location"]))
    if lost_loc:
        r.fail(f"locations disappeared: {lost_loc}")
    if gained_loc:
        r.warn(f"new locations appeared: {gained_loc}")

    # 12. offence category / type vocabulary drift
    for col in ("Offence category", "Offence type"):
        gained = sorted(set(new[col]) - set(old[col]))
        if gained:
            r.warn(f"new {col} values: {gained}")

    # 13. population must not change for locations that already had one
    po = (old.dropna(subset=["Population (ABS 2021 reference)"])
            .groupby("Location")["Population (ABS 2021 reference)"].first().astype(float))
    pn = (new.dropna(subset=["Population (ABS 2021 reference)"])
            .groupby("Location")["Population (ABS 2021 reference)"].first().astype(float))
    for loc, val in po.items():
        if loc in pn and float(pn[loc]) != float(val):
            r.fail(f"population changed for {loc}: {val} -> {pn[loc]}")

    # 9 + 17. offence movement, split by kind of change
    o_by = old.groupby("Date")["Number of offences"].sum()
    n_by = new.groupby("Date")["Number of offences"].sum()

    revised = []
    for m in sorted(old_months & new_months_set):
        a, b = int(o_by[m]), int(n_by[m])
        if a == b:
            continue
        delta = b - a
        pct = (delta / a * 100) if a else 0.0
        revised.append({"month": m, "before": a, "after": b,
                        "delta": delta, "pct": round(pct, 3)})
        if abs(delta) > REVISION_ABS_PER_MONTH and abs(pct) > REVISION_PCT_PER_MONTH:
            r.fail(f"month {m} revised beyond threshold: {a} -> {b} "
                   f"({delta:+d}, {pct:+.2f}%)")
    r.facts["revised_months"] = revised

    # the pinned historical period must be essentially frozen
    hist_old = int(old.loc[old["Date"] <= HISTORY_END, "Number of offences"].sum())
    hist_new = int(new.loc[new["Date"] <= HISTORY_END, "Number of offences"].sum())
    if hist_old:
        hist_pct = (hist_new - hist_old) / hist_old * 100
        r.facts["historical_total_change_pct"] = round(hist_pct, 4)
        if abs(hist_pct) > HISTORY_TOTAL_PCT:
            r.fail(f"historical total (<= {HISTORY_END}) moved {hist_pct:+.3f}% "
                   f"({hist_old:,} -> {hist_new:,}); pinned history should not move")

    # new months must be a plausible size
    for m in added:
        v = int(n_by[m])
        if not (NEW_MONTH_MIN <= v <= NEW_MONTH_MAX):
            r.fail(f"new month {m} has an implausible total: {v:,} offences "
                   f"(expected {NEW_MONTH_MIN:,}-{NEW_MONTH_MAX:,})")

    # 16. every previously published row must still be represented
    o_keys = old.groupby(KEY[:-1])["Number of offences"].sum()
    n_keys = new.groupby(KEY[:-1])["Number of offences"].sum()
    lost = o_keys.index.difference(n_keys.index)
    if len(lost):
        r.fail(f"{len(lost)} previously published dimension keys are gone")

    r.facts.update({
        "prev_rows": len(old),
        "prev_offences": int(old["Number of offences"].sum()),
        "prev_last_month": max(old_months),
    })
    return r
