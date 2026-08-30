"""
publish_kaggle.py — push a new version of the ONE persistent Kaggle dataset.

    python -m pipeline.publish_kaggle --check     verify credentials only
    python -m pipeline.publish_kaggle --dry-run   stage files, do not upload
    python -m pipeline.publish_kaggle             create or version the dataset

Staging is deliberate: we copy exactly three files into a clean temp directory
and upload that. The repository's kaggle/ folder also holds backups, the older
clean dataset and update reports, and none of those belong in a public release.
Uploading a directory wholesale is how development files leak.

Credentials come from the environment (KAGGLE_USERNAME / KAGGLE_KEY) or from
~/.kaggle/kaggle.json. They are never read into the repo, never logged, and
never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAGGLE_DIR = os.path.join(BASE, "kaggle")

DATASET_SLUG = "northern-territory-crime-statistics-2008-2026"
TITLE = "Northern Territory Crime Statistics — 2008–2026"
SUBTITLE = "222 months of recorded crime in the Northern Territory, 2008-2026"
KEYWORDS = ["crime", "australia", "government", "public safety", "law"]
# `datasets create` takes the short slug; the settings-update endpoint
# validates against the display name. Same licence, two spellings.
LICENSE_SLUG = "CC-BY-4.0"
LICENSE_DISPLAY_NAME = "Attribution 4.0 International (CC BY 4.0)"


def kaggle_username() -> str | None:
    """The Kaggle account that will own the dataset. Never hard-coded: a Kaggle
    username need not match the GitHub one. Resolved in the same order the CLI
    itself authenticates - access token, then legacy key."""
    if os.environ.get("KAGGLE_USERNAME"):
        return os.environ["KAGGLE_USERNAME"]
    path = os.path.join(os.path.expanduser("~"), ".kaggle", "kaggle.json")
    if os.path.isfile(path):
        try:
            with open(path) as fh:
                user = json.load(fh).get("username")
            if user:
                return user
        except Exception:
            pass
    # Access-token auth: the CLI resolves the username by introspecting the
    # token, so ask it rather than trying to decode the token ourselves.
    try:
        res = subprocess.run([sys.executable, "-m", "kaggle", "config", "view"],
                             capture_output=True, text=True, timeout=120)
        for line in res.stdout.splitlines():
            if line.strip().startswith("- username:"):
                val = line.split(":", 1)[1].strip()
                if val and val.lower() != "none":
                    return val
    except Exception:
        pass
    return None


def dataset_id() -> str | None:
    user = kaggle_username()
    return f"{user}/{DATASET_SLUG}" if user else None

UPLOAD_FILES = ["nt_crime_master.csv", "DATA_DICTIONARY.md", "METHODOLOGY.md"]


def have_credentials() -> tuple[bool, str]:
    if os.environ.get("KAGGLE_API_TOKEN"):
        return True, "environment (KAGGLE_API_TOKEN)"
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True, "environment (KAGGLE_USERNAME/KAGGLE_KEY)"
    for name in ("access_token", "kaggle.json"):
        if os.path.isfile(os.path.join(os.path.expanduser("~"), ".kaggle", name)):
            return True, f"~/.kaggle/{name}"
    return False, "none found"


def description() -> str:
    return """\
Recorded crime in the Northern Territory of Australia, every month from
January 2008 to June 2026 — 222 consecutive months with no gaps.

Built from the Northern Territory Government's official open data releases and
reassembled into a single clean time series, with the traps that make this
source difficult already handled.

## What's inside

- 56,217 rows, 567,438 recorded offences
- 222 months, January 2008 → June 2026, no missing months
- 27 locations, including remote communities that the government's default
  "NT Balance" grouping hides
- Offence category and type as published, plus a simplified `Crime Type` that
  spans both eras
- Alcohol and domestic-violence involvement for assault offences

## Read this before analysing

**The recording system changed between November 2023 and December 2023.** The
NT Police moved from PROMIS to SerPro. The NT Government advises that data from
December 2023 onward should not be compared directly with earlier data. Every
row is tagged `Data era` so you can separate the two. The simplified
`Crime Type` field lets you group both eras under one set of labels, but it does
not make them comparable.

**November 2023 is a cutover month and is flagged provisional.** It exists in
this dataset (278 rows, 3,345 offences) but was not published in the original
November 2023 release — it appeared months later as a supplementary correction.
The NT Government advises that data for this period may be incomplete or
subject to later revision.

**April 2025 is flagged, but nothing changes there.** That is when NT adopted
the 2023 ANZSOC classification for reporting. It was applied retrospectively
across the whole current era, so categories do not change at that month inside
this dataset. The flag exists only to warn against comparing with NT
publications produced before May 2025.

**Alcohol involvement is not comparable across the full period.** Historically
"unknown" was a valid answer; during migration all unknown values were recoded
to "No". The NT metadata notes roughly 27% of assault offences previously
carried "unknown". A 2008–2026 alcohol trend line partly measures this coding
change.

**Population is a 2021 reference figure, not a time series.** It holds ABS 2021
Census counts and is populated only from December 2023 onward, for 9 of the 27
locations. It is blank everywhere else. Blank means unknown, not zero. Do not
compute historical per-capita rates from it.

## Files

- `nt_crime_master.csv` — the dataset
- `DATA_DICTIONARY.md` — every column explained
- `METHODOLOGY.md` — how it was built, which official extracts were used, and
  the known limitations

## Source and licence

Source: Northern Territory Government, Department of the Attorney-General and
Justice — NT Crime Statistics, published on the NTG Open Data Portal
(data.nt.gov.au). Offences recorded by NT Police.

The source data is published by the Northern Territory Government under a
Creative Commons Attribution (CC BY) licence; the portal does not specify a
version. This derived dataset is released under CC BY 4.0.

These are recorded offences, not victims, offenders, or court outcomes, and
they reflect crime reported to police rather than all crime that occurred. NT
figures are not comparable with other Australian jurisdictions.
"""


# File and column descriptions, taken verbatim in substance from
# DATA_DICTIONARY.md so the Kaggle data card and the shipped documentation can
# never drift apart.
COLUMN_DESCRIPTIONS = [
    ("Date", "yearmonth",
     "Month the offence was reported to NT Police, as YYYY-MM. Runs 2008-01 to 2026-06 with no gaps."),
    ("Year", "numeric", "Calendar year, 2008-2026. Always agrees with Date."),
    ("Month number", "numeric", "Month of year, 1 = January through 12 = December."),
    ("Crime Type", "string",
     "Simplified nine-value label available in both eras: Homicide, Assault & Violence, Sexual Offences, "
     "Harassment & Threats, Robbery & Extortion, Residential B&E, Commercial B&E, General Theft, Property Damage. "
     "Lets you group both eras under one set of labels, but does NOT make them directly comparable."),
    ("Offence category", "string",
     "The government's own high-level classification, kept exactly as published. Wording differs between the two "
     "eras (11 values under PROMIS, 9 under SerPro) with no shared value, so use it only within a single Data era."),
    ("Offence type", "string",
     "The government's detailed classification, kept exactly as published. 23 values in each era, none shared."),
    ("Reporting Region", "string",
     "One of seven NT reporting regions, plus Unknown. 'NT Balance' is the government's catch-all for everywhere "
     "outside the main towns."),
    ("Location", "string",
     "The usable geography field: the town name where the region is a town, or the Statistical Area 2 (SA2) name "
     "where the region is NT Balance. 27 distinct values, identical across both eras."),
    ("Location Type", "string",
     "Urban (Darwin, Palmerston), Regional (Alice Springs, Katherine, Tennant Creek), or Remote (all others)."),
    ("Population (ABS 2021 reference)", "numeric",
     "ABS 2021 Census usual-resident count. A single reference figure, NOT a population time series. Populated only "
     "from December 2023 onward and only for 9 of the 27 locations; blank everywhere else. Blank means unknown, not "
     "zero. Do not compute historical per-capita rates from it."),
    ("Alcohol involvement", "string",
     "Yes, No, or '-' (not applicable). Recorded for assault offences only. NOT comparable across the full period: "
     "historical 'unknown' values were recoded to No during migration, and roughly 27% of assault offences "
     "previously carried 'unknown'."),
    ("DV involvement", "string",
     "Domestic violence involvement for assault offences: Yes, No, or '-' (not applicable)."),
    ("Data era", "string",
     "Historical / PROMIS (2008-01 to 2023-11) or Current / SerPro (2023-12 to 2026-06). The NT Police recording "
     "system changed between these two periods."),
    ("Source extract", "string",
     "Which official government extract supplied the row: the March 2024 historical extract (2008-01 to 2013-12), "
     "the April 2024 historical extract (2014-01 to 2023-11), or the current extract (2023-12 onward)."),
    ("is_break_month", "boolean",
     "True on the two months where something documented changed: 2023-11 and 2025-04. The two events differ in kind "
     "- see Break note."),
    ("Break note", "string",
     "Blank except on the two break months. 2023-11 is the SerPro cutover month, flagged provisional. 2025-04 is "
     "when ANZSOC was adopted for NT reporting, applied retrospectively so categories do not change there."),
    ("Number of offences", "numeric",
     "Count of offences recorded by NT Police for this combination of month, offence, location and flags. Always 1 "
     "or more; never zero, negative or missing. A row is a count, not a single crime."),
]

FILE_DESCRIPTIONS = {
    "nt_crime_master.csv":
        "The dataset. 56,217 rows covering 222 consecutive months, January 2008 to June 2026, with no missing "
        "months. Each row is a count of offences recorded by NT Police for one combination of month, offence "
        "category and type, location, and (for assault offences) alcohol and domestic-violence involvement. Read "
        "Number of offences for the count - a row is not a single crime. Assembled from three official NT "
        "Government extracts; every row records which one it came from.",
    "DATA_DICTIONARY.md":
        "Every column explained in plain language, plus the three things to read before analysing: why offence "
        "categories cannot be compared across December 2023, why alcohol involvement is not comparable across the "
        "full period, and why the population column is a 2021 reference value rather than a time series.",
    "METHODOLOGY.md":
        "How the dataset was built and why. Covers the cumulative-file trap in the source portal, which three "
        "official extracts were used for which periods and why, the two documented breaks in the series "
        "(November 2023 and April 2025), the location and population decisions, what was verified, and the known "
        "limitations.",
}


# Provenance and cadence, stated exactly as METHODOLOGY.md documents them.
PROVENANCE = (
    "Northern Territory Government, Department of the Attorney-General and Justice - "
    "NT Crime Statistics, published on the NTG Open Data Portal (data.nt.gov.au), group "
    "'Crime, justice and law'. Offences are recorded by NT Police. Releases were "
    "discovered through the portal's CKAN API and identified by inspecting each file's "
    "Year and Month number columns rather than its filename, because the portal's "
    "filenames are unreliable (the release titled 'November 2023' contained no November "
    "2023 data). Every monthly release is cumulative, so files are never concatenated. "
    "This dataset is assembled from exactly three official extracts, each covering a "
    "distinct period: the March 2024 historical extract (2008-01 to 2013-12), the April "
    "2024 historical extract (2014-01 to 2023-11), and the current SerPro-era extract "
    "(2023-12 onward). The two historical extracts are pinned and are never replaced "
    "automatically. Source data is published under a Creative Commons Attribution "
    "(CC BY) licence; the portal does not specify a version. This derived dataset is "
    "released under CC BY 4.0. Full detail, including the two documented breaks in the "
    "series and the known limitations, is in METHODOLOGY.md."
)

# The NT Government publishes one release per month, roughly five weeks after the
# crime month ends. An automated pipeline checks the portal daily but only
# publishes when a genuinely new month appears, so the dataset's cadence is monthly.
UPDATE_FREQUENCY = "monthly"

COVER_IMAGE = "dataset-cover-image.png"


def resources_block() -> list:
    """Per-file and per-column descriptions for the Kaggle data card."""
    return [
        {
            "path": "nt_crime_master.csv",
            "description": FILE_DESCRIPTIONS["nt_crime_master.csv"],
            "schema": {
                "fields": [
                    {"name": n, "description": d, "type": t}
                    for n, t, d in COLUMN_DESCRIPTIONS
                ]
            },
        },
        {"path": "DATA_DICTIONARY.md", "description": FILE_DESCRIPTIONS["DATA_DICTIONARY.md"]},
        {"path": "METHODOLOGY.md", "description": FILE_DESCRIPTIONS["METHODOLOGY.md"]},
    ]


def stage(dest: str, ds_id: str) -> dict:
    os.makedirs(dest, exist_ok=True)
    for name in UPLOAD_FILES:
        src = os.path.join(KAGGLE_DIR, name)
        if not os.path.isfile(src):
            raise SystemExit(f"STOP: required upload file missing: {src}")
        shutil.copyfile(src, os.path.join(dest, name))

    meta = {
        "title": TITLE,
        "id": ds_id,
        "licenses": [{"name": LICENSE_SLUG}],
        "subtitle": SUBTITLE,
        "description": description(),
        "keywords": KEYWORDS,
        "resources": resources_block(),
    }
    with open(os.path.join(dest, "dataset-metadata.json"), "w") as fh:
        json.dump(meta, fh, indent=2)

    # Refuse to ship anything unexpected.
    allowed = set(UPLOAD_FILES) | {"dataset-metadata.json"}
    actual = set(os.listdir(dest))
    if actual - allowed:
        raise SystemExit(f"STOP: unexpected files staged: {sorted(actual - allowed)}")
    return meta


def verify(dest: str) -> dict:
    df = pd.read_csv(os.path.join(dest, "nt_crime_master.csv"), low_memory=False)
    facts = {
        "rows": len(df),
        "offences": int(df["Number of offences"].sum()),
        "months": df["Date"].nunique(),
        "first": df["Date"].min(),
        "last": df["Date"].max(),
        "locations": df["Location"].nunique(),
        "files": sorted(os.listdir(dest)),
    }
    if facts["months"] != len(pd.period_range(facts["first"], facts["last"], freq="M")):
        raise SystemExit("STOP: staged CSV has missing months")
    return facts


def kaggle_cli(args, cwd=None):
    """Invoke the Kaggle CLI. Credentials stay in the environment."""
    cmd = [sys.executable, "-m", "kaggle"] + args
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def data_block() -> list:
    """The same descriptions in the shape the settings endpoint stores."""
    return [
        {
            "name": "nt_crime_master.csv",
            "description": FILE_DESCRIPTIONS["nt_crime_master.csv"],
            "columns": [
                {"name": n, "description": d, "type": t}
                for n, t, d in COLUMN_DESCRIPTIONS
            ],
        },
        {"name": "DATA_DICTIONARY.md",
         "description": FILE_DESCRIPTIONS["DATA_DICTIONARY.md"], "columns": []},
        {"name": "METHODOLOGY.md",
         "description": FILE_DESCRIPTIONS["METHODOLOGY.md"], "columns": []},
    ]


def stage_metadata(dest: str, ds_id: str) -> dict:
    """Write dataset-metadata.json (plus the cover image) for a settings-only
    update. No data files: this path changes the data card, not the data."""
    os.makedirs(dest, exist_ok=True)
    meta = {
        "id": ds_id,
        "title": TITLE,
        "subtitle": SUBTITLE,
        "description": description(),
        "licenses": [{"name": LICENSE_DISPLAY_NAME}],
        "keywords": KEYWORDS,
        "resources": resources_block(),
        # The settings endpoint stores file/column descriptions under "data".
        # The CLI can derive it from "resources", but sending it explicitly is
        # what actually persists, so provide both.
        "data": data_block(),
        "userSpecifiedSources": PROVENANCE,
        "expectedUpdateFrequency": UPDATE_FREQUENCY,
        "isPrivate": False,
    }
    cover = os.path.join(KAGGLE_DIR, COVER_IMAGE)
    if os.path.isfile(cover):
        shutil.copyfile(cover, os.path.join(dest, COVER_IMAGE))
        meta["image"] = COVER_IMAGE
    with open(os.path.join(dest, "dataset-metadata.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    return meta


def update_metadata() -> int:
    """Push data-card metadata only - descriptions, provenance, cadence, cover."""
    ds_id = dataset_id()
    if not ds_id:
        print("STOP: cannot determine the Kaggle username (no credentials).")
        return 1
    tmp = tempfile.mkdtemp(prefix="kaggle_meta_")
    meta = stage_metadata(tmp, ds_id)
    print(f"Updating metadata for {ds_id}")
    print(f"  columns described : {len(meta['resources'][0]['schema']['fields'])}")
    print(f"  files described   : {len(meta['resources'])}")
    print(f"  provenance        : {len(meta['userSpecifiedSources'])} chars")
    print(f"  update frequency  : {meta['expectedUpdateFrequency']}")
    print(f"  cover image       : {meta.get('image') or 'none'}")
    res = kaggle_cli(["datasets", "metadata", "--update", "-p", tmp, ds_id], cwd=tmp)
    print(res.stdout.strip() or "(no output)")
    if res.returncode != 0:
        print(res.stderr.strip(), file=sys.stderr)
        return 1
    print(f"https://www.kaggle.com/datasets/{ds_id}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--update-metadata", action="store_true",
                    help="update the data card only; do not re-upload data")
    ap.add_argument("--message", default="Automated update")
    args = ap.parse_args(argv)

    if args.update_metadata:
        ok, where = have_credentials()
        print(f"Kaggle credentials: {'found in ' + where if ok else 'NOT FOUND'}")
        if not ok:
            return 1
        return update_metadata()

    ok, where = have_credentials()
    print(f"Kaggle credentials: {'found in ' + where if ok else 'NOT FOUND'}")
    if args.check:
        return 0 if ok else 1

    ds_id = dataset_id()
    if not ds_id:
        print("STOP: cannot determine the Kaggle username (no credentials).")
        return 1
    print(f"Target dataset: {ds_id}")
    tmp = tempfile.mkdtemp(prefix="kaggle_stage_")
    stage(tmp, ds_id)
    facts = verify(tmp)
    print(f"Staged for upload from {tmp}")
    for k, v in facts.items():
        print(f"  {k}: {v}")

    if args.dry_run:
        print("DRY RUN — nothing uploaded.")
        return 0
    if not ok:
        print("STOP: no Kaggle credentials available; not attempting upload.")
        return 1

    probe = kaggle_cli(["datasets", "status", ds_id])
    exists = probe.returncode == 0 and "404" not in (probe.stdout + probe.stderr)

    if exists:
        print(f"Dataset exists — pushing a new version: {ds_id}")
        # --keep-tabular: without it the CLI re-derives the schema during
        # conversion, which discards the column descriptions we supply.
        res = kaggle_cli(["datasets", "version", "-p", tmp, "-m", args.message,
                          "--keep-tabular", "--dir-mode", "skip"], cwd=tmp)
    else:
        print(f"Dataset not found — creating it: {ds_id}")
        # --public: the dataset is intended as a public release. Kaggle
        # creates privately by default, and visibility cannot be changed
        # from the CLI afterwards, so it must be set at creation time.
        res = kaggle_cli(["datasets", "create", "-p", tmp, "--public",
                          "--dir-mode", "skip"], cwd=tmp)

    print(res.stdout.strip())
    if res.returncode != 0:
        print(res.stderr.strip(), file=sys.stderr)
        return 1
    print(f"https://www.kaggle.com/datasets/{ds_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
