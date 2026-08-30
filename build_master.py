"""
build_master.py — kept for backwards compatibility.

The build logic now lives in pipeline/build.py so the automated pipeline can
call it with any current-era source. This wrapper rebuilds the master dataset
from whatever the manifest currently points at.

    python build_master.py
"""
import os

from pipeline import build, manifest

man = manifest.load()
BASE = manifest.BASE
cur = os.path.join(BASE, man["current"]["file"])
label = man["current"].get("dataset_title") or "current extract"
if man["current"].get("covers_to"):
    label = f"{man['current']['covers_to']} current extract"
    if man["current"].get("as_at"):
        label += f" (As At {man['current']['as_at']})"
else:
    label = "June 2026 current extract"

out = build.build(
    current_file=cur,
    hist_early=os.path.join(BASE, man["historical"][0]["file"]),
    hist_late=os.path.join(BASE, man["historical"][1]["file"]),
    current_label=label,
)
print(f"Wrote kaggle/nt_crime_master.csv — {len(out):,} rows, "
      f"{out['Number of offences'].sum():,} offences, {out['Date'].nunique()} months, "
      f"{out['Date'].min()} to {out['Date'].max()}")
