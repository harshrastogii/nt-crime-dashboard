"""
prepare_data.py — NT Crime dashboard data preparation.
Run once: `python prepare_data.py`  ->  crime_clean.parquet + kaggle/nt_crime_clean.csv

Key design choice (v2): the source 'Reporting Region' lumps ~20 distinct
Statistical Area 2 (SA2) localities under the single label "NT Balance".
That hides the Territory's remote communities — exactly the geography NT
policy focuses on. We therefore build a true `Location` field: the town name
where the region IS a town, and the SA2 name where the region is "NT Balance".

Key correctness fix (v3): each monthly download from the NT government is a
CUMULATIVE extract — it contains the ENTIRE history back to Dec 2023, not just
that month. Concatenating the files therefore counted early months once per
file (~5.5x inflation overall, worse the further back you go) and mixed in
superseded figures, since NT revises past months in later releases. We now use
exactly ONE file: the most recent release. Older files are kept on disk as an
archive but are not read.

Note on picking the newest file: filenames sort alphabetically as
apr, feb, jan, june, mar, may — so sorted()[-1] is WRONG. We read the
authoritative 'As At' release date from inside each file instead.
"""

import pandas as pd
import glob, os

DATA_DIR = "data" if os.path.isdir("data") else "."
CSV_FILES = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
if not CSV_FILES:
    raise SystemExit(f"No CSV files found in '{DATA_DIR}/'. Add the NT crime CSVs there and re-run.")


def release_date(path):
    """The 'As At' value the NT government stamps on every row of a release."""
    head = pd.read_csv(path, nrows=1)
    head.columns = [c.strip() for c in head.columns]
    return pd.to_datetime(head["As At"].iloc[0], dayfirst=True)


releases = sorted(((release_date(f), f) for f in CSV_FILES), key=lambda t: t[0])
as_at, LATEST = releases[-1]
superseded = [os.path.basename(f) for _, f in releases[:-1]]

print(f"Found {len(CSV_FILES)} cumulative extract(s) in '{DATA_DIR}/'.")
print(f"Using ONLY the newest: {os.path.basename(LATEST)} (As At {as_at:%d/%m/%Y})")
if superseded:
    print(f"Ignoring {len(superseded)} superseded extract(s): " + ", ".join(superseded))

df = pd.read_csv(LATEST)
df.columns = [c.strip() for c in df.columns]
for col in ["Offence type", "Offence category", "Reporting Region",
            "Statistical Area 2", "Alcohol involvement", "DV involvement"]:
    df[col] = df[col].astype(str).str.strip()

# --- Offence category -> simplified label ---
CATEGORY_MAP = {
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
df["Crime Type"] = df["Offence category"].map(CATEGORY_MAP).fillna("Other Crimes")

# --- TRUE LOCATION: town name, or SA2 name when region is "NT Balance" ---
df["Location"] = df["Reporting Region"]
mask = df["Reporting Region"] == "NT Balance"
df.loc[mask, "Location"] = df.loc[mask, "Statistical Area 2"]
# Tidy the residual unknowns into one bucket
df["Location"] = df["Location"].replace({"Unknown": "Unknown / not stated", "nan": "Unknown / not stated"})

# --- Location type (urban / regional / remote) for every location ---
URBAN = {"Darwin", "Palmerston"}
REGIONAL = {"Alice Springs", "Katherine", "Tennant Creek"}
def loc_type(name):
    if name in URBAN: return "Urban"
    if name in REGIONAL: return "Regional"
    return "Remote"  # all SA2 localities + Nhulunbuy are remote
df["Location Type"] = df["Location"].map(loc_type)

# --- Population (ABS 2021) — towns + SA2s with VERIFIED figures only ---
# SA2s without a confident public figure are intentionally left as None so the
# app shows COUNTS for them but never an invented per-capita rate.
POPULATION = {
    # towns
    "Darwin": 139902, "Palmerston": 37247, "Alice Springs": 25912,
    "Katherine": 10000, "Tennant Creek": 3000, "Nhulunbuy": 4000,
    # SA2 localities (ABS 2021 Census usual-resident counts; verified)
    "East Arnhem": 6989, "West Arnhem": 5204, "Tiwi Islands": 2348,
    # remaining SA2s: population not confidently sourced -> rate suppressed
}
df["Population"] = df["Location"].map(POPULATION)  # NaN where unknown

# --- Approx coordinates for the map (towns + SA2 centroids that are sourceable)
COORDS = {
    "Darwin": (-12.4634, 130.8456), "Palmerston": (-12.4861, 130.9833),
    "Katherine": (-14.4639, 132.2635), "Alice Springs": (-23.6980, 133.8807),
    "Tennant Creek": (-19.6472, 134.1903), "Nhulunbuy": (-12.1825, 136.7819),
    "East Arnhem": (-12.8, 135.8), "West Arnhem": (-12.4, 133.4),
    "Tiwi Islands": (-11.6, 130.9), "Gulf": (-16.5, 136.5),
    "Tanami": (-20.5, 130.0), "Victoria River": (-16.4, 131.0),
    "Barkly": (-19.0, 135.5), "Daly": (-13.8, 130.7),
    "Sandover - Plenty": (-21.5, 135.5), "Petermann - Simpson": (-25.0, 132.0),
    "Yuendumu - Anmatjere": (-22.2, 131.8), "Anindilyakwa": (-13.9, 136.4),
    "Elsey": (-15.0, 133.1), "Alligator": (-12.9, 132.5),
    "Thamarrurr": (-14.2, 129.5), "Howard Springs": (-12.49, 131.05),
    "Humpty Doo": (-12.58, 131.13), "Virginia": (-12.52, 131.02),
    "Weddell": (-12.55, 131.0),
}
df["lat"] = df["Location"].map(lambda x: COORDS.get(x, (None, None))[0])
df["lon"] = df["Location"].map(lambda x: COORDS.get(x, (None, None))[1])

# --- Flags ---
df["Number of offences"] = pd.to_numeric(df["Number of offences"], errors="coerce").fillna(0).astype(int)
df["complete_year"] = df["Year"].isin([2024, 2025])

# --- Counting-rule breaks -------------------------------------------------
# The NT government changed how offences are recorded TWICE. Counts either
# side of a break are not directly comparable, so every row is stamped with
# the regime it was recorded under.
#   Nov 2023 — revised recording practice
#   Apr 2025 — move to the ANZSOC classification
period = pd.PeriodIndex.from_fields(year=df["Year"], month=df["Month number"], freq="M")
BREAK_1 = pd.Period("2023-11", freq="M")   # revised recording practice
BREAK_2 = pd.Period("2025-04", freq="M")   # ANZSOC reclassification

df["Counting Rules Era"] = pd.Series(
    pd.cut(
        period.astype("int64"),
        bins=[-float("inf"), BREAK_1.ordinal - 1, BREAK_2.ordinal - 1, float("inf")],
        labels=["Pre-Nov-2023", "Nov-2023 to Mar-2025", "Post-Apr-2025 (ANZSOC)"],
    ),
    index=df.index,
).astype(str)

# True on the first month of each new regime — useful for drawing a break
# line on a time series.
df["is_break_month"] = period.isin([BREAK_1, BREAK_2])

# Kept for backwards compatibility with the existing app.
df["post_anzsoc"] = period >= BREAK_2

keep = ["Year", "Month number", "Crime Type", "Reporting Region", "Location",
        "Location Type", "Alcohol involvement", "DV involvement",
        "Population", "lat", "lon", "complete_year", "post_anzsoc",
        "Counting Rules Era", "is_break_month",
        "Number of offences"]
df[keep].to_parquet("crime_clean.parquet", index=False)

n_loc = df["Location"].nunique()
n_rate = df.dropna(subset=["Population"])["Location"].nunique()
print(f"Wrote crime_clean.parquet — {len(df):,} rows, {df['Number of offences'].sum():,} offences")
print(f"Locations: {n_loc} (was 8 regions). With per-capita rates: {n_rate}.")

# --- Kaggle-ready CSV -----------------------------------------------------
# A flat, self-describing publication copy: real place names (not the
# "NT Balance" catch-all), the population column, and the counting-rule
# break markers so a downstream user cannot accidentally compare across them.
KAGGLE_DIR = "kaggle"
os.makedirs(KAGGLE_DIR, exist_ok=True)

kag = df.copy()
kag["Date"] = period.to_timestamp().strftime("%Y-%m")
kag_cols = ["Date", "Year", "Month number", "Crime Type", "Offence category",
            "Offence type", "Reporting Region", "Location", "Location Type",
            "Population", "Alcohol involvement", "DV involvement",
            "Counting Rules Era", "is_break_month", "Number of offences"]
kag = kag[kag_cols].sort_values(["Date", "Location", "Crime Type"]).reset_index(drop=True)

kaggle_path = os.path.join(KAGGLE_DIR, "nt_crime_clean.csv")
kag.to_csv(kaggle_path, index=False)
print(f"Wrote {kaggle_path} — {len(kag):,} rows, "
      f"{kag['Date'].min()} to {kag['Date'].max()}, "
      f"source release As At {as_at:%d/%m/%Y}")
