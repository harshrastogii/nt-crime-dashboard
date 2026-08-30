"""
update.py — the orchestrator.

    python -m pipeline.update --check          discover only, change nothing
    python -m pipeline.update --dry-run        build + validate into a temp dir
    python -m pipeline.update                  build, validate, write if safe
    python -m pipeline.update --simulate FILE  pretend FILE is the newest
                                               release (used by the test suite)

Exit codes:  0 = up to date or updated successfully
             1 = STOP, a safety check failed (never publishes)
             2 = the portal or a source file could not be understood
             3 = an update is available but this run was read-only

Nothing here writes to kaggle/ unless every critical validation passes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

import pandas as pd

from . import build, inspect_csv, manifest, portal, validate

BASE = manifest.BASE
MASTER = os.path.join(BASE, "kaggle", "nt_crime_master.csv")
REPORT = os.path.join(BASE, "kaggle", "UPDATE_REPORT.md")
DATA_DIR = os.path.join(BASE, "data")
SERPRO_START = pd.Period("2023-12", freq="M")


def log(msg): print(msg, flush=True)


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------
def discover_current(cands) -> tuple[dict, list]:
    """Find the candidate that best serves the CURRENT (SerPro) period.

    We inspect contents, never filenames. The winner is the SerPro-era file
    that reaches the latest crime month; ties break on the later 'As At'.
    """
    notes, viable = [], []
    for c in cands:
        # Only fetch things plausibly in the current era. Every SerPro release
        # so far is a page whose title is a month from 2024 onward, but we do
        # not rely on that - we fetch and inspect. To keep the run cheap we
        # skip pages that are clearly the old historical series.
        try:
            blob, md5 = portal.fetch_bytes(c.url)
            df, rep = inspect_csv.inspect_source(blob)
        except Exception as exc:
            notes.append(f"could not read {c.resource_name or c.url}: {exc}")
            continue
        if rep.era != "Current / SerPro":
            continue
        if not rep.ok:
            notes.append(f"SKIP {c.dataset_title}: {rep.problems}")
            continue
        viable.append({"cand": c, "report": rep, "md5": md5, "blob": blob})

    if not viable:
        return None, notes
    viable.sort(key=lambda v: (v["report"].last_month, v["report"].as_at))
    return viable[-1], notes


def check_history(cands, man) -> list[dict]:
    """PART 3 safety feature. Detect whether the government has published
    anything that would change the pinned historical period. We never act on
    it - we report it."""
    flags = []
    pinned_urls = {h["resource_url"] for h in man["historical"]}
    for h in man["historical"]:
        if not h.get("resource_url"):
            continue
        try:
            blob, md5 = portal.fetch_bytes(h["resource_url"])
        except Exception as exc:
            flags.append({"kind": "unreachable", "file": h["file"], "detail": str(exc)})
            continue
        if h.get("md5") and md5 != h["md5"]:
            flags.append({"kind": "pinned_source_changed_upstream",
                          "file": h["file"], "url": h["resource_url"],
                          "expected_md5": h["md5"], "found_md5": md5})
    # A brand-new historical-era release that we have not already evaluated.
    #
    # Two-stage, so this does not cry wolf. Stage 1 narrows cheaply by name and
    # dataset title; stage 2 DOWNLOADS the candidate and only raises a flag if
    # the contents really are PROMIS-era data. A detector that fires every run
    # on files we already know about would train the reader to ignore it.
    known = pinned_urls | set(man.get("known_historical_urls", []))
    for c in cands:
        if c.url in known:
            continue
        base = os.path.basename(c.url).lower()
        title = c.dataset_title.lower()
        looks_historical = (
            "nov_2023" in base
            or any(str(y) in title for y in range(2008, 2024)))
        if not looks_historical:
            continue
        try:
            blob, md5 = portal.fetch_bytes(c.url)
            _, rep = inspect_csv.inspect_source(blob)
        except Exception as exc:
            flags.append({"kind": "unreadable_candidate",
                          "dataset": c.dataset_title, "url": c.url,
                          "detail": str(exc)})
            continue
        if rep.era != "Historical / PROMIS":
            continue  # not actually historical data - ignore
        flags.append({"kind": "unevaluated_historical_release",
                      "dataset": c.dataset_title,
                      "resource": c.resource_name,
                      "url": c.url,
                      "published": c.created,
                      "covers": f"{rep.first_month}..{rep.last_month}",
                      "months": rep.months,
                      "rows": rep.rows,
                      "offences": rep.offences,
                      "md5": md5})
    return flags


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def write_report(path, *, status, res, chosen, hist_flags, portal_notes,
                 licence, simulated=False):
    f = res.facts
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [f"# NT Crime Data — Update Report\n",
         f"_Generated {now}_" + ("  \n**SIMULATED RUN — nothing published**" if simulated else "") + "\n",
         f"## Result: **{status}**\n"]

    L.append("| | Previous | New |")
    L.append("|---|---|---|")
    L.append(f"| Latest month | {f.get('prev_last_month','—')} | {f.get('last_month','—')} |")
    L.append(f"| Rows | {f.get('prev_rows','—'):,} | {f.get('rows',0):,} |" if isinstance(f.get('prev_rows'), int)
             else f"| Rows | — | {f.get('rows',0):,} |")
    L.append(f"| Total offences | {f.get('prev_offences','—'):,} | {f.get('offences',0):,} |" if isinstance(f.get('prev_offences'), int)
             else f"| Total offences | — | {f.get('offences',0):,} |")
    L.append(f"| Months | — | {f.get('months',0)} |")
    L.append(f"| Locations | — | {f.get('locations',0)} |\n")

    added = f.get("new_months", [])
    L.append(f"**New months added:** {', '.join(added) if added else 'none'}\n")

    rev = f.get("revised_months", [])
    if rev:
        L.append(f"**Existing months revised:** {len(rev)}\n")
        L.append("| Month | Before | After | Change |")
        L.append("|---|---|---|---|")
        for x in rev[:25]:
            L.append(f"| {x['month']} | {x['before']:,} | {x['after']:,} | {x['delta']:+,} ({x['pct']:+.2f}%) |")
        if len(rev) > 25:
            L.append(f"| … | | | {len(rev)-25} more |")
        L.append("")
    else:
        L.append("**Existing months revised:** none\n")

    if "historical_total_change_pct" in f:
        L.append(f"**Pinned historical total change:** {f['historical_total_change_pct']:+.4f}% "
                 f"(must stay within ±{validate.HISTORY_TOTAL_PCT}%)\n")

    L.append("## Source used\n")
    if chosen:
        c, rep = chosen["cand"], chosen["report"]
        L.append(f"- **Dataset:** {c.dataset_title}")
        L.append(f"- **Resource:** `{os.path.basename(c.url)}`")
        L.append(f"- **Extracted (As At):** {rep.as_at}")
        L.append(f"- **Shape detected:** `{rep.shape}` · era `{rep.era}`")
        L.append(f"- **Covers:** {rep.first_month} → {rep.last_month} ({rep.months} months)")
        L.append(f"- **md5:** `{chosen['md5']}`")
        L.append(f"- **Portal licence:** {licence}\n")
    else:
        L.append("- No new current-era source was selected this run.\n")

    L.append("## Validation\n")
    if res.critical:
        L.append("**CRITICAL — publication blocked:**\n")
        for m in res.critical:
            L.append(f"- {m}")
        L.append("")
    else:
        L.append("All critical checks passed.\n")
    if res.warnings:
        L.append("Warnings (do not block publication):\n")
        for m in res.warnings:
            L.append(f"- {m}")
        L.append("")

    L.append("## Historical-revision watch\n")
    if hist_flags:
        L.append("**The government may have published something affecting the "
                 "pinned historical period. This is NOT applied automatically.**\n")
        for fl in hist_flags:
            L.append(f"- `{fl['kind']}` — " + ", ".join(
                f"{k}: {v}" for k, v in fl.items() if k != "kind"))
        L.append("")
    else:
        L.append("No change detected to the pinned historical sources.\n")

    if portal_notes:
        L.append("## Portal notes\n")
        for n in portal_notes[:20]:
            L.append(f"- {n}")
        L.append("")

    with open(path, "w") as fh:
        fh.write("\n".join(L) + "\n")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="discover only")
    ap.add_argument("--dry-run", action="store_true", help="build+validate, write nothing")
    ap.add_argument("--simulate", metavar="CSV", help="treat this local CSV as the newest release")
    ap.add_argument("--skip-history-check", action="store_true",
                    help="skip re-fetching pinned historical sources (faster)")
    args = ap.parse_args(argv)

    man = manifest.load()

    pin_problems = manifest.verify_pinned(man)
    if pin_problems:
        log("STOP: pinned historical sources failed verification:")
        for p in pin_problems:
            log(f"  - {p}")
        return 1

    old = pd.read_csv(MASTER, low_memory=False) if os.path.isfile(MASTER) else None
    prev_last = max(old["Date"]) if old is not None else None
    log(f"Current master: {'none' if old is None else f'{len(old):,} rows, latest {prev_last}'}")

    chosen, portal_notes, hist_flags, licence = None, [], [], "n/a"

    if args.simulate:
        blob = open(args.simulate, "rb").read()
        df, rep = inspect_csv.inspect_source(blob)
        if not rep.ok:
            log(f"STOP: simulated source is not usable: {rep.problems}")
            return 2
        import hashlib
        fake = portal.Candidate(
            dataset_title=f"SIMULATED ({os.path.basename(args.simulate)})",
            dataset_name="simulated", resource_name=os.path.basename(args.simulate),
            url=args.simulate, created="", last_modified="",
            license_id="cc-by", license_title="Creative Commons Attribution")
        chosen = {"cand": fake, "report": rep, "md5": hashlib.md5(blob).hexdigest(),
                  "blob": blob}
        licence = "cc-by | Creative Commons Attribution (simulated)"
    else:
        log("Querying the NT Open Data Portal (CKAN)…")
        try:
            cands = portal.list_candidates()
        except portal.PortalError as exc:
            log(f"STOP: {exc}")
            return 2
        log(f"  {len(cands)} CSV resources visible")

        lic = portal.licence_summary(cands)
        licence = max(lic, key=lic.get)
        expected = man["expected_licence"]
        if expected["license_id"] not in licence:
            log(f"STOP: portal licence changed - expected {expected}, saw {lic}")
            return 1

        if not args.skip_history_check:
            log("Checking whether the pinned historical period is affected…")
            hist_flags = check_history(cands, man)
            if hist_flags:
                log(f"  {len(hist_flags)} historical flag(s) raised — reported, not applied")

        log("Inspecting candidates for the current period (contents, not names)…")
        chosen, portal_notes = discover_current(cands)
        if chosen is None:
            log("STOP: no usable current-era source found on the portal")
            return 2

    rep = chosen["report"]
    log(f"Selected: {chosen['cand'].dataset_title}")
    log(f"  shape={rep.shape} era={rep.era} covers {rep.first_month}..{rep.last_month} "
        f"({rep.months} months) as_at={rep.as_at}")

    if rep.shape not in ("cumulative_current", "single_month"):
        log(f"STOP: unexpected shape for a current-era release: {rep.shape}")
        return 1
    if rep.shape == "cumulative_current" and str(SERPRO_START) != rep.first_month:
        log(f"STOP: cumulative current file should start {SERPRO_START}, starts {rep.first_month}")
        return 1

    if old is not None and rep.last_month <= prev_last and not args.simulate:
        log(f"Up to date: portal's newest month is {rep.last_month}, master already has {prev_last}")
        return 0

    if args.check:
        log(f"UPDATE AVAILABLE: {prev_last} -> {rep.last_month} (read-only run)")
        return 3

    # ---- materialise the current source, build into a temp location ----
    tmpdir = tempfile.mkdtemp(prefix="ntcrime_")
    try:
        if rep.shape == "single_month":
            log("STOP: a single-month release cannot rebuild the cumulative "
                "current segment on its own. Needs review.")
            return 1

        cur_path = os.path.join(tmpdir, "current_source.csv")
        with open(cur_path, "wb") as fh:
            fh.write(chosen["blob"])

        label = f"{rep.last_month} current extract (As At {rep.as_at})"
        out_path = os.path.join(tmpdir, "nt_crime_master.csv")
        new = build.build(
            current_file=cur_path,
            hist_early=os.path.join(BASE, man["historical"][0]["file"]),
            hist_late=os.path.join(BASE, man["historical"][1]["file"]),
            current_label=label,
            out_path=out_path)
        log(f"Built candidate master: {len(new):,} rows, "
            f"{new['Number of offences'].sum():,} offences, {new['Date'].nunique()} months")

        # 'Source extract' label changes each month by design; compare the old
        # dataset with its own labels intact but ignore the label when matching
        # keys (validate.KEY[:-1] already excludes it).
        res = validate.validate(new, old)

        status = "PASS — safe to publish" if res.passed else "STOP — publication blocked"
        for m in res.critical:
            log(f"  CRITICAL: {m}")
        for m in res.warnings:
            log(f"  warning: {m}")

        # a simulated or dry run must never touch the published report
        read_only = args.dry_run or bool(args.simulate)
        report_path = os.path.join(tmpdir, "UPDATE_REPORT.md") if read_only else REPORT
        write_report(report_path, status=status, res=res, chosen=chosen,
                     hist_flags=hist_flags, portal_notes=portal_notes,
                     licence=licence, simulated=bool(args.simulate))

        if not res.passed:
            log(f"STOP: validation failed. Report: {report_path}")
            if read_only:
                log(open(report_path).read())
            return 1

        if args.dry_run or args.simulate:
            log(f"DRY RUN OK — nothing written to kaggle/. Report at {report_path}")
            log(f"  would add months: {res.facts.get('new_months')}")
            return 0

        # ---- commit to the working tree ----
        dest_src = os.path.join(DATA_DIR, os.path.basename(chosen["cand"].url))
        shutil.copyfile(cur_path, dest_src)
        shutil.copyfile(out_path, MASTER)
        man["current"].update({
            "file": os.path.relpath(dest_src, BASE),
            "covers_to": rep.last_month,
            "dataset_title": chosen["cand"].dataset_title,
            "resource_url": chosen["cand"].url,
            "as_at": rep.as_at,
            "md5": chosen["md5"],
        })
        man["last_run"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        manifest.refresh_hashes(man)
        manifest.save(man)
        log(f"UPDATED through {rep.last_month}. Report: {REPORT}")
        # emit the new latest month for the workflow's commit message
        gh_out = os.environ.get("GITHUB_OUTPUT")
        if gh_out:
            month_name = pd.Period(rep.last_month, freq="M").strftime("%B %Y")
            with open(gh_out, "a") as fh:
                fh.write(f"updated=true\nlatest_month={rep.last_month}\n"
                         f"latest_month_name={month_name}\n")
        return 0
    finally:
        if not (args.dry_run or args.simulate):
            shutil.rmtree(tmpdir, ignore_errors=True)
        else:
            log(f"(temp artefacts kept at {tmpdir})")


if __name__ == "__main__":
    sys.exit(main())
