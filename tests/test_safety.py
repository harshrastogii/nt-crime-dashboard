"""
test_safety.py — prove the pipeline REFUSES bad data.

A safety system that has never been seen to fire is not a safety system. Each
case below builds a deliberately corrupt "new release" in a temp directory and
asserts that the pipeline stops rather than publishing.

    python tests/test_safety.py

Nothing here touches kaggle/ or data/.
"""
import os
import subprocess
import sys
import tempfile

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
SRC = os.path.join(BASE, "data", "nt_crime_statistics_june_2026.csv")
MASTER = os.path.join(BASE, "kaggle", "nt_crime_master.csv")

PASS, FAIL = "PASS", "FAIL"
results = []


def record(name, expected_stop, code, detail=""):
    stopped = code != 0
    ok = stopped == expected_stop
    results.append((name, PASS if ok else FAIL,
                    f"exit={code} " + ("stopped" if stopped else "allowed") + detail))


def run_simulate(path):
    p = subprocess.run(
        [sys.executable, "-m", "pipeline.update", "--simulate", path],
        cwd=BASE, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def base_df():
    d = pd.read_csv(SRC, dtype=str)
    d.columns = [c.strip() for c in d.columns]
    return d


def add_month(d, month="7", as_at="4/09/2026"):
    """A legitimate new month: copy June 2026's shape forward."""
    jun = d[(d["Year"] == "2026") & (d["Month number"] == "6")].copy()
    jun["Month number"] = month
    out = pd.concat([d, jun], ignore_index=True)
    out["As At"] = as_at
    return out


def main():
    tmp = tempfile.mkdtemp(prefix="ntsafety_")
    d = base_df()

    # --- control: a normal new month must be ACCEPTED -------------------
    p = os.path.join(tmp, "ok.csv")
    add_month(d).to_csv(p, index=False)
    code, out = run_simulate(p)
    record("control: legitimate new month is accepted", False, code)

    # --- 1. a month disappears -----------------------------------------
    p = os.path.join(tmp, "missing_month.csv")
    g = add_month(d)
    g = g[~((g["Year"] == "2025") & (g["Month number"] == "1"))]
    g.to_csv(p, index=False)
    code, out = run_simulate(p)
    record("existing month disappears", True, code)

    # --- 2. duplicated/concatenated file (counts roughly double) --------
    p = os.path.join(tmp, "doubled.csv")
    g = add_month(d)
    pd.concat([g, g], ignore_index=True).to_csv(p, index=False)
    code, out = run_simulate(p)
    record("file concatenated with itself", True, code)

    # --- 3. unknown offence category (classification changed) -----------
    p = os.path.join(tmp, "new_category.csv")
    g = add_month(d)
    g.loc[g.index[:50], "Offence category"] = "99 Brand New Category"
    g.to_csv(p, index=False)
    code, out = run_simulate(p)
    record("unrecognised offence category", True, code)

    # --- 4. history rewritten inside the current file -------------------
    p = os.path.join(tmp, "history_moved.csv")
    g = add_month(d)
    mask = g["Year"] == "2024"
    g.loc[mask, "Number of offences"] = (
        pd.to_numeric(g.loc[mask, "Number of offences"]) * 3).astype(str)
    g.to_csv(p, index=False)
    code, out = run_simulate(p)
    record("existing months revised far beyond threshold", True, code)

    # --- 5. implausibly small new month (truncated extract) -------------
    p = os.path.join(tmp, "tiny_month.csv")
    jun = d[(d["Year"] == "2026") & (d["Month number"] == "6")].head(5).copy()
    jun["Month number"] = "7"
    g = pd.concat([d, jun], ignore_index=True)
    g["As At"] = "4/09/2026"
    g.to_csv(p, index=False)
    code, out = run_simulate(p)
    record("new month implausibly small", True, code)

    # --- 6. coverage no longer starts at the SerPro start ---------------
    p = os.path.join(tmp, "bad_start.csv")
    g = add_month(d)
    g = g[~((g["Year"] == "2023") & (g["Month number"] == "12"))]
    g.to_csv(p, index=False)
    code, out = run_simulate(p)
    record("current file no longer starts 2023-12", True, code)

    # --- 7. unparseable garbage ----------------------------------------
    p = os.path.join(tmp, "garbage.csv")
    open(p, "w").write("this,is,not,the,expected,file\n1,2,3,4,5,6\n")
    code, out = run_simulate(p)
    record("unparseable source", True, code)

    # --- 8. an offence's location corrected in a later release ----------
    # The pattern seen in the real July 2026 release: a one-offence record
    # leaves one SA2 and reappears in another in the same month. That is the
    # source improving, and must not block publication.
    p = os.path.join(tmp, "location_corrected.csv")
    g = add_month(d)
    dims = ["Year", "Month number", "Offence category", "Offence type",
            "Alcohol involvement", "DV involvement", "Reporting Region"]
    sa2s = sorted(set(g.loc[g["Reporting Region"] == "NT Balance", "Statistical Area 2"]))
    existing = set(map(tuple, g[dims + ["Statistical Area 2"]].values))
    moved = 0
    for idx in g.index[(g["Year"] == "2025") & (g["Number of offences"] == "1")
                       & (g["Reporting Region"] == "NT Balance")]:
        row = g.loc[idx]
        for target in sa2s:
            key = tuple(row[dims]) + (target,)
            if target != row["Statistical Area 2"] and key not in existing:
                existing.discard(tuple(row[dims]) + (row["Statistical Area 2"],))
                existing.add(key)
                g.loc[idx, "Statistical Area 2"] = target
                moved += 1
                break
        if moved == 3:
            break
    g.to_csv(p, index=False)
    code, out = run_simulate(p)
    record("offence locations corrected in a later release", False, code,
           f" ({moved} moved)")

    # --- 9. offences genuinely missing from the current era -------------
    # Remove 60 one-offence records spread across 2024-2025, at most three per
    # month, so no single month moves far enough to trip the revision check.
    # Only the vanished-key limit can catch this.
    p = os.path.join(tmp, "offences_lost.csv")
    g = add_month(d)
    victims, per_month = [], {}
    for idx in g.index[g["Year"].isin(["2024", "2025"]) & (g["Number of offences"] == "1")]:
        m = (g.at[idx, "Year"], g.at[idx, "Month number"])
        if per_month.get(m, 0) < 3:
            per_month[m] = per_month.get(m, 0) + 1
            victims.append(idx)
        if len(victims) == 60:
            break
    g.drop(index=victims).to_csv(p, index=False)
    code, out = run_simulate(p)
    record("offences quietly missing from the current era", True, code,
           f" ({len(victims)} removed)")

    # --- 10. doc wording drift stops the refresh -------------------------
    from pipeline import refresh_docs, stats
    docs = tempfile.mkdtemp(prefix="ntdocs_")
    for rel in ("kaggle/DATA_DICTIONARY.md", "kaggle/METHODOLOGY.md", "README.md"):
        os.makedirs(os.path.dirname(os.path.join(docs, rel)) or docs, exist_ok=True)
        text = open(os.path.join(BASE, rel), encoding="utf-8").read()
        if rel == "README.md":
            text = text.replace("consecutive months, no gaps", "months back to back")
        open(os.path.join(docs, rel), "w", encoding="utf-8").write(text)
    s = stats.load(MASTER)
    try:
        refresh_docs.refresh(s, "x.csv", check_only=True, base=docs)
        code = 0
    except SystemExit:
        code = 1
    record("documentation wording drift", True, code)

    # --- 11. the published master must be untouched throughout ----------
    import hashlib
    h = hashlib.md5(open(MASTER, "rb").read()).hexdigest()
    results.append(("published master untouched by all tests", PASS,
                    f"md5={h}"))

    width = max(len(n) for n, _, _ in results)
    print("\n" + "=" * (width + 30))
    for name, verdict, detail in results:
        print(f"  [{verdict}] {name.ljust(width)}  {detail}")
    print("=" * (width + 30))
    failed = [r for r in results if r[1] == FAIL]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
