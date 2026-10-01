"""
refresh_docs.py — keep the figures in the shipped documentation current.

Each rule below names one sentence that carries a figure which moves when a new
month is published, and says exactly how many times it must match. If a rule
matches a different number of times, someone has edited the wording, and the
run stops rather than publishing a page that is half updated. Fixing that is a
one-line change to the pattern here.

    refresh(stats, current_file, check_only=True)   # verify every rule matches
    refresh(stats, current_file)                    # rewrite the files
"""

from __future__ import annotations

import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MONTH = r"[A-Z][a-z]+ \d{4}"
YM = r"\d{4}-\d{2}"


def _rules(s: dict, current_file: str) -> dict:
    return {
        "kaggle/DATA_DICTIONARY.md": [
            (rf"\*\*Coverage:\*\* January 2008 → {MONTH} \(\d+ months, no gaps\)",
             f"**Coverage:** January 2008 → {s['last_name']} ({s['months']} months, no gaps)"),
            (r"\*\*Rows:\*\* [\d,]+", f"**Rows:** {s['rows_fmt']}"),
            (r"\*\*Total offences:\*\* [\d,]+", f"**Total offences:** {s['offences_fmt']}"),
            (r"Year, 2008–\d{4}\. Always agrees",
             f"Year, 2008–{s['last_year']}. Always agrees"),
            (rf"`Current / SerPro` \(2023-12 → {YM}\)",
             f"`Current / SerPro` (2023-12 → {s['last']})"),
            (rf"\| `{MONTH} current extract` \| 2023-12 → {YM} \| `[^`]+` \|",
             f"| `{s['last_name']} current extract` | 2023-12 → {s['last']} | `{current_file}` |"),
            (r"spanning 2008–\d{4}", f"spanning 2008–{s['last_year']}"),
        ],
        "kaggle/METHODOLOGY.md": [
            (rf"\| 2023-12 → {YM} \| {MONTH} \| The most recent release",
             f"| 2023-12 → {s['last']} | {s['last_name']} | The most recent release"),
            (r"All [\d,]+ offences map successfully",
             f"All {s['offences_fmt']} offences map successfully"),
            (rf"\d+ of \d+ months present \(2008-01 → {YM}\)",
             f"{s['months']} of {s['months']} months present (2008-01 → {s['last']})"),
        ],
        "README.md": [
            (r"\*\*Northern Territory Crime Statistics — 2008–\d{4}\*\*",
             f"**Northern Territory Crime Statistics — 2008–{s['last_year']}**"),
            (rf"\*\*January 2008 to {MONTH}\*\* — \d+ consecutive months, no gaps\. [\d,]+ rows,\n  [\d,]+ recorded offences",
             f"**January 2008 to {s['last_name']}** — {s['months']} consecutive months, no gaps. "
             f"{s['rows_fmt']} rows,\n  {s['offences_fmt']} recorded offences"),
        ],
    }


def refresh(s: dict, current_file: str, check_only: bool = False, base: str = BASE) -> list:
    """Verify (and unless check_only, apply) every rule. Returns changed files."""
    problems, changed = [], []
    planned = {}
    for rel, rules in _rules(s, current_file).items():
        path = os.path.join(base, rel)
        text = open(path, encoding="utf-8").read()
        new = text
        for pattern, repl in rules:
            n = len(re.findall(pattern, new))
            if n != 1:
                problems.append(f"{rel}: expected 1 match, found {n}: {pattern}")
                continue
            new = re.sub(pattern, lambda _m, r=repl: r, new)
        planned[path] = (text, new)

    if problems:
        raise SystemExit("STOP: documentation wording has drifted from refresh_docs.py:\n  "
                         + "\n  ".join(problems))
    if check_only:
        return []
    for path, (old, new) in planned.items():
        if new != old:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
            changed.append(os.path.relpath(path, base))
    return changed
