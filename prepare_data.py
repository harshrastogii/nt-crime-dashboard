"""
prepare_data.py — NT Crime dashboard data preparation.
Run once: `python prepare_data.py`  ->  crime_clean.parquet

Key design choice (v2): the source 'Reporting Region' lumps ~20 distinct
Statistical Area 2 (SA2) localities under the single label "NT Balance".
That hides the Territory's remote communities — exactly the geography NT
policy focuses on. We therefore build a true `Location` field: the town name
where the region IS a town, and the SA2 name where the region is "NT Balance".
"""

import pandas as pd

# Auto-discover every CSV in the data folder. To add a new month (e.g. April),
# just drop nt_crime_statistics_apr_2026.csv into ./data and re-run this script —
# no code change needed. Falls back to the current folder if ./data is absent.
import glob, os

DATA_DIR = "data" if os.path.isdir("data") else "."
CSV_FILES = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
if not CSV_FILES:
    raise SystemExit(f"No CSV files found in '{DATA_DIR}/'. Add the NT crime CSVs there and re-run.")
print(f"Reading {len(CSV_FILES)} CSV file(s) from '{DATA_DIR}/': "
      + ", ".join(os.path.basename(f) for f in CSV_FILES))

df = pd.concat([pd.read_csv(f) for f in CSV_FILES], ignore_index=True)
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
df["complete_year"] = df["Year"].isin([2024, 2025])
df["post_anzsoc"] = (df["Year"] > 2025) | ((df["Year"] == 2025) & (df["Month number"] >= 4))
df["Number of offences"] = pd.to_numeric(df["Number of offences"], errors="coerce").fillna(0).astype(int)

keep = ["Year", "Month number", "Crime Type", "Reporting Region", "Location",
        "Location Type", "Alcohol involvement", "DV involvement",
        "Population", "lat", "lon", "complete_year", "post_anzsoc",
        "Number of offences"]
df[keep].to_parquet("crime_clean.parquet", index=False)

n_loc = df["Location"].nunique()
n_rate = df.dropna(subset=["Population"])["Location"].nunique()
print(f"Wrote crime_clean.parquet — {len(df):,} rows, {df['Number of offences'].sum():,} offences")
print(f"Locations: {n_loc} (was 8 regions). With per-capita rates: {n_rate}.")
