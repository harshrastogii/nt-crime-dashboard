# Data Dictionary — NT Crime Master Dataset

**File:** `nt_crime_master.csv`
**Coverage:** January 2008 → June 2026 (222 months, no gaps)
**Rows:** 56,217
**Total offences:** 567,438

Each row is a count of offences recorded by NT Police for one combination of
month, offence type, location, and (for assault offences) alcohol and domestic
violence involvement. **A row is not a single crime** — read `Number of offences`
for the count.

---

## Attribution

> Source: Northern Territory Government, Department of the Attorney-General and
> Justice — NT Crime Statistics, published on the NTG Open Data Portal
> (data.nt.gov.au). Offences recorded by NT Police.

## Licence

Source data is published by the Northern Territory Government under a Creative
Commons Attribution (CC BY) licence. The NT Open Data Portal does not specify a
licence version.

This derived master dataset is released under **Creative Commons Attribution 4.0
International (CC BY 4.0)**.

---

## Columns

| Column | Type | Description |
|---|---|---|
| `Date` | text `YYYY-MM` | The month the offence was reported to NT Police. |
| `Year` | integer | Year, 2008–2026. Always agrees with `Date`. |
| `Month number` | integer | 1 = January … 12 = December. |
| `Crime Type` | text | Simplified label with nine values, available in both eras. **Read the note below before using it across eras.** |
| `Offence category` | text | The government's own high-level classification, kept exactly as published. **The wording differs between the two eras** — see `Data era`. |
| `Offence type` | text | The government's detailed classification, kept exactly as published. **Also differs between eras.** |
| `Reporting Region` | text | One of 7 regions, plus `Unknown`. `NT Balance` is a catch-all covering everywhere outside the main towns. See the note on `Unknown` below. |
| `Location` | text | **The useful geography field.** The town name where the region is a town; the Statistical Area 2 (SA2) name where the region is `NT Balance`. 27 distinct values. |
| `Location Type` | text | `Urban` (Darwin, Palmerston), `Regional` (Alice Springs, Katherine, Tennant Creek), or `Remote` (everywhere else). |
| `Population (ABS 2021 reference)` | integer / blank | **A single 2021 Census figure, not a population time series.** See the warning below. |
| `Alcohol involvement` | text | `Yes`, `No`, or `-`. Recorded for assault offences only; `-` means not applicable. **See the warning below.** |
| `DV involvement` | text | `Yes`, `No`, or `-`. Domestic violence involvement, assault offences only. |
| `Data era` | text | `Historical / PROMIS` (2008-01 → 2023-11) or `Current / SerPro` (2023-12 → 2026-06). |
| `Source extract` | text | Which official government file this row came from. Three values — see below. |
| `is_break_month` | boolean | `True` on the two months where something documented changed: 2023-11 and 2025-04. **The two events are different in kind** — see below. |
| `Break note` | text | Blank except on the two break months, where it explains what changed. |
| `Number of offences` | integer | The count. Always 1 or more; never zero, negative, or missing. |

---

## `Crime Type` values

Nine simplified labels, mapped from the government categories in both eras:

`Homicide` · `Assault & Violence` · `Sexual Offences` · `Harassment & Threats` ·
`Robbery & Extortion` · `Residential B&E` · `Commercial B&E` · `General Theft` ·
`Property Damage`

Every record in both eras maps to one of these — nothing falls into an "other"
bucket.

**`Crime Type` is the only offence field that lets users group both eras using
one consistent set of labels. It does NOT make the two eras directly
comparable.** The NT Government advises that data from December 2023 onward
should not be compared directly with data prior to December 2023, because the
police recording system changed. Analyse the eras separately, or treat cross-era
trends as indicative only.

---

## `Source extract` values

| Value | Covers | Official file |
|---|---|---|
| `March 2024 historical extract` | 2008-01 → 2013-12 | `nt_crime_statistics_nov_2023_updated_03_24.csv` |
| `April 2024 historical extract` | 2014-01 → 2023-11 | `nt_crime_statistics_nov_2023_updated_04_24.csv` |
| `June 2026 current extract` | 2023-12 → 2026-06 | `nt_crime_statistics_june_2026.csv` |

No month is supplied by more than one extract.

---

## The two `is_break_month` events are not the same kind of event

**November 2023 is the final month before the recording-system break; April 2025
is the first month of the new published ANZSOC classification. Therefore, the
same boolean flag is used for two different documented events.**

| Month | What it marks | What you will see in the data |
|---|---|---|
| **2023-11** | Last month recorded under the old PROMIS system. SerPro was rolled out during this month. Flagged provisional. | `Offence category` and `Offence type` values change completely at the following month (2023-12). |
| **2025-04** | The month NT adopted the 2023 ANZSOC classification for its reporting. | **No change in this dataset.** ANZSOC was applied retrospectively across the whole current era, so categories are identical either side of this month. |

If you filter on `is_break_month == True`, read `Break note` to see which event
each month represents.

---

## Notes on specific columns

### `Reporting Region` — `Unknown`

The value `Unknown` occurs **only in the current era**, and covers **7 rows /
8 offences** in total. It does not appear anywhere in the historical data.

### `Population (ABS 2021 reference)`

**Population is blank for every historical row. Within the current era it is
populated for 9 of the 27 locations; the other 18 locations do not have a
confidently sourced figure in the current dataset.**

The column holds ABS 2021 Census usual-resident counts. It is deliberately blank
for all historical rows, because applying a 2021 figure to 2008 would be wrong.
**Blank means unknown, not zero.**

**Do not compute per-capita crime rates for the historical period from this
column.** For rates over time you need ABS Estimated Resident Population by
year, which is not included here.

---

## Two things to read before you analyse this data

### 1. Don't compare offence categories across the December 2023 boundary

The NT Government changed its police recording system (PROMIS → SerPro) between
November and December 2023. `Offence category` and `Offence type` use
**completely different wording** in the two eras — there is no shared value
between them.

Use `Offence category` and `Offence type` only within a single `Data era`. Use
`Crime Type` to group both eras under one set of labels, keeping in mind the
comparability limit described above.

### 2. `Alcohol involvement` is not comparable across the full period

In the historical data, "alcohol involvement unknown" was a valid third answer.
When the data was migrated, **all unknown values were recoded to `No`**. The NT
metadata notes that roughly 27% of assault offences had alcohol involvement
recorded as unknown beforehand, and that a proportion of those were likely
alcohol-related.

An "alcohol-related assault" trend line spanning 2008–2026 will partly measure
this coding change rather than real-world change. The same caution applies in
lesser degree to `DV involvement`.
