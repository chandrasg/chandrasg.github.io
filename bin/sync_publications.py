#!/usr/bin/env python3
"""
Sync Google Scholar publications to _bibliography/papers.bib.

Mirrors the CSL-lab approach (csl-lab-upenn.github.io):
  1. SerpAPI (google_scholar_author engine) fetches the full paper list.
     SerpAPI bypasses anti-bot and returns complete, non-truncated titles.
  2. CrossRef enriches each entry with DOI, full author list, volume, pages.
  3. New papers not already in papers.bib are added.
  4. Existing entries are enriched if metadata is missing.

Requirements:
  pip install google-search-results

Environment:
  GOOGLE_SCHOLAR_API_KEY  -- SerpAPI key (stored as GitHub secret)

Usage:
  python bin/sync_publications.py               # full sync
  python bin/sync_publications.py --enrich-only # skip Scholar fetch
  python bin/sync_publications.py --dry-run     # print diff, don't write
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

# --- Config ------------------------------------------------------------------

SCHOLAR_ID = "76_hrfUAAAAJ"
BIB_FILE   = Path("_bibliography/papers.bib")
API_PAUSE  = 0.5   # seconds between CrossRef requests

CR_WORKS   = "https://api.crossref.org/works"
UA         = "bib-sync/3.0 (mailto:sharathg@cis.upenn.edu)"

# --- Text helpers ------------------------------------------------------------

def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return " ".join(t.split())


def _similarity(a: str, b: str) -> float:
    wa = set(_norm(a).split())
    wb = set(_norm(b).split())
    if not wa:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


# --- HTTP helper -------------------------------------------------------------

def _get(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"    [warn] GET {url[:80]}: {e}", file=sys.stderr)
        return None
    finally:
        time.sleep(API_PAUSE)


# --- SerpAPI: Google Scholar fetch -------------------------------------------

def fetch_scholar_pubs(scholar_id: str) -> list[dict]:
    """Fetch all publications via SerpAPI google_scholar_author engine.

    Same approach as the CSL lab website. SerpAPI handles anti-bot,
    returns complete non-truncated titles, and paginates cleanly.

    Returns list of dicts with keys:
      scholar_key, title, authors, venue, year, scholar_url
    """
    try:
        from serpapi import GoogleSearch
    except ImportError:
        print(
            "ERROR: 'google-search-results' package not installed.\n"
            "  pip install google-search-results",
            file=sys.stderr,
        )
        sys.exit(1)

    api_key = os.environ.get("GOOGLE_SCHOLAR_API_KEY", "").strip()
    if not api_key:
        print("ERROR: GOOGLE_SCHOLAR_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    all_articles: list[dict] = []
    start = 0

    while True:
        params = {
            "engine":    "google_scholar_author",
            "author_id": scholar_id,
            "api_key":   api_key,
            "num":       100,
            "start":     start,
            "sort":      "pubdate",
        }
        print(f"  Fetching Scholar page (start={start})...")
        results  = GoogleSearch(params).get_dict()
        articles = results.get("articles", [])
        if not articles:
            break
        all_articles.extend(articles)
        print(f"    Got {len(articles)} articles (total: {len(all_articles)})")
        if len(articles) < 100:
            break
        start += 100

    pubs: list[dict] = []
    for work in all_articles:
        citation_id = work.get("citation_id", "")
        # Normalise to a valid BibTeX key
        key = citation_id.replace(":", "_").replace("/", "_")
        pubs.append({
            "scholar_key": key,
            "title":       work.get("title", "").strip(),
            "authors":     work.get("authors", "").strip(),
            "venue":       work.get("publication", "").strip(),
            "year":        str(work.get("year", "")).strip(),
            "scholar_url": work.get("link", "").strip(),
        })

    return pubs


# --- CrossRef enrichment -----------------------------------------------------

def _cr_lookup_doi(doi: str) -> dict | None:
    data = _get(f"{CR_WORKS}/{urllib.parse.quote(doi, safe='')}")
    return data.get("message") if data else None


def _cr_lookup_title(title: str) -> dict | None:
    data = _get(f"{CR_WORKS}?query.title={urllib.parse.quote(title)}&rows=5")
    if not data:
        return None
    for item in data.get("message", {}).get("items", []):
        cand = (item.get("title") or [""])[0]
        if _similarity(title, cand) >= 0.75:
            return item
    return None


def _cr_to_fields(item: dict) -> dict:
    """Convert a CrossRef work item to BibTeX-ready field dict."""
    f: dict[str, str] = {}

    # Authors
    parts = [
        f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
        for a in item.get("author", []) if a.get("family")
    ]
    if parts:
        f["author"] = " and ".join(parts)

    # Title — CrossRef is canonical; strip HTML tags/entities
    titles = item.get("title", [])
    if titles:
        t = re.sub(r"<[^>]+>", "", titles[0])
        t = (t.replace("&amp;", "\\&")
              .replace("&lt;", "<").replace("&gt;", ">")
              .replace("&quot;", '"').replace("&apos;", "'"))
        f["title"] = t.strip()

    # Year
    for dk in ("published", "published-print", "published-online"):
        dp = item.get(dk, {}).get("date-parts", [[]])
        if dp and dp[0]:
            f["year"] = str(dp[0][0])
            break

    # Venue / volume / issue / pages / DOI
    ct = item.get("container-title", [])
    if ct:
        f["journal"] = ct[0]
    if item.get("volume"):
        f["volume"] = str(item["volume"])
    if item.get("issue"):
        f["number"] = str(item["issue"])
    if item.get("page"):
        f["pages"] = str(item["page"]).replace("-", "--")
    if item.get("DOI"):
        f["doi"] = item["DOI"].lower()

    # Entry-type hint
    ctype = item.get("type", "")
    f["_bib_type"] = "inproceedings" if ("proceedings" in ctype or "chapter" in ctype) else "article"

    return f


def enrich(title: str, doi: str = "") -> dict:
    """Return CrossRef fields for this paper, or {}."""
    item = _cr_lookup_doi(doi) if doi else None
    if not item:
        item = _cr_lookup_title(title)
    return _cr_to_fields(item) if item else {}


# --- BibTeX parser / writer --------------------------------------------------

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


# --- Merge helper ------------------------------------------------------------

def _merge(existing: dict, new: dict) -> tuple[dict, bool]:
    """Fill in missing fields from new. CrossRef title wins if longer."""
    f = dict(existing)
    changed = False
    for k, v in new.items():
        if k.startswith("_") or not v:
            continue
        cur = f.get(k, "").strip()
        if not cur:
            f[k] = v
            changed = True
        elif k == "title" and len(v) > len(cur) + 5:
            f[k] = v   # CrossRef title is more complete
            changed = True
    return f, changed


# --- Main --------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sync Google Scholar -> papers.bib (SerpAPI + CrossRef)"
    )
    ap.add_argument("--scholar-id",   default=SCHOLAR_ID)
    ap.add_argument("--enrich-only",  action="store_true",
                    help="Skip Scholar fetch; only enrich existing entries")
    ap.add_argument("--dry-run",      action="store_true",
                    help="Print what would change but don't write")
    args = ap.parse_args()

    entries = parse_bib(BIB_FILE)
    by_key  = {e["_key"]: e for e in entries if e.get("_key")}
    # Secondary lookup by DOI and normalised title for duplicate detection
    by_doi  = {
        e["_fields"]["doi"].strip().lower(): e["_key"]
        for e in entries if e.get("_key") and e["_fields"].get("doi")
    }
    by_norm_title = {
        _norm(e["_fields"]["title"]): e["_key"]
        for e in entries if e.get("_key") and e["_fields"].get("title")
    }
    print(f"Loaded {len(entries)} entries from {BIB_FILE}.")

    # -- Step 1: Add new publications from Google Scholar via SerpAPI ----------
    added = 0
    if not args.enrich_only:
        print("\nFetching publications from Google Scholar via SerpAPI...")
        scholar_pubs = fetch_scholar_pubs(args.scholar_id)
        print(f"SerpAPI returned {len(scholar_pubs)} publications.")

        for pub in scholar_pubs:
            key   = pub["scholar_key"]
            title = pub["title"]
            if not key or not title:
                continue
            # Skip if already present by key, DOI, or title
            if key in by_key:
                continue
            enriched_doi = pub.get("doi", "").strip().lower()
            if enriched_doi and enriched_doi in by_doi:
                continue
            if _norm(title) in by_norm_title:
                continue

            print(f"  + {title[:72]}")

            # Enrich via CrossRef
            cr       = enrich(title)
            bib_type = cr.pop("_bib_type", "article")

            fields: dict[str, str] = {
                **cr,
                # Fall back to SerpAPI values for anything CrossRef didn't find
                "title":       cr.get("title")  or title,
                "year":        cr.get("year")   or pub["year"],
                "bibtex_show": "true",
            }
            if pub["scholar_url"] and not fields.get("html"):
                fields["html"] = pub["scholar_url"]
            if pub["venue"] and not fields.get("journal"):
                fields["journal"] = pub["venue"]
            if pub["authors"] and not fields.get("author"):
                fields["author"] = pub["authors"]

            new_e: dict = {"_type": bib_type, "_key": key, "_fields": fields}
            entries.append(new_e)
            by_key[key] = new_e
            added += 1

        print(f"Added {added} new publication(s).")

    # -- Step 2: Enrich existing entries missing metadata ----------------------
    def needs_enrichment(e: dict) -> bool:
        f = e["_fields"]
        return bool(f.get("title")) and (
            not f.get("author") or not f.get("doi") or not f.get("year")
        )

    need = [e for e in entries if e.get("_key") and needs_enrichment(e)]
    print(f"\nEnriching {len(need)} entries missing metadata...")

    enriched = 0
    for i, e in enumerate(need, 1):
        title = e["_fields"].get("title", "").strip()
        doi   = e["_fields"].get("doi",   "").strip()
        print(f"  [{i:3d}/{len(need)}] {title[:65]}...")

        cr = enrich(title, doi)
        if not cr:
            print("           x not found in CrossRef")
            continue
        cr.pop("_bib_type", None)
        merged, changed = _merge(e["_fields"], cr)
        if changed:
            if not args.dry_run:
                e["_fields"] = merged
            enriched += 1
            print("           + enriched")
        else:
            print("           ~ already complete")

    print(f"\nSummary: {added} added  {enriched} enriched")

    if args.dry_run:
        print("Dry run -- not writing.")
        return 0

    write_bib(BIB_FILE, entries)
    print(f"Wrote {BIB_FILE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
