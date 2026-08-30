"""
manifest.py — the pipeline's memory of which official extract supplies which
period, and what each one hashed to when it was accepted.

The two historical extracts are PINNED. The pipeline will never replace them
automatically, no matter what appears on the portal. If the government ever
publishes something that would change the historical period, the pipeline
reports it and stops (see update.py --check-history). Replacing pinned history
is a deliberate human decision, because a silent change to 2008-2023 would
invalidate every published analysis built on this dataset.
"""

from __future__ import annotations

import hashlib
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(BASE, "data", "manifest.json")

DEFAULT = {
    "schema": 1,
    "note": ("Historical entries are pinned and never replaced automatically. "
             "See METHODOLOGY.md for why these two extracts were chosen."),
    "historical": [
        {
            "role": "historical_early",
            "file": "data/historical_raw/nt_crime_statistics_nov_2023_updated_03_24.csv",
            "covers": ["2008-01", "2013-12"],
            "dataset_title": "NT Crime Statistics January 2024",
            "resource_url": ("https://data.nt.gov.au/dataset/ca417769-513c-49ed-9b8c-b08d13aac533/"
                             "resource/2b264226-fac9-4bb2-9519-4cf28270ce1a/download/"
                             "nt_crime_statistics_nov_2023_updated_03_24.csv"),
            "md5": None,
            "pinned": True,
        },
        {
            "role": "historical_late",
            "file": "data/historical_raw/nt_crime_statistics_nov_2023_updated_04_24.csv",
            "covers": ["2014-01", "2023-11"],
            "dataset_title": "NT Crime Statistics February 2024",
            "resource_url": ("https://data.nt.gov.au/dataset/16c38102-69c5-413e-b92e-378593a9649d/"
                             "resource/ad7c48ea-31f2-448f-b526-f735295be5b3/download/"
                             "nt_crime_statistics_nov_2023_updated_04_24.csv"),
            "md5": None,
            "pinned": True,
        },
    ],
    "current": {
        "role": "current",
        "file": "data/nt_crime_statistics_june_2026.csv",
        "covers_from": "2023-12",
        "covers_to": None,
        "dataset_title": "Current - NT Crime Statistics June 2026",
        "resource_url": None,
        "as_at": None,
        "md5": None,
        "pinned": False,
    },
    "expected_licence": {"license_id": "cc-by",
                         "license_title": "Creative Commons Attribution"},
    "last_run": None,
}


def md5_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load() -> dict:
    if os.path.isfile(MANIFEST_PATH):
        with open(MANIFEST_PATH) as fh:
            return json.load(fh)
    return json.loads(json.dumps(DEFAULT))


def save(man: dict) -> None:
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w") as fh:
        json.dump(man, fh, indent=2)
        fh.write("\n")


def refresh_hashes(man: dict) -> dict:
    """Record the md5 of every source currently on disk."""
    for entry in man["historical"] + [man["current"]]:
        path = os.path.join(BASE, entry["file"])
        entry["md5"] = md5_file(path) if os.path.isfile(path) else None
    return man


def verify_pinned(man: dict) -> list[str]:
    """Confirm the pinned historical files on disk still match their recorded
    hashes. A mismatch means someone or something altered history locally."""
    problems = []
    for entry in man["historical"]:
        path = os.path.join(BASE, entry["file"])
        if not os.path.isfile(path):
            problems.append(f"pinned historical file missing: {entry['file']}")
            continue
        if entry.get("md5") and md5_file(path) != entry["md5"]:
            problems.append(
                f"pinned historical file CHANGED on disk: {entry['file']} "
                f"(expected md5 {entry['md5']})")
    return problems
