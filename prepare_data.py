"""
prepare_data.py — build the dashboard's data from the published Kaggle dataset.

    python prepare_data.py            # download from Kaggle, verify, build
    python prepare_data.py --local    # use kaggle/nt_crime_master.csv (offline)

Writes crime_clean.parquet (read by app.py) and dashboard_source.json (which
the dashboard shows, so anyone can see exactly what it is built from).

Why Kaggle. The dashboard and the public dataset must show the same numbers,
so the dashboard reads the dataset itself rather than re-deriving it from raw
government files. The download is checked against the MD5 of the release being
deployed (data_release.json, written by the deploy workflow). If Kaggle cannot
be reached or serves something else, the byte-identical copy committed to
GitHub at the same release is used instead, and the dashboard says so.

Why only the current era. The dashboard compares calendar years and computes
per-capita rates. The NT Government advises that data from December 2023 onward
must not be compared with anything earlier, because NT Police changed recording
systems between November and December 2023, and population is a 2021 reference
figure supplied only for that period. So the dashboard uses the dataset's
"Current / SerPro" rows: everything from December 2023 to the latest month.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import ssl
import sys
import time
import urllib.request
import zipfile

import pandas as pd

OWNER_SLUG = "harshrastogiii/northern-territory-crime-statistics-2008-2026"
KAGGLE_ZIP = f"https://www.kaggle.com/api/v1/datasets/download/{OWNER_SLUG}"
KAGGLE_INFO = ("https://www.kaggle.com/api/v1/datasets/list?search="
               + OWNER_SLUG.split("/")[1])
GITHUB_RAW = ("https://raw.githubusercontent.com/harshrastogii/nt-crime-dashboard/"
              "{ref}/kaggle/nt_crime_master.csv")
LOCAL_MASTER = os.path.join("kaggle", "nt_crime_master.csv")
RELEASE_FILE = "data_release.json"
CURRENT_ERA = "Current / SerPro"

REQUIRED = ["Date", "Year", "Month number", "Crime Type", "Reporting Region",
            "Location", "Location Type", "Population (ABS 2021 reference)",
            "Alcohol involvement", "DV involvement", "Data era",
            "Number of offences"]

# Approximate coordinates for the map: towns, plus SA2 centroids that could be
# sourced. Koolpinyah and "Unknown / not stated" have none and are left off it.
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

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # certifi absent: fall back to the system trust store
    _SSL = ssl.create_default_context()


def log(msg: str) -> None:
    print(msg, flush=True)


def _get(url: str, tries: int = 3) -> bytes:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nt-crime-dashboard"})
            with urllib.request.urlopen(req, timeout=120, context=_SSL) as r:
                return r.read()
        except Exception as exc:
            last = exc
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def from_kaggle() -> bytes:
    with zipfile.ZipFile(io.BytesIO(_get(KAGGLE_ZIP))) as z:
        return z.read("nt_crime_master.csv")


def kaggle_version() -> int | None:
    try:
        info = json.loads(_get(KAGGLE_INFO))
        for d in info:
            if d.get("refNullable", d.get("ref", "")) == OWNER_SLUG or OWNER_SLUG in d.get("urlNullable", ""):
                return d.get("currentVersionNumber")
    except Exception:
        pass
    return None


def expected_release() -> dict | None:
    """What the deployed release should contain. Written by the deploy
    workflow; for local runs, derived from the committed copy if present."""
    if os.path.isfile(RELEASE_FILE):
        with open(RELEASE_FILE) as fh:
            return json.load(fh)
    if os.path.isfile(LOCAL_MASTER):
        blob = open(LOCAL_MASTER, "rb").read()
        return {"md5": hashlib.md5(blob).hexdigest(), "commit": "main"}
    return None


def acquire(local: bool) -> tuple[bytes, dict]:
    want = expected_release()
    want_md5 = (want or {}).get("md5")

    if local:
        blob = open(LOCAL_MASTER, "rb").read()
        return blob, {"source": "local copy (kaggle/nt_crime_master.csv)",
                      "verified": want_md5 == hashlib.md5(blob).hexdigest()}

    attempts = [("Kaggle", from_kaggle)]
    if want and want.get("commit"):
        attempts.append(("GitHub copy of the same release",
                         lambda: _get(GITHUB_RAW.format(ref=want["commit"]))))

    problems = []
    for name, fetch in attempts:
        try:
            blob = fetch()
        except Exception as exc:
            problems.append(f"{name} unreachable: {exc}")
            log(f"  {problems[-1]}")
            continue
        md5 = hashlib.md5(blob).hexdigest()
        if want_md5 and md5 != want_md5:
            problems.append(f"{name} served md5 {md5}, release is {want_md5}")
            log(f"  {problems[-1]}")
            continue
        return blob, {"source": name, "verified": bool(want_md5),
                      "fallback_reasons": problems}
    raise SystemExit("STOP: no source supplied the expected release:\n  " + "\n  ".join(problems))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true",
                    help="build from kaggle/nt_crime_master.csv instead of downloading")
    args = ap.parse_args(argv)

    log("Fetching the NT crime dataset…")
    blob, prov = acquire(args.local)
    md5 = hashlib.md5(blob).hexdigest()
    master = pd.read_csv(io.BytesIO(blob), low_memory=False)

    missing = [c for c in REQUIRED if c not in master.columns]
    if missing:
        raise SystemExit(f"STOP: dataset is missing columns the dashboard needs: {missing}")
    months = pd.PeriodIndex(sorted(master["Date"].unique()), freq="M")
    if len(months) != len(pd.period_range(months.min(), months.max(), freq="M")):
        raise SystemExit("STOP: dataset has missing months")

    df = master[master["Data era"] == CURRENT_ERA].copy()
    df = df.rename(columns={"Population (ABS 2021 reference)": "Population"})
    df["lat"] = df["Location"].map(lambda x: COORDS.get(x, (None, None))[0])
    df["lon"] = df["Location"].map(lambda x: COORDS.get(x, (None, None))[1])

    # A year counts as complete when all twelve of its months are present.
    months_per_year = df.groupby("Year")["Month number"].nunique()
    complete = sorted(int(y) for y, n in months_per_year.items() if n == 12)
    df["complete_year"] = df["Year"].isin(complete)
    df["post_anzsoc"] = pd.PeriodIndex(df["Date"], freq="M") >= pd.Period("2025-04", freq="M")

    keep = ["Year", "Month number", "Crime Type", "Reporting Region", "Location",
            "Location Type", "Alcohol involvement", "DV involvement",
            "Population", "lat", "lon", "complete_year", "post_anzsoc",
            "Number of offences"]
    df[keep].to_parquet("crime_clean.parquet", index=False)

    era_months = sorted(df["Date"].unique())
    partial = {int(y): sorted(int(m) for m in g["Month number"].unique())
               for y, g in df.groupby("Year") if int(y) not in complete}
    summary = {
        "source": prov["source"],
        "verified_against_release": prov["verified"],
        "fallback_reasons": prov.get("fallback_reasons", []),
        "dataset": OWNER_SLUG,
        "kaggle_version": kaggle_version() if prov["source"] == "Kaggle" else None,
        "md5": md5,
        "dataset_rows": len(master),
        "dataset_offences": int(master["Number of offences"].sum()),
        "dataset_first": str(months.min()),
        "dataset_last": str(months.max()),
        "dashboard_rows": len(df),
        "dashboard_offences": int(df["Number of offences"].sum()),
        "dashboard_first": era_months[0],
        "dashboard_last": era_months[-1],
        "complete_years": complete,
        "partial_years": partial,
        "built_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
    }
    with open("dashboard_source.json", "w") as fh:
        json.dump(summary, fh, indent=2)

    log(f"Source: {prov['source']} (md5 {md5}, "
        f"{'verified against the release' if prov['verified'] else 'not verified'})")
    log(f"Wrote crime_clean.parquet — {len(df):,} rows, "
        f"{summary['dashboard_offences']:,} offences, "
        f"{era_months[0]} to {era_months[-1]} (current era of {len(master):,}-row dataset)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
