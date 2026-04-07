#!/usr/bin/env python3
"""
Reconcile papers.bib against cv_publications.yaml (the CV ground truth).

For each bib entry, finds the best-matching CV entry using normalized Jaccard
title similarity (threshold 0.75).  Matched entries get:
  - author      updated from CV authors_cv string
  - journal     updated from CV venue (article entries)
  - booktitle   updated from CV venue (inproceedings entries)
  - publisher   updated from CV venue (book entries)

Fields never overwritten: doi, volume, number, pages, html, arxiv, year.
Preprint entries skip venue update but still get author update.

Usage:
  python bin/reconcile_cv.py               # apply changes in place
  python bin/reconcile_cv.py --dry-run     # print diff, don't write
  python bin/reconcile_cv.py --cv-yaml PATH/TO/other.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "ERROR: PyYAML not installed.  pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

BIB_FILE     = Path("_bibliography/papers.bib")
CV_YAML_FILE = Path("_bibliography/cv_publications.yaml")
THRESHOLD    = 0.75

# ---------------------------------------------------------------------------
# Text helpers (same as sync_publications.py)
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return " ".join(t.split())


def _jaccard(a: str, b: str) -> float:
    wa = set(_norm(a).split())
    wb = set(_norm(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# ---------------------------------------------------------------------------
# BibTeX parser / writer  (copy from sync_publications.py for self-contained run)
# ---------------------------------------------------------------------------

def parse_bib(path: Path) -> list[dict]:
    text = path.read_text("utf-8")
    entries: list[dict] = []
    for raw in re.findall(r"@\w+\{[^@]+", text, re.DOTALL):
        raw = raw.strip()
        m = re.match(r"@(\w+)\{([^,\n]+),", raw)
        if not m:
            if raw:
                entries.append({"_raw": raw, "_type": None, "_key": None, "_fields": {}})
            continue
        fields: dict[str, str] = {}
        for fm in re.finditer(
            r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", raw, re.DOTALL
        ):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        entries.append({
            "_raw":    raw,
            "_type":   m.group(1).lower(),
            "_key":    m.group(2).strip(),
            "_fields": fields,
        })
    return entries


_FIELD_ORDER = [
    "title", "author", "journal", "booktitle", "year",
    "volume", "number", "pages", "doi", "arxiv", "pdf", "html",
    "note", "keywords", "bibtex_show",
]


def _entry_str(e: dict) -> str:
    if not e.get("_type"):
        return e["_raw"]
    f = {k: v for k, v in e["_fields"].items() if not k.startswith("_")}
    ordered  = [k for k in _FIELD_ORDER if k in f]
    ordered += sorted(k for k in f if k not in _FIELD_ORDER)
    lines = [f"@{e['_type']}{{{e['_key']},"]
    for k in ordered:
        lines.append(f"  {k} = {{{f[k]}}},")
    lines.append("}")
    return "\n".join(lines)


def write_bib(path: Path, entries: list[dict]) -> None:
    path.write_text("\n\n\n".join(_entry_str(e) for e in entries) + "\n", "utf-8")


# ---------------------------------------------------------------------------
# Author conversion: CV format  →  BibTeX "Last, F.I. and Last, F.I." format
# ---------------------------------------------------------------------------

def _cv_authors_to_bibtex(authors_cv: str) -> str:
    """
    Convert a CV author string such as:
        "Sehgal, N.K., Tronieri, J., Ungar, L.H., Guntuku, S.C."
    to BibTeX format:
        "Sehgal, N.K. and Tronieri, J. and Ungar, L.H. and Guntuku, S.C."

    Strategy
    --------
    Each author occupies exactly two comma-separated tokens:
        token[0]: Last name  (e.g. "Sehgal")
        token[1]: Initials   (e.g. "N.K.")

    We iterate the comma-split token list, pairing consecutive tokens when the
    second token looks like initials, and treat unpaired tokens as standalone
    names (e.g. "World Bank", "Aditya, B." where "B." is the second token).
    """
    # Normalise ampersand before last author
    s = authors_cv.replace(" & ", ", ").strip()

    # Tokenise on commas; preserve trailing period within each token
    raw_tokens = [t.strip() for t in s.split(",")]
    # Drop empty trailing token that arises from a trailing comma + period combo
    raw_tokens = [t for t in raw_tokens if t]

    # Initials pattern: optional multi-char uppercase prefix ending with a dot,
    # e.g. "N.K.", "S.C.", "R.M.", "A.", "L.H.", "Y.Y.L.", "A.K.", "B."
    _INITIALS = re.compile(r'^[A-Z](?:\.[A-Za-z]+)*\.?$')

    authors: list[str] = []
    i = 0
    while i < len(raw_tokens):
        tok = raw_tokens[i]
        if i + 1 < len(raw_tokens):
            nxt = raw_tokens[i + 1]
            if _INITIALS.match(nxt):
                # Ensure initials end with a dot
                if not nxt.endswith("."):
                    nxt = nxt + "."
                authors.append(f"{tok}, {nxt}")
                i += 2
                continue
        # Standalone token (no initials following, or last token is initials
        # that were already consumed); append as-is if non-empty
        if tok:
            authors.append(tok)
        i += 1

    return " and ".join(authors) if authors else s


# ---------------------------------------------------------------------------
# CV YAML loader
# ---------------------------------------------------------------------------

def load_cv(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text("utf-8"))
    return data.get("publications", [])


# ---------------------------------------------------------------------------
# Venue field name for a given bib entry type / entry
# ---------------------------------------------------------------------------

def _venue_field(bib_type: str, fields: dict) -> str | None:
    """Return the field name that holds the venue for this entry, or None."""
    t = bib_type.lower()
    if t == "article":
        return "journal"
    if t in ("inproceedings", "proceedings"):
        return "booktitle"
    if t == "book":
        return "publisher"
    # misc / techreport / etc. — use journal if present, else None
    if "journal" in fields:
        return "journal"
    return None


def _is_preprint(fields: dict) -> bool:
    """Heuristic: treat as preprint if venue contains arXiv/preprint/medRxiv."""
    venue_text = (fields.get("journal", "") + " " + fields.get("note", "")).lower()
    return any(kw in venue_text for kw in ("arxiv", "preprint", "medrxiv", "biorxiv"))


# ---------------------------------------------------------------------------
# Main reconciliation logic
# ---------------------------------------------------------------------------

def reconcile(
    bib_path: Path,
    cv_path: Path,
    dry_run: bool = False,
    threshold: float = THRESHOLD,
) -> int:
    entries = parse_bib(bib_path)
    cv_pubs = load_cv(cv_path)

    print(f"Loaded {len(entries)} bib entries from {bib_path}.")
    print(f"Loaded {len(cv_pubs)} CV entries from {cv_path}.")

    # Build a lookup list of (title, cv_entry) for fast iteration
    cv_index = [(pub["title"], pub) for pub in cv_pubs if pub.get("title")]

    n_matched   = 0
    n_updated   = 0
    n_no_match  = 0
    n_skipped   = 0

    for e in entries:
        if not e.get("_key") or not e.get("_type"):
            n_skipped += 1
            continue

        bib_title = e["_fields"].get("title", "").strip()
        if not bib_title:
            n_skipped += 1
            continue

        # Find best CV match by Jaccard similarity
        best_score = 0.0
        best_cv    = None
        for cv_title, cv_entry in cv_index:
            score = _jaccard(bib_title, cv_title)
            if score > best_score:
                best_score = score
                best_cv    = cv_entry

        if best_score < threshold or best_cv is None:
            n_no_match += 1
            continue

        n_matched += 1
        changes: list[str] = []

        # --- Author update ---
        cv_authors_raw = best_cv.get("authors_cv", "").strip()
        if cv_authors_raw:
            new_author = _cv_authors_to_bibtex(cv_authors_raw)
            old_author = e["_fields"].get("author", "").strip()
            if new_author and new_author != old_author:
                changes.append(f"  author:\n    old: {old_author[:80]}\n    new: {new_author[:80]}")
                if not dry_run:
                    e["_fields"]["author"] = new_author

        # --- Venue update (skip for preprints) ---
        if not _is_preprint(e["_fields"]):
            cv_venue = best_cv.get("venue", "").strip()
            if cv_venue:
                venue_field = _venue_field(e["_type"], e["_fields"])
                if venue_field:
                    old_venue = e["_fields"].get(venue_field, "").strip()
                    if cv_venue != old_venue:
                        changes.append(
                            f"  {venue_field}:\n"
                            f"    old: {old_venue[:80]}\n"
                            f"    new: {cv_venue[:80]}"
                        )
                        if not dry_run:
                            e["_fields"][venue_field] = cv_venue

        if changes:
            n_updated += 1
            print(f"\n[{e['_key']}] matched CV entry (score={best_score:.2f}):")
            print(f"  title: {bib_title[:80]}")
            for c in changes:
                print(c)

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"Summary")
    print(f"  Bib entries processed : {len(entries)}")
    print(f"  Matched to CV         : {n_matched}")
    print(f"  Updated               : {n_updated}")
    print(f"  No CV match found     : {n_no_match}")
    print(f"  Skipped (no title)    : {n_skipped}")
    print(f"{'=' * 60}")

    if dry_run:
        print("\nDry run -- not writing.")
        return 0

    write_bib(bib_path, entries)
    print(f"\nWrote updated bib to {bib_path}.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Reconcile papers.bib against cv_publications.yaml ground truth."
    )
    ap.add_argument(
        "--bib",
        default=str(BIB_FILE),
        help=f"Path to BibTeX file (default: {BIB_FILE})",
    )
    ap.add_argument(
        "--cv-yaml",
        default=str(CV_YAML_FILE),
        help=f"Path to CV YAML file (default: {CV_YAML_FILE})",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change but do not write the bib file",
    )
    ap.add_argument(
        "--threshold",
        type=float,
        default=THRESHOLD,
        help=f"Jaccard similarity threshold for title matching (default: {THRESHOLD})",
    )
    args = ap.parse_args()

    bib_path = Path(args.bib)
    cv_path  = Path(args.cv_yaml)

    if not bib_path.exists():
        print(f"ERROR: bib file not found: {bib_path}", file=sys.stderr)
        return 1
    if not cv_path.exists():
        print(f"ERROR: CV YAML not found: {cv_path}", file=sys.stderr)
        return 1

    return reconcile(
        bib_path=bib_path,
        cv_path=cv_path,
        dry_run=args.dry_run,
        threshold=args.threshold,
    )


if __name__ == "__main__":
    sys.exit(main())
