"""
portal.py — discover NT Crime Statistics releases on the NT Government's
open data portal via the official CKAN API.

Why the API and not scraping: the portal is CKAN, so package_search returns
every dataset with its resources, licence and timestamps in one call. That is
stable, documented, and does not break when the site's HTML changes.

Why we never trust filenames: the portal has demonstrably lied by name before.
The dataset titled "NT Crime Statistics November 2023" contained no November
2023 data; November 2023 arrived months later as a supplementary CSV attached
to the January and February 2024 dataset pages. Discovery therefore returns
CANDIDATES only — every CSV resource we can see — and the caller decides what
each one really is by reading its contents (see inspect_csv.py).
"""

from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict

# Verify TLS properly. Some Python installs (notably python.org builds on
# macOS) ship without a usable system trust store, so prefer certifi's bundle
# when it is available. Verification is never disabled.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover - certifi absent, use system defaults
    _SSL_CTX = ssl.create_default_context()

PORTAL = "https://data.nt.gov.au"
API = f"{PORTAL}/api/3/action"
SEARCH_QUERY = '"Crime Statistics"'
USER_AGENT = "nt-crime-dashboard-pipeline/1.0 (+https://data.nt.gov.au)"
TIMEOUT = 120


class PortalError(RuntimeError):
    """The portal could not be reached or returned something unusable."""


def _get(url: str, retries: int = 3, backoff: float = 3.0) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
                return resp.read()
        except Exception as exc:  # network, HTTP, timeout
            last = exc
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise PortalError(f"GET failed after {retries} attempts: {url}\n  {last}")


@dataclass
class Candidate:
    """One CSV resource seen on the portal. Says nothing about its contents."""
    dataset_title: str
    dataset_name: str
    resource_name: str
    url: str
    created: str
    last_modified: str
    license_id: str
    license_title: str

    def as_dict(self):
        return asdict(self)


def list_candidates() -> list[Candidate]:
    """Every CSV resource on every NT Crime Statistics dataset page."""
    url = f"{API}/package_search?q={urllib.parse.quote(SEARCH_QUERY)}&rows=1000"
    payload = json.loads(_get(url))
    if not payload.get("success"):
        raise PortalError("CKAN package_search returned success=false")

    results = payload["result"]["results"]
    if not results:
        raise PortalError("CKAN returned zero datasets - refusing to proceed")

    out: list[Candidate] = []
    for pkg in results:
        for res in pkg.get("resources", []):
            if (res.get("format") or "").upper() != "CSV":
                continue
            if not res.get("url"):
                continue
            out.append(Candidate(
                dataset_title=pkg.get("title", ""),
                dataset_name=pkg.get("name", ""),
                resource_name=res.get("name") or "",
                url=res["url"],
                created=res.get("created") or "",
                last_modified=res.get("last_modified") or res.get("created") or "",
                license_id=pkg.get("license_id") or "",
                license_title=pkg.get("license_title") or "",
            ))
    return out


def download(url: str, dest: str) -> str:
    """Download a resource to dest. Returns its md5. Never overwrites silently:
    the caller compares the hash against the manifest before accepting it."""
    blob = _get(url)
    if not blob.strip():
        raise PortalError(f"Downloaded an empty file from {url}")
    head = blob[:2048].lstrip().lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        raise PortalError(f"Expected CSV but got HTML from {url}")
    with open(dest, "wb") as fh:
        fh.write(blob)
    return hashlib.md5(blob).hexdigest()


def fetch_bytes(url: str) -> tuple[bytes, str]:
    """Fetch a resource into memory. Returns (bytes, md5). Used to inspect a
    candidate without writing it to disk."""
    blob = _get(url)
    return blob, hashlib.md5(blob).hexdigest()


def licence_summary(cands: list[Candidate]) -> dict:
    """What licence the portal states. Used to detect an upstream licence
    change, which would be a publication-blocking event."""
    seen = {}
    for c in cands:
        key = (c.license_id, c.license_title)
        seen[key] = seen.get(key, 0) + 1
    return {f"{k[0]}|{k[1]}": v for k, v in sorted(seen.items(), key=lambda kv: -kv[1])}
