# Methodology — NT Crime Master Dataset

How `nt_crime_master.csv` was built from Northern Territory Government open data,
and why each decision was made.

---

## Attribution

> Source: Northern Territory Government, Department of the Attorney-General and
> Justice — NT Crime Statistics, published on the NTG Open Data Portal
> (data.nt.gov.au). Offences recorded by NT Police.

All data is published by the Northern Territory Government. This dataset
reorganises it; it does not add to or estimate it.

## Licence

Source data is published by the Northern Territory Government under a Creative
Commons Attribution (CC BY) licence. The NT Open Data Portal does not specify a
licence version.

This derived master dataset is released under **Creative Commons Attribution 4.0
International (CC BY 4.0)**.

---

## The problem with the raw files

The NT Government publishes a new crime statistics file every month. Each file
is **cumulative** — it contains the whole history, not just the new month. A
January file and a June file overlap almost entirely.

Naively stacking the monthly downloads therefore counts early months once per
file. Doing that across six files inflates the total roughly 5.5×, and unevenly:
the oldest months are counted most, which artificially tilts long-run trends
downward. **This dataset uses one file per period, never a stack.**

There is a second trap: filenames don't sort chronologically. Alphabetically,
`may` sorts after `june`. Files here were selected by the `As At` extraction date
recorded inside each file, not by filename.

---

## Which files were used, and why

Three official extracts, covering three non-overlapping spans:

| Period | Extract | Why this one |
|---|---|---|
| 2008-01 → 2013-12 | March 2024 | The only extract carrying both pre-2014 history and November 2023. |
| 2014-01 → 2023-11 | April 2024 | Newer revisions than the March file. Its history is truncated at 2014-01, which is why March covers the earlier years. |
| 2023-12 → 2026-06 | June 2026 | The most recent release of the post-transition series. |

### Why two historical extracts instead of one

November 2023 was published twice as a supplementary correction, in March and
April 2024. The two were compared record by record over their shared span
(2014-01 → 2023-11):

- Identical column names, offence categories (11), offence types (23), regions
  (7), SA2 areas (21), and alcohol/DV coding.
- Only **153 of 29,695** dimension combinations differ (0.52%).
- Net change: **+70 offences (+0.023%)**.
- Changes cluster in recent months (2023 accounts for 71 of them); 2014–2017
  nets to exactly zero.

That is the signature of routine revision, not a methodology change — so the
newer April file is preferred wherever it exists.

**One known consequence (limitation):** the April extract includes a small,
systematic correction that reassigns some offences from *West Arnhem* to *Elsey*
(23 offences across 2014–2023). Because the April file starts at 2014, the
2008–2013 segment keeps the pre-correction geography. The estimated effect is
about 14 offences out of 171,707 in that segment — roughly **0.008%**. It cannot
be resolved: no published file contains both the correction and pre-2014 history.

---

## Two documented changes in the series

The NT Government's own guidance states there is *"a break in the crime
statistics time series following November 2023, due to the implementation of the
SerPro data system"*, and that statistics from December 2023 onward should not be
compared directly with earlier statistics.

**The recording-system break occurs between November 2023 and December 2023.**
November 2023 is the last month on the old side of that break; December 2023 is
the first month on the new side.

| Month | What happened | Flag |
|---|---|---|
| **November 2023** | Final month recorded under PROMIS. SerPro was rolled out during this month, making it the cutover month. | `is_break_month = True` |
| **April 2025** | The month NT adopted the 2023 edition of ANZSOC for its published reporting. | `is_break_month = True` |

### About April 2025

ANZSOC was applied **retrospectively** to the whole current-era extract, so the
offence categories in this dataset are identical either side of April 2025 —
there is no discontinuity in the underlying counts here. The flag exists because
the NT metadata advises caution when comparing against NT publications produced
before May 2025.

### About November 2023 specifically

November 2023 **is present** in this dataset — 278 rows, 3,345 offences, taken
from the April 2024 extract.

It is flagged as provisional. The NT Government advises that following the
SerPro transition, data entry happens later in the investigation process, so
monthly figures take longer to settle and **may be incomplete or subject to
later revision**. November 2023 was also the month most revised between the
March and April extracts, which is consistent with data still settling.

Treat the November 2023 figure with caution, and don't read the month-to-month
movement around the transition as a straightforward change in crime levels.

---

## Classification: both kept, nothing forced

The historical and current eras use genuinely different offence classifications
with **no shared values at all** — 11 categories/23 types historically versus
9 categories/23 types currently.

Rather than pretend they match, this dataset:

1. **Keeps both government classifications verbatim** in `Offence category` and
   `Offence type`, tagged by `Data era`.
2. **Adds a simplified `Crime Type`** with nine labels that both eras map onto.
   All 567,438 offences map successfully; nothing falls into an "other" bucket.

`Crime Type` lets users group both eras using one consistent set of labels. It
does **not** make the two eras directly comparable — the recording system changed
between November and December 2023, and the NT Government advises against direct
comparison across that boundary. Analyse the eras separately, or treat cross-era
trends as indicative only.

The finer `Offence type` level is deliberately *not* bridged — the mapping there
is many-to-many and lossy (one historical `Assault` splits into three current
categories), so forcing it would invent precision that isn't there.

---

## Location

`Reporting Region` lumps around 20 distinct localities under a single
`NT Balance` label, which hides exactly the remote communities that NT policy
focuses on. The `Location` field resolves this: the town name where the region
is a town, the SA2 name where the region is `NT Balance`.

This yields **27 locations**, and produces an identical set of names in both the
historical and current eras — so it is safe to group by `Location` across the
whole time series.

The `Unknown` reporting region occurs only in the current era, covering 7 rows
and 8 offences.

---

## Population

The population column holds ABS 2021 Census usual-resident counts and is
populated **only from December 2023 onward**. It is blank for all historical
rows by design: applying one 2021 figure to 2008 would be an anachronism, and
computing historical per-capita rates from it would produce misleading numbers.

Within the current era it is populated for 9 of the 27 locations; the other 18
do not have a confidently sourced figure. Counts are still shown for those
places — only the rate is withheld. **Blank means unknown, not zero.**

No population value was estimated, interpolated, or back-cast.

---

## What was verified

- 222 of 222 months present (2008-01 → 2026-06), **no gaps, nothing interpolated**.
- No month drawn from more than one extract; no duplicate rows or dimension keys.
- Each segment reconciles exactly against its source file — 0 records lost,
  0 invented, 0 counts altered.
- The December 2023 → June 2026 portion was validated row-for-row against an
  independently prepared extract of the same source file.
- Every original source file was left byte-for-byte unchanged (checksums
  verified before and after the build).

---

## Limitations

1. **The recording system changed between November 2023 and December 2023.**
   The NT Government advises that data from December 2023 onward should not be
   compared directly with data prior to December 2023.
2. **Alcohol involvement is not comparable across the full period.** Historical
   "unknown" values were recoded to `No` during migration; roughly 27% of assault
   offences previously carried "unknown".
3. **November 2023 is provisional** and may be revised by the NT Government.
4. **A small geography correction applies only from 2014 onward** — the West
   Arnhem / Elsey reassignment described above, affecting roughly 0.008% of the
   2008–2013 segment.
5. **These are recorded offences, not victims, offenders, or court outcomes**,
   and they reflect crimes reported to police — not all crime that occurred.
6. **NT crime figures are not comparable with other Australian jurisdictions**,
   as offence definitions are not standardised nationally.
7. Offences show strong seasonal patterns. The NT Government recommends
   comparing the same month across different years, and using a 12-month rolling
   average for trends.
