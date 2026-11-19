"""
test_portal.py — prove release discovery survives a search-server outage.

The NT portal's search server has failed on its own while the rest of its API
kept working. Discovery must then fall back to listing datasets, find the same
releases, and still refuse to proceed when it finds none at all.

The whole portal has also gone down (14-15 November 2026). That is reported as
an outage (exit 4, a warning), not a failure, until the data falls far enough
behind that a release is overdue.

    python tests/test_portal.py

Runs offline: the portal's responses are simulated.
"""
import json
import os
import sys
import io
import urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from pipeline import portal, update

PKGS = {
    "nt-crime-statistics-august-2026": {
        "name": "nt-crime-statistics-august-2026", "title": "Current - NT Crime Statistics August 2026",
        "notes": "", "license_id": "cc-by", "license_title": "Creative Commons Attribution",
        "resources": [{"format": "CSV", "url": "https://example/aug.csv", "name": "aug"},
                      {"format": "XLSX", "url": "https://example/aug.xlsx", "name": "glossary"}]},
    "crime-prevention-grants": {
        "name": "crime-prevention-grants", "title": "Crime prevention grants", "notes": "",
        "resources": [{"format": "CSV", "url": "https://example/grants.csv", "name": "grants"}]},
    "school-enrolments": {"name": "school-enrolments", "title": "School enrolments",
                          "notes": "", "resources": []},
}
results = []


def fake_get(search_up, packages):
    def _get(url, retries=3, backoff=3.0):
        if "package_search" in url:
            if not search_up:
                raise portal.PortalError(f"GET failed after {retries} attempts: {url}\n"
                                         "  HTTP Error 500: INTERNAL SERVER ERROR")
            hits = [p for p in packages.values() if "crime statistics" in p["title"].lower()]
            return json.dumps({"success": True, "result": {"results": hits}}).encode()
        if url.endswith("package_list"):
            return json.dumps({"success": True, "result": list(packages)}).encode()
        if "package_show" in url:
            return json.dumps({"success": True, "result": packages[url.split("id=")[1]]}).encode()
        raise urllib.error.URLError(f"unexpected url {url}")
    return _get


def check(name, ok, detail=""):
    results.append((name, "PASS" if ok else "FAIL", detail))


def main():
    real = portal._get
    try:
        portal._get = fake_get(True, PKGS)
        up = portal.list_candidates()
        check("search working: finds the crime release", [c.url for c in up] == ["https://example/aug.csv"])

        portal._get = fake_get(False, PKGS)
        notes = []
        down = portal.list_candidates(notes.append)
        check("search down: falls back to listing", [c.url for c in down] == [c.url for c in up],
              f"{len(down)} candidate(s)")
        check("search down: says it fell back", any("listing datasets" in n for n in notes))

        portal._get = fake_get(False, {"school-enrolments": PKGS["school-enrolments"]})
        try:
            portal.list_candidates()
            check("search down and nothing listed: refuses", False)
        except portal.PortalUnavailable:
            check("search down and nothing listed: refuses", False, "misread as an outage")
        except portal.PortalError:
            check("search down and nothing listed: refuses", True)

        def all_down(url, retries=3, backoff=3.0):
            raise portal.PortalUnavailable(f"GET failed: {url}\n  HTTP Error 500: Internal Server Error")
        portal._get = all_down
        try:
            portal.list_candidates()
            check("whole portal down: reported as an outage", False)
        except portal.PortalUnavailable:
            check("whole portal down: reported as an outage", True)
    finally:
        portal._get = real

    # How _get classifies failures: server-side means an outage, a 404 does not.
    real_open, real_sleep = portal.urllib.request.urlopen, portal.time.sleep
    portal.time.sleep = lambda s: None
    try:
        for label, exc, outage in [
                ("HTTP 500 is an outage", urllib.error.HTTPError("u", 500, "err", {}, io.BytesIO()), True),
                ("HTTP 503 is an outage", urllib.error.HTTPError("u", 503, "err", {}, io.BytesIO()), True),
                ("network error is an outage", urllib.error.URLError("connection reset"), True),
                ("HTTP 404 is not an outage", urllib.error.HTTPError("u", 404, "err", {}, io.BytesIO()), False)]:
            def _raise(*a, exc=exc, **k): raise exc
            portal.urllib.request.urlopen = _raise
            try:
                portal._get("https://example/x")
                check(label, False)
            except portal.PortalError as err:
                check(label, isinstance(err, portal.PortalUnavailable) == outage)
    finally:
        portal.urllib.request.urlopen, portal.time.sleep = real_open, real_sleep

    # What the orchestrator does with an outage: wait while the data is
    # current, fail once a release is overdue.
    out = io.StringIO(); real_stdout = sys.stdout; sys.stdout = out
    try:
        fresh = update.portal_down("HTTP 500", "2026-08", today="2026-11-19")
        stale = update.portal_down("HTTP 500", "2026-08", today="2026-12-02")
        real_list, real_behind = portal.list_candidates, update.months_behind
        portal.list_candidates = lambda log=None: all_down("https://data.nt.gov.au/api/3/action/package_list")
        update.months_behind = lambda *a, **k: 0
        try:
            end_to_end = update.main(["--check", "--skip-history-check"])
        finally:
            portal.list_candidates, update.months_behind = real_list, real_behind
    finally:
        sys.stdout = real_stdout
    check("outage while data is current: exit 4", fresh == 4, f"exit={fresh}")
    check("outage once a release is overdue: exit 1", stale == 1, f"exit={stale}")
    check("update --check during an outage: exit 4", end_to_end == 4, f"exit={end_to_end}")

    real_fetch = portal.fetch_bytes
    tried = []
    portal.fetch_bytes = lambda url: (tried.append(url), all_down(url))[1]
    try:
        cands = [portal.Candidate("t", "n", "r", f"https://example/{i}.csv", "", "", "", "") for i in range(2)]
        chosen, _, down = update.discover_current(cands)
        check("every download fails in an outage: flagged", chosen is None and down is True)
        tried.clear()
        cands = [portal.Candidate("t", "n", "r", f"https://example/{i}.csv", "", "", "", "") for i in range(78)]
        chosen, _, down = update.discover_current(cands)
        check("portal down mid-run: stops after 3 files", chosen is None and down and len(tried) == 3,
              f"{len(tried)} of 78 tried")
    finally:
        portal.fetch_bytes = real_fetch

    print()
    print("=" * 76)
    for name, status, detail in results:
        print(f"  [{status}] {name:52s} {detail}")
    print("=" * 76)
    failed = [r for r in results if r[1] != "PASS"]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
