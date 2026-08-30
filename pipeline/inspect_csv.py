"""
inspect_csv.py — decide what a downloaded CSV actually IS by reading it.

Nothing here looks at the filename. Every conclusion comes from the Year and
Month number columns and the offence-category vocabulary inside the file.

Release shapes we have actually observed on this portal:

  single_month        one crime month only (e.g. the January 2024 release,
                      which contained only 2023-12)
  cumulative_current  the SerPro series: starts 2023-12, grows monthly
  cumulative_history  the PROMIS series: starts 2008-01
  partial_history     PROMIS series with a truncated start (the April 2024
                      backfill starts 2014-01, not 2008-01)
  unknown             anything that does not match - always a STOP condition
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field, asdict

import pandas as pd

# The two offence-category vocabularies. Membership in one of these is how we
# tell which recording system produced a file, without trusting its name.
PROMIS_CATEGORIES = {
    "Abduction - harassment and other offences against the person",
    "Acts intended to cause Injury", "Acts intended to cause injury",
    "Commercial break-ins", "Homicide and related Offences", "House break-ins",
    "Motor vehicle theft and related offences",
    "Other dangerous or negligent acts endangering persons",
    "Property Damage Offences", "Robbery - extortion and related offences",
    "Sexual assault and related offences",
    "Theft and related offences (other than MV)",
}
SERPRO_CATEGORIES = {
    "01 Homicide", "02 Assault", "03 Sexual offences",
    "04 Harm or endanger persons", "05 Robbery, blackmail, and extortion",
    "061 Burglary - dwelling", "062 Burglary - non-residential",
    "07 Theft", "11 Property damage offences",
}

REQUIRED_COLUMNS = {
    "As At", "Year", "Month number", "Offence category", "Offence type",
    "Alcohol involvement", "DV involvement", "Statistical Area 2",
    "Number of offences",
}
# 'Reporting region' / 'Reporting Region' both occur; handled separately.

SERPRO_START = pd.Period("2023-12", freq="M")
PROMIS_START = pd.Period("2008-01", freq="M")


@dataclass
class Report:
    ok: bool
    shape: str
    era: str
    rows: int
    offences: int
    first_month: str
    last_month: str
    months: int
    contiguous: bool
    missing_months: list = field(default_factory=list)
    columns: list = field(default_factory=list)
    as_at: str = ""
    unknown_categories: list = field(default_factory=list)
    problems: list = field(default_factory=list)

    def as_dict(self):
        return asdict(self)


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Strip header whitespace and unify the region column name. The trailing
    space has moved between eras (it was on 'Reporting region ', it is now on
    'Offence type '), so we strip every header rather than special-casing."""
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    if "Reporting region" in df.columns and "Reporting Region" not in df.columns:
        df = df.rename(columns={"Reporting region": "Reporting Region"})
    for col in ["Offence category", "Offence type", "Reporting Region",
                "Statistical Area 2", "Alcohol involvement", "DV involvement"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def load(source) -> pd.DataFrame:
    """Load from a path or raw bytes, then normalise."""
    if isinstance(source, (bytes, bytearray)):
        df = pd.read_csv(io.BytesIO(source), dtype=str)
    else:
        df = pd.read_csv(source, dtype=str)
    return normalise(df)


def inspect(df: pd.DataFrame) -> Report:
    problems: list[str] = []
    cols = list(df.columns)

    missing_cols = REQUIRED_COLUMNS - set(cols)
    if missing_cols:
        problems.append(f"missing required columns: {sorted(missing_cols)}")
    if "Reporting Region" not in cols:
        problems.append("no reporting region column in any known spelling")
    if problems:
        return Report(False, "unknown", "unknown", len(df), 0, "", "", 0, False,
                      columns=cols, problems=problems)

    try:
        year = df["Year"].astype(int)
        month = df["Month number"].astype(int)
    except Exception as exc:
        return Report(False, "unknown", "unknown", len(df), 0, "", "", 0, False,
                      columns=cols, problems=[f"Year/Month not numeric: {exc}"])

    if not month.between(1, 12).all():
        problems.append("Month number outside 1-12")
    if not year.between(2000, 2100).all():
        problems.append("Year outside a plausible range")

    n = pd.to_numeric(df["Number of offences"], errors="coerce")
    if n.isna().any():
        problems.append(f"{int(n.isna().sum())} non-numeric offence counts")
    if (n.fillna(0) < 0).any():
        problems.append("negative offence counts present")

    per = pd.PeriodIndex.from_fields(year=year, month=month, freq="M")
    uniq = pd.PeriodIndex(sorted(set(per)))
    expected = pd.period_range(uniq.min(), uniq.max(), freq="M")
    missing = [str(p) for p in expected if p not in set(uniq)]

    cats = set(df["Offence category"].unique())
    promis_hits = len(cats & PROMIS_CATEGORIES)
    serpro_hits = len(cats & SERPRO_CATEGORIES)
    if serpro_hits and not promis_hits:
        era = "Current / SerPro"
    elif promis_hits and not serpro_hits:
        era = "Historical / PROMIS"
    elif promis_hits and serpro_hits:
        era = "mixed"
        problems.append("file mixes PROMIS and SerPro offence categories")
    else:
        era = "unknown"
        problems.append("offence categories match neither known classification")

    unknown_cats = sorted(cats - PROMIS_CATEGORIES - SERPRO_CATEGORIES)
    if unknown_cats:
        problems.append(f"unrecognised offence categories: {unknown_cats}")

    # Shape, decided purely from the periods present.
    if len(uniq) == 1:
        shape = "single_month"
    elif uniq.min() == PROMIS_START:
        shape = "cumulative_history"
    elif uniq.min() == SERPRO_START:
        shape = "cumulative_current"
    elif era == "Historical / PROMIS":
        shape = "partial_history"
    else:
        shape = "unknown"
        problems.append(
            f"unrecognised coverage: starts {uniq.min()}, ends {uniq.max()}")

    as_at = ""
    try:
        as_at = str(pd.to_datetime(df["As At"].iloc[0], dayfirst=True).date())
    except Exception:
        problems.append("could not parse 'As At'")

    return Report(
        ok=not problems,
        shape=shape,
        era=era,
        rows=len(df),
        offences=int(n.fillna(0).sum()),
        first_month=str(uniq.min()),
        last_month=str(uniq.max()),
        months=len(uniq),
        contiguous=not missing,
        missing_months=missing,
        columns=cols,
        as_at=as_at,
        unknown_categories=unknown_cats,
        problems=problems,
    )


def inspect_source(source) -> tuple[pd.DataFrame, Report]:
    df = load(source)
    return df, inspect(df)
