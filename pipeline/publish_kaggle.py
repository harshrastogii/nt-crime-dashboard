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
        "licenses": [{"name": "CC-BY-4.0"}],
        "subtitle": "222 months of recorded crime in the Northern Territory, 2008-2026",
        "description": description(),
        "keywords": ["crime", "australia", "northern territory", "policing",
                     "public safety", "time series", "government"],
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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--message", default="Automated update")
    args = ap.parse_args(argv)

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
        res = kaggle_cli(["datasets", "version", "-p", tmp, "-m", args.message,
                          "--dir-mode", "skip"], cwd=tmp)
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
