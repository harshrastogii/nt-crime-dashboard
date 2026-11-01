"""
test_portal.py — prove release discovery survives a search-server outage.

The NT portal's search server has failed on its own while the rest of its API
kept working. Discovery must then fall back to listing datasets, find the same
releases, and still refuse to proceed when it finds none at all.

    python tests/test_portal.py

Runs offline: the portal's responses are simulated.
"""
import json
import os
import sys
import urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from pipeline import portal

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
        except portal.PortalError:
            check("search down and nothing listed: refuses", True)
    finally:
        portal._get = real

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
