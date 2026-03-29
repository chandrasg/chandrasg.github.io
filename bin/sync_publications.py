#!/usr/bin/env python3
"""
Sync Google Scholar publications to _bibliography/papers.bib.

Steps
-----
1. Fetch all publications from Google Scholar via `scholarly`.
   - Any entry not already in papers.bib is added.
2. Enrich every entry that is missing `author` (or has a truncated title)
   using Semantic Scholar, then CrossRef as fallback.
   - Also picks up open-access PDF links from Semantic Scholar.
3. Write the updated papers.bib in-place.

Usage
-----
  pip install scholarly
  python bin/sync_publications.py               # full sync
  python bin/sync_publications.py --enrich-only # skip Scholar fetch
  python bin/sync_publications.py --dry-run     # print diff, don't write
"""

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────

SCHOLAR_ID = "76_hrfUAAAAJ"
BIB_FILE   = Path("_bibliography/papers.bib")
API_PAUSE  = 1.2   # seconds between external API calls

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = "title,authors,year,venue,journal,externalIds,isOpenAccess,openAccessPdf"
CR_WORKS  = "https://api.crossref.org/works"
UA        = "bib-sync/2.0 (mailto:sharathg@cis.upenn.edu)"

# ─── Text helpers ─────────────────────────────────────────────────────────────

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


# ─── HTTP helper ──────────────────────────────────────────────────────────────

def _get(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"    [warn] {url[:80]}: {e}", file=sys.stderr)
        return None
    finally:
        time.sleep(API_PAUSE)


# ─── BibTeX parser / writer ───────────────────────────────────────────────────

def parse_bib(path: Path) -> list[dict]:
    """Return list of entry dicts (with _raw, _type, _key, _fields)."""
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
            "_raw": raw,
            "_type": m.group(1).lower(),
            "_key": m.group(2).strip(),
            "_fields": fields,
        })
    return entries


_FIELD_ORDER = [
    "title", "author", "journal", "booktitle", "year",
    "volume", "number", "pages", "doi", "pdf", "html",
    "keywords", "bibtex_show",
]


def _entry_str(e: dict) -> str:
    if not e.get("_type"):
        return e["_raw"]
    f = e["_fields"]
    ordered = [k for k in _FIELD_ORDER if k in f]
    ordered += sorted(k for k in f if k not in _FIELD_ORDER)
    lines = [f"@{e['_type']}{{{e['_key']},"]
    for k in ordered:
        v = f[k]
        # escape any unbalanced braces in value
        lines.append(f"  {k} = {{{v}}},")
    lines.append("}")
    return "\n".join(lines)


def write_bib(path: Path, entries: list[dict]) -> None:
    chunks = [_entry_str(e) for e in entries]
    path.write_text("\n\n\n".join(chunks) + "\n", "utf-8")


# ─── Semantic Scholar ─────────────────────────────────────────────────────────

def _s2_lookup(title: str) -> dict | None:
    q = urllib.parse.quote(title)
    data = _get(f"{S2_SEARCH}?query={q}&fields={S2_FIELDS}&limit=5")
    if not data:
        return None
    for paper in data.get("data", []):
        if _similarity(title, paper.get("title", "")) >= 0.70:
            return paper
    return None


def _s2_fields(paper: dict) -> dict:
    f: dict[str, str] = {}
    names = [a.get("name", "") for a in paper.get("authors", []) if a.get("name")]
    if names:
        f["author"] = " and ".join(names)
    if paper.get("title"):
        f["title"] = paper["title"]
    if paper.get("year"):
        f["year"] = str(paper["year"])
    j = paper.get("journal") or {}
    if j.get("name"):
        f["journal"] = j["name"]
        if j.get("volume"):
            f["volume"] = str(j["volume"])
        if j.get("pages"):
            f["pages"] = str(j["pages"]).replace("-", "--")
    elif paper.get("venue"):
        f["journal"] = paper["venue"]
    doi = (paper.get("externalIds") or {}).get("DOI")
    if doi:
        f["doi"] = doi
    # Open-access PDF
    oapdf = paper.get("openAccessPdf") or {}
    if oapdf.get("url"):
        f["pdf"] = oapdf["url"]
    return f


# ─── CrossRef ────────────────────────────────────────────────────────────────

def _cr_lookup(title: str) -> dict | None:
    q = urllib.parse.quote(title)
    data = _get(f"{CR_WORKS}?query.title={q}&rows=5")
    if not data:
        return None
    for item in data.get("message", {}).get("items", []):
        cand = ((item.get("title") or [""])[0])
        if _similarity(title, cand) >= 0.75:
            return item
    return None


def _cr_fields(item: dict) -> dict:
    f: dict[str, str] = {}
    authors = item.get("author", [])
    parts = [
        f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
        for a in authors if a.get("family")
    ]
    if parts:
        f["author"] = " and ".join(parts)
    titles = item.get("title", [])
    if titles:
        f["title"] = re.sub(r"<[^>]+>", "", titles[0])
    for dk in ("published", "published-print", "published-online"):
        dp = item.get(dk, {}).get("date-parts", [[]])
        if dp and dp[0]:
            f["year"] = str(dp[0][0])
            break
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
        f["doi"] = item["DOI"]
    return f


# ─── Enrichment ──────────────────────────────────────────────────────────────

def enrich(title: str) -> dict:
    """Return enriched fields from S2 then CrossRef, or {}."""
    paper = _s2_lookup(title)
    if paper:
        fields = _s2_fields(paper)
        if fields.get("author"):
            return fields

    item = _cr_lookup(title)
    if item:
        fields = _cr_fields(item)
        if fields.get("author"):
            return fields

    return {}


def _merge(existing: dict, new: dict) -> tuple[dict, bool]:
    """Merge new fields into existing. Returns (merged, changed)."""
    f = dict(existing)
    changed = False
    for k, v in new.items():
        if not v:
            continue
        cur = f.get(k, "").strip()
        if not cur:
            # Field missing — add it
            f[k] = v
            changed = True
        elif k == "title" and len(v) > len(cur) + 5:
            # Longer title = likely less truncated
            f[k] = v
            changed = True
        elif k == "pdf" and not cur:
            f[k] = v
            changed = True
    return f, changed


# ─── Google Scholar via scholarly ────────────────────────────────────────────

def _scholar_key(pub: dict) -> str | None:
    apid = pub.get("author_pub_id", "")
    if not apid:
        return None
    return apid.replace(":", "_").replace("/", "_")


def _scholar_fields(pub: dict) -> dict:
    bib = pub.get("bib", {})
    f: dict[str, str] = {}
    if bib.get("author"):
        f["author"] = bib["author"]
    if bib.get("title"):
        f["title"] = bib["title"]
    year = bib.get("pub_year") or bib.get("year")
    if year:
        f["year"] = str(year)
    venue = bib.get("journal") or bib.get("venue") or bib.get("booktitle")
    if venue:
        f["journal"] = venue
    for k in ("volume", "number", "pages"):
        if bib.get(k):
            f[k] = str(bib[k])
    url = pub.get("pub_url") or pub.get("eprint_url")
    if url:
        f["html"] = url
    return f


def fetch_scholar_pubs(scholar_id: str) -> list[dict]:
    """Return list of scholarly publication dicts, or [] on failure."""
    try:
        from scholarly import scholarly as sc
        print("Fetching Google Scholar profile (this may take a minute)...")
        author = sc.search_author_id(scholar_id)
        author = sc.fill(author, sections=["publications"])
        pubs = author.get("publications", [])
        print(f"  Found {len(pubs)} publications on Scholar.")
        return pubs
    except ImportError:
        print("scholarly not installed — run: pip install scholarly", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Scholar fetch failed ({e}) — proceeding with enrich-only.", file=sys.stderr)
        return []


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Sync Google Scholar → papers.bib")
    ap.add_argument("--scholar-id", default=SCHOLAR_ID)
    ap.add_argument("--enrich-only", action="store_true",
                    help="Skip Scholar fetch; only enrich existing entries")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would change but don't write")
    args = ap.parse_args()

    entries = parse_bib(BIB_FILE)
    by_key = {e["_key"]: e for e in entries if e.get("_key")}
    print(f"Loaded {len(entries)} entries from {BIB_FILE}.")

    # ── Step 1: Add new publications from Google Scholar ──────────────────────
    added = 0
    if not args.enrich_only:
        for pub in fetch_scholar_pubs(args.scholar_id):
            key = _scholar_key(pub)
            if not key or key in by_key:
                continue
            sf = _scholar_fields(pub)
            if not sf.get("title"):
                continue
            new_e: dict = {
                "_type": "article",
                "_key": key,
                "_fields": {**sf, "bibtex_show": "true"},
            }
            entries.append(new_e)
            by_key[key] = new_e
            added += 1
            print(f"  + {sf.get('title', '')[:75]}")
        print(f"Added {added} new publication(s) from Scholar.")

    # ── Step 2: Enrich entries missing author or with truncated titles ─────────
    # An entry needs enrichment if:
    #   a) no author field, OR
    #   b) title ends with "..." or looks truncated (ends mid-word without punct)
    def needs_enrichment(e: dict) -> bool:
        f = e["_fields"]
        if not f.get("title"):
            return False  # nothing to search with
        if not f.get("author", "").strip():
            return True
        title = f.get("title", "").strip()
        # Heuristic: truncated if last char is not punctuation and not a closing brace
        if title and title[-1] not in ".!?)}'\"":
            return True
        return False

    need = [e for e in entries if e.get("_key") and needs_enrichment(e)]
    print(f"\nEnriching {len(need)} entries...")

    enriched = 0
    failed = 0
    for i, e in enumerate(need, 1):
        title = e["_fields"].get("title", "").strip()
        key = e["_key"]
        print(f"  [{i:3d}/{len(need)}] {key[:40]:40s}  {title[:45]}...")

        new_f = enrich(title)
        if not new_f:
            print("           ✗ not found")
            failed += 1
            continue

        merged, changed = _merge(e["_fields"], new_f)
        if changed:
            if not args.dry_run:
                e["_fields"] = merged
            enriched += 1
            author_preview = merged.get("author", "")[:60]
            print(f"           ✓ {author_preview}")
        else:
            print("           ~ no new data")

    print(f"\nSummary: {added} added · {enriched} enriched · {failed} not found")

    if args.dry_run:
        print("Dry run — not writing.")
        return 0

    write_bib(BIB_FILE, entries)
    print(f"Wrote {BIB_FILE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
