---
title: Territory Crime Atlas
emoji: 🗺️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# NT Crime Intelligence Dashboard

An interactive analytics dashboard for Northern Territory recorded-crime data, built in Python with [Plotly Dash](https://dash.plotly.com/). It re-imagines a Power BI dashboard I built in 2025 as a reproducible, code-driven, web-deployable tool — and adds analysis aimed at the questions a policymaker actually asks.

**Live demo:** _https://huggingface.co/spaces/harshrastogii/nt-crime-dashboard_

![dashboard preview](preview.png) <!-- add a screenshot named preview.png -->

---


---

## The dataset (Kaggle)

Alongside the dashboard, this repo builds and publishes a clean public dataset:
**Northern Territory Crime Statistics — 2008–2026**.

- **What it is:** every month of recorded crime in the Northern Territory from
  **January 2008 to August 2026** — 224 consecutive months, no gaps. 56,848 rows,
  572,532 recorded offences, 27 locations.
- **Where the data comes from:** the Northern Territory Government's official
  open data portal, <https://data.nt.gov.au/group/law>. Offences are recorded by
  NT Police and published by the Department of the Attorney-General and Justice.
- **Licence:** the source is published under a Creative Commons Attribution
  (CC BY) licence — the portal does not state a version. The dataset built here
  is released under **CC BY 4.0**.

Files published: `kaggle/nt_crime_master.csv`, `kaggle/DATA_DICTIONARY.md`,
`kaggle/METHODOLOGY.md`.

### How the history was put together

The portal is harder to use than it looks. Every monthly file is **cumulative** —
it contains the whole history, not just that month — so stacking the downloads
counts old months many times over. Filenames are also unreliable: they don't sort
chronologically, and the file named "November 2023" contained no November 2023
data.

The dataset is therefore assembled from exactly three official extracts, chosen
by reading their contents rather than their names:

| Period | Source |
|---|---|
| 2008-01 → 2013-12 | March 2024 historical extract |
| 2014-01 → 2023-11 | April 2024 historical extract |
| 2023-12 → present | the newest current-era release |

The two historical extracts are **pinned** and are never replaced automatically.

### Three things that matter when using it

**The recording system changed between November and December 2023.** NT Police
moved from PROMIS to SerPro. The NT Government advises that data from December
2023 onward should not be compared directly with earlier data. Every row carries
a `Data era` tag so the two periods can be analysed separately.

**November 2023 is marked specially.** It is the cutover month — the last month
recorded under the old system, and the month the new one was rolled out. It was
missing from the original November 2023 release and only appeared later as a
supplementary correction. It is flagged provisional because the government
advises data for this period may be incomplete or subject to later revision.

**Population is limited on purpose.** The column holds ABS 2021 Census figures
and is filled in only from December 2023 onward, for 9 of the 27 locations.
Applying one 2021 number to 2008 would be wrong, so historical rows are blank.
Blank means unknown, not zero — don't compute historical per-capita rates from it.

### How automatic updates work

A GitHub Action (`.github/workflows/update-data.yml`) runs daily and can also be
triggered by hand:

1. Queries the portal's CKAN API for every crime-statistics release.
2. **Downloads and inspects candidates** — decisions come from the `Year` and
   `Month number` columns inside each file, never from its filename.
3. If the newest release contains a month we don't have, rebuilds the master
   dataset — history from the pinned extracts, the current era from the new file.
4. Runs the full validation suite.
5. Only if every critical check passes: commits, pushes, and publishes a new
   version of the Kaggle dataset.

If anything looks wrong — a month disappears, totals move too far, an unknown
offence category appears, the file can't be parsed — **the pipeline stops and
publishes nothing**, and writes `kaggle/UPDATE_REPORT.md` explaining why. If the
government publishes something that would change the pinned historical period,
that is reported for review and never applied automatically.

Run it yourself:

```bash
python -m pipeline.update --check     # is there anything new?
python -m pipeline.update --dry-run   # build and validate, write nothing
python tests/test_safety.py           # prove the safety checks still fire
```

### One-time setup

Two things need your own credentials and cannot be automated: the GitHub
`workflow` scope, and a Kaggle API token. This script does both, then publishes
the dataset and stores the secrets the workflow needs:

```bash
./scripts/finish_setup.sh
```

Your Kaggle key is piped straight from `~/.kaggle/kaggle.json` into
`gh secret set` — it is never printed, logged, or written into the repository.

## Why this exists

The original version was a Power BI report. It looked fine, but it had two limits: it couldn't be version-controlled or run on a Mac, and — more importantly — it answered the data's questions, not a decision-maker's. This rebuild fixes both. It runs anywhere from a single Python codebase, and it leads with the finding a director needs in the first five seconds.

## The headline finding

Ranked by **raw offence counts**, Darwin looks like the Territory's crime centre — it has the largest population, so it has the most offences. But ranked **per 1,000 residents**, the picture inverts: **Tennant Creek's rate is roughly 5× Darwin's across 2008–2026, and about 7× since December 2023.** Resourcing decisions made on raw volume alone systematically under-serve smaller remote communities. The dashboard opens in per-capita mode for exactly this reason, and a plain-English summary states it up front.

## What's on the dashboard

- **Click any place to focus on it** — click a bar, a map bubble or a heatmap row (or pick from *Focus on a location*) and the headline figures, takeaways, trend and seasonality switch to that place, while the other charts highlight it. Click it again to return to the whole Territory.
- **Replay the years** — press play to animate every place's rate year by year from 2008, with the recording system named on each frame.
- **Key takeaways** — a plain-English summary that updates with every filter, including a profile of the focused place.
- **Download data** — the current selection as a CSV; **Reset** clears every filter.

- **Monthly trend, 2008 onward** — every month in the dataset, with a 12-month average that restarts after the November 2023 recording-system change so it never blends the two systems. The change is marked on the chart and November 2023 is flagged provisional.
- **Decision row** — a ranked "where crime hits hardest" chart (per-capita by default) beside a tile map of crime intensity across the Territory.
- **Year-on-year change by region** — in the same format the NT Government uses to report progress.
- **Alcohol & DV involvement by location** — the two factors tied to current NT alcohol-supply policy.
- **Seasonality** — monthly offences indexed to each region's own average, so the seasonal *pattern* is visible rather than washed out by a flat all-region total.
- **Crime fingerprint** — a heatmap of each location's offences by type, revealing distinct "fingerprints" (Darwin/Palmerston are theft-led; remote areas are assault-led).
- A **period slider** (any month range from January 2008 to the latest release) with one-click presets for the whole series, the period before the change, and the period after it; plus filters for location type, crime type, and month. Every chart cross-filters.

## Geographic granularity

The source data lumps ~20 distinct localities under a single "NT Balance" label. That hides the Territory's remote communities — exactly the geography NT policy focuses on. The data prep rebuilds a true `Location` field (town name where the region is a town; Statistical Area 2 name where it is "NT Balance"), expanding 8 regions into **27 locations** so remote areas like East Arnhem, Thamarrurr and West Arnhem are visible in their own right.

## Analytical decisions worth knowing

These are the judgment calls behind the numbers:

- **The whole series, with the November 2023 break handled rather than hidden.** NT Police moved from PROMIS to SerPro between November and December 2023, and the NT Government advises against comparing the two periods directly. The dashboard keeps both: the trend chart marks the change and computes its rolling average separately on each side, the period presets select one recording system in a click, and any year-on-year figure whose comparison spans the change is greyed out and labelled indicative. The break month is read from the dataset's `Data era` tag, not hard-coded.
- **Like-for-like year-on-year.** Year-on-year compares the latest year in the selected period with the same months of the year before, so a partial year (e.g. January–August 2026) is compared fairly instead of being dropped.
- **Consistent categories.** Charts group offences by the dataset's nine harmonised `Crime Type` labels, the one offence field with the same values in both recording eras.
- **Per-capita rates are indicative, and only shown where defensible.** Rates are annualised (per 1,000 residents a year), so they mean the same thing for one month or eighteen years. They use 2021 ABS census populations for the seven towns plus the SA2 localities with confidently sourced figures, applied to every period, so rates for years far from 2021 are more approximate. Locations without a reliable population show **counts only** — no invented rate. Small-population areas have volatile rates and are labelled approximate.
- **"NT Balance" coordinates are approximate.** SA2 map points are indicative centroids, not official ABS centroids.

## Where the dashboard's data comes from

The dashboard reads the published Kaggle dataset, so its numbers always match
it. When the Hugging Face Space builds, `prepare_data.py` downloads the dataset
from Kaggle (it is public, so no credentials are needed) and checks its MD5
against `data_release.json`, the fingerprint the deploy workflow ships with the
code. If Kaggle cannot be reached, it uses the byte-identical copy committed to
GitHub for the same release. The footer of the dashboard says which source was
used and which Kaggle version it is.

It uses every month in the dataset, January 2008 onward, from both recording
eras. Each row keeps its `Data era` tag, which the dashboard uses to mark the
November 2023 recording-system change and to label any comparison that spans
it as indicative.

Nothing needs uploading by hand. When the NT publishes a new month, the update
workflow adds it to the dataset, publishes it to Kaggle, waits until Kaggle is
serving it, and then redeploys the dashboard. To re-sync the dashboard on
demand, run the *Update NT crime data* workflow with **redeploy** ticked.

## Tech

- **Python / pandas** — cleaning and aggregation.
- **Plotly Dash** — single-callback cross-filtering; shared figure template for consistent styling.
- **Carto tiles** — interactive map, no API token required.
- **Motion** — Plotly transitions and animation frames, plus `assets/style.css` and `assets/motion.js` for card and KPI animations. All motion is switched off for visitors who set *reduce motion* on their device.
- **Colour** — chart series colours are checked for colour-blind separation, chroma and contrast on white.
- Data is prepared once into a Parquet file, then served by the app.

## Run it locally

```bash
pip install -r requirements.txt
python prepare_data.py   # downloads from Kaggle -> crime_clean.parquet
# or, offline:  python prepare_data.py --local
python app.py            # open http://127.0.0.1:8050
```

## Project structure

```
prepare_data.py       # downloads the Kaggle dataset, verifies it, builds the dashboard data
app.py                # the Dash application
data/                 # official source extracts, maintained by the update pipeline
requirements.txt
crime_clean.parquet   # generated by prepare_data.py
assets/               # styles, motion script, icons, NT illustration, favicon
```

## Data source

Recorded-offence data published by NT Police via the Northern Territory Government Open Data Portal. This is an independent analysis and is not affiliated with or endorsed by the NT Government or NT Police.
