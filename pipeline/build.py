"""
build.py — assemble the master dataset from the three pinned/selected extracts.

This is the logic previously in build_master.py, refactored so the pipeline can
call it with any current-era source file. The transformation rules are
unchanged; only the source of the current segment is now a parameter.
"""

from __future__ import annotations

import os

import pandas as pd

from . import inspect_csv

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "kaggle", "nt_crime_master.csv")

P = lambda s: pd.Period(s, freq="M")
BREAK_CUTOVER = P("2023-11")   # last PROMIS month; SerPro rolled out this month
BREAK_ANZSOC = P("2025-04")    # ANZSOC adopted for NT reporting

HIST_CATEGORY_MAP = {
    "Homicide and related Offences": "Homicide",
    "Acts intended to cause Injury": "Assault & Violence",
    "Acts intended to cause injury": "Assault & Violence",
    "Sexual assault and related offences": "Sexual Offences",
    "Abduction - harassment and other offences against the person": "Harassment & Threats",
    "Other dangerous or negligent acts endangering persons": "Harassment & Threats",
    "Robbery - extortion and related offences": "Robbery & Extortion",
    "House break-ins": "Residential B&E",
    "Commercial break-ins": "Commercial B&E",
    "Theft and related offences (other than MV)": "General Theft",
    "Motor vehicle theft and related offences": "General Theft",
    "Property Damage Offences": "Property Damage",
}
CUR_CATEGORY_MAP = {
    "01 Homicide": "Homicide",
    "02 Assault": "Assault & Violence",
    "03 Sexual offences": "Sexual Offences",
    "04 Harm or endanger persons": "Harassment & Threats",
    "05 Robbery, blackmail, and extortion": "Robbery & Extortion",
    "061 Burglary - dwelling": "Residential B&E",
    "062 Burglary - non-residential": "Commercial B&E",
    "07 Theft": "General Theft",
    "11 Property damage offences": "Property Damage",
}
CATEGORY_MAP = {**HIST_CATEGORY_MAP, **CUR_CATEGORY_MAP}

URBAN = {"Darwin", "Palmerston"}
REGIONAL = {"Alice Springs", "Katherine", "Tennant Creek"}

# ABS 2021 Census usual-resident counts. A single point in time, applied only
# to the current era and never back-cast. See METHODOLOGY.md.
POPULATION_2021 = {
    "Darwin": 139902, "Palmerston": 37247, "Alice Springs": 25912,
    "Katherine": 10000, "Tennant Creek": 3000, "Nhulunbuy": 4000,
    "East Arnhem": 6989, "West Arnhem": 5204, "Tiwi Islands": 2348,
}

COLUMNS = ["Date", "Year", "Month number", "Crime Type", "Offence category",
           "Offence type", "Reporting Region", "Location", "Location Type",
           "Population (ABS 2021 reference)", "Alcohol involvement",
           "DV involvement", "Data era", "Source extract", "is_break_month",
           "Break note", "Number of offences"]


def _segment(path, lo, hi, label):
    df = inspect_csv.load(path)
    df["Year"] = df["Year"].astype(int)
    df["Month number"] = df["Month number"].astype(int)
    df["Number of offences"] = (
        pd.to_numeric(df["Number of offences"], errors="coerce").fillna(0).astype(int))
    per = pd.PeriodIndex.from_fields(year=df["Year"], month=df["Month number"], freq="M")
    df = df[(per >= P(lo)) & (per <= P(hi))].copy() if hi else df[per >= P(lo)].copy()
    df["Source extract"] = label
    return df


def build(current_file: str,
          hist_early: str,
          hist_late: str,
          current_label: str,
          out_path: str = OUT) -> pd.DataFrame:
    """Assemble and write the master dataset. Returns the DataFrame."""
    parts = [
        _segment(hist_early, "2008-01", "2013-12", "March 2024 historical extract"),
        _segment(hist_late, "2014-01", "2023-11", "April 2024 historical extract"),
        _segment(current_file, "2023-12", None, current_label),
    ]
    df = pd.concat(parts, ignore_index=True)
    per = pd.PeriodIndex.from_fields(
        year=df["Year"], month=df["Month number"], freq="M")

    df["Data era"] = "Historical / PROMIS"
    df.loc[per >= P("2023-12"), "Data era"] = "Current / SerPro"

    df["Crime Type"] = df["Offence category"].map(CATEGORY_MAP)
    unmapped = sorted(df.loc[df["Crime Type"].isna(), "Offence category"].unique())
    if unmapped:
        raise SystemExit(
            "STOP: unmapped offence categories, the government may have "
            f"changed its classification: {unmapped}")

    df["Location"] = df["Reporting Region"]
    mask = df["Reporting Region"] == "NT Balance"
    df.loc[mask, "Location"] = df.loc[mask, "Statistical Area 2"]
    df["Location"] = df["Location"].replace(
        {"Unknown": "Unknown / not stated", "nan": "Unknown / not stated",
         "": "Unknown / not stated"})
    df["Location Type"] = df["Location"].map(
        lambda n: "Urban" if n in URBAN else "Regional" if n in REGIONAL else "Remote")

    is_current = df["Data era"] == "Current / SerPro"
    df["Population (ABS 2021 reference)"] = (
        df["Location"].map(POPULATION_2021).where(is_current).astype("Int64"))

    df["is_break_month"] = per.isin([BREAK_CUTOVER, BREAK_ANZSOC])
    df["Break note"] = ""
    df.loc[per == BREAK_CUTOVER, "Break note"] = (
        "SerPro system cutover month - provisional; NT Government advises data "
        "for this period may be incomplete or subject to later revision")
    df.loc[per == BREAK_ANZSOC, "Break note"] = (
        "ANZSOC classification adopted for NT reporting from this month. Offence "
        "categories in this dataset were applied retrospectively and do not change "
        "here - use caution only when comparing against NT publications produced "
        "before May 2025")

    df["Date"] = per.astype(str)
    out = (df[COLUMNS]
           .sort_values(["Date", "Location", "Crime Type", "Offence type"])
           .reset_index(drop=True))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.to_csv(out_path, index=False)
    return out
