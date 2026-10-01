"""
write_release.py — record which data release a dashboard deploy expects.

    python scripts/write_release.py data_release.json

The deploy workflow writes this into the Hugging Face snapshot. When the Space
builds, prepare_data.py downloads the dataset from Kaggle and checks it against
this fingerprint, so the dashboard can only ever show the release that was
published alongside this code. Standard library only, so the deploy job needs
no installs.
"""

import csv
import hashlib
import io
import json
import os
import sys

MASTER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "kaggle", "nt_crime_master.csv")


def main(out: str) -> int:
    blob = open(MASTER, "rb").read()
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8")))
    rows, offences, months = 0, 0, set()
    for r in reader:
        rows += 1
        offences += int(r["Number of offences"])
        months.add(r["Date"])
    release = {
        "md5": hashlib.md5(blob).hexdigest(),
        "commit": os.environ.get("GITHUB_SHA", "main"),
        "rows": rows,
        "offences": offences,
        "first_month": min(months),
        "last_month": max(months),
    }
    with open(out, "w") as fh:
        json.dump(release, fh, indent=2)
    print(json.dumps(release))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data_release.json"))
