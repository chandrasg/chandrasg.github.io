#!/usr/bin/env python3
"""
Rebuild papers.bib from Google Scholar using scholarly.

Two-phase strategy:
  Phase 1: Get ALL 144 pubs from author profile (1 API call - fast, reliable)
            → full titles, years, citation strings (venue info)
  Phase 2: Fill individual pubs for authors (one by one, may get blocked)
            → fallback to CrossRef if scholarly.fill() fails

Writes incrementally so partial work is preserved.

Usage:
  python bin/rebuild_bib.py
  python bin/rebuild_bib.py --no-fill    # phase 1 only, no author fills
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SCHOLAR_ID = "76_hrfUAAAAJ"
BIB_FILE   = Path("_bibliography/papers.bib")
FILL_PAUSE = 3.0   # seconds between scholarly.fill() calls
CR_PAUSE   = 1.0   # seconds between CrossRef calls
UA         = "bib-rebuild/3.0 (mailto:sharathg@cis.upenn.edu)"
CR_WORKS   = "https://api.crossref.org/works"
MAX_FILL_FAILS = 8  # switch to CrossRef after this many consecutive scholar failures


# ─── Load existing keywords ───────────────────────────────────────────────────

def load_existing_keywords(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text("utf-8")
    kw_map = {}
    for raw in re.findall(r"@\w+\{[^@]+", text, re.DOTALL):
        m_key = re.match(r"@\w+\{([^,\n]+),", raw.strip())
        m_kw  = re.search(r"keywords\s*=\s*\{([^}]+)\}", raw)
        if m_key and m_kw:
            kw_map[m_key.group(1).strip()] = m_kw.group(1).strip()
    return kw_map


# ─── CrossRef author lookup ───────────────────────────────────────────────────

def crossref_authors(title: str) -> str:
    """Return 'A and B and C' author string from CrossRef, or ''."""
    try:
        q = urllib.parse.quote(title[:120])
        req = urllib.request.Request(
            f"{CR_WORKS}?query.title={q}&rows=3&select=title,author",
            headers={"User-Agent": UA}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        items = data.get("message", {}).get("items", [])
        for item in items:
            cand = (item.get("title") or [""])[0]
            # Simple word overlap
            tw = set(title.lower().split())
            cw = set(cand.lower().split())
            if tw and len(tw & cw) / max(len(tw), len(cw)) >= 0.6:
                authors = item.get("author", [])
                parts = []
                for a in authors:
                    given = a.get("given", "")
                    family = a.get("family", "")
                    if family:
                        parts.append(f"{given} {family}".strip())
                if parts:
                    return " and ".join(parts)
    except Exception as e:
        pass
    finally:
        time.sleep(CR_PAUSE)
    return ""


# ─── Citation string parser ───────────────────────────────────────────────────

def parse_citation(citation: str) -> dict:
    result = {}
    if not citation:
        return result

    # arXiv preprints
    m = re.match(r"arXiv preprint arXiv:(\S+)", citation, re.I)
    if m:
        result["arxiv"] = m.group(1).rstrip(",")
        result["journal"] = "arXiv"
        result["entry_type"] = "article"
        return result

    # Strip trailing year
    m_yr = re.search(r",\s*(\d{4})\s*$", citation)
    body = citation[:m_yr.start()].strip() if m_yr else citation.strip()

    # Strip pages
    m_pages = re.search(r",?\s*(e\w+|\d+[-–]\d+)\s*$", body)
    if m_pages:
        result["pages"] = m_pages.group(1).replace("–", "--")
        body = body[:m_pages.start()].strip()

    # Strip volume/issue
    m_vol = re.search(r"\s+(\d+)(?:\s*\((\d+)\))?\s*$", body)
    if m_vol:
        result["volume"] = m_vol.group(1)
        if m_vol.group(2):
            result["number"] = m_vol.group(2)
        journal_raw = body[:m_vol.start()].strip().rstrip(",")
    else:
        journal_raw = body.strip().rstrip(",")

    if journal_raw:
        is_conf = bool(re.search(
            r"\b(proceedings|workshop|conference|symposium|annual|"
            r"ACL|EMNLP|NAACL|ICWSM|CHI|CSCW|CVPR|ICCV|AAAI|IJCAI|"
            r"ICML|NeurIPS|KDD|WWW|WSDM|WebSci|INTERSPEECH|ICASSP|ICIP|"
            r"MM|EACL|COLING|LREC|SemEval|ClinicalNLP|WASSA|CLPsych)\b",
            journal_raw, re.I
        ))
        if is_conf:
            result["entry_type"] = "inproceedings"
            result["booktitle"] = journal_raw
        else:
            result["entry_type"] = "article"
            result["journal"] = journal_raw

    return result


# ─── BibTeX writer ────────────────────────────────────────────────────────────

_FIELD_ORDER = [
    "title", "author", "journal", "booktitle", "year",
    "volume", "number", "pages", "doi", "arxiv",
    "html", "keywords", "bibtex_show",
]

def make_entry(key: str, entry_type: str, fields: dict) -> str:
    ordered = [k for k in _FIELD_ORDER if k in fields]
    ordered += sorted(k for k in fields if k not in _FIELD_ORDER)
    lines = [f"@{entry_type}{{{key},"]
    for k in ordered:
        v = str(fields[k]).replace("\n", " ").strip()
        if not v:
            continue
        v = re.sub(r"(?<!\\)%", r"\\%", v)
        lines.append(f"  {k} = {{{v}}},")
    lines.append("}")
    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scholar-id", default=SCHOLAR_ID)
    ap.add_argument("--no-fill", action="store_true",
                    help="Skip scholarly.fill() calls — use only basic pub data")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    existing_kw = load_existing_keywords(BIB_FILE)
    print(f"Loaded keywords for {len(existing_kw)} existing entries.")

    try:
        from scholarly import scholarly
    except ImportError:
        print("pip install scholarly")
        return 1

    # ── Phase 1: Get all pubs (basic info) ────────────────────────────────────
    print(f"\nPhase 1: Fetching all publications for {args.scholar_id}...")
    author = scholarly.search_author_id(args.scholar_id)
    author = scholarly.fill(author, sections=["publications"])
    all_pubs = author.get("publications", [])
    print(f"Found {len(all_pubs)} publications.")

    if args.limit:
        all_pubs = all_pubs[:args.limit]
        print(f"Limited to first {args.limit}.")

    # ── Phase 2: Fill each pub individually ───────────────────────────────────
    entries = []
    consec_fails = 0
    use_crossref_only = args.no_fill

    print(f"\nPhase 2: Enriching {len(all_pubs)} pubs...")
    print("(Will fall back to CrossRef for authors if Scholar blocks)\n")

    for i, pub in enumerate(all_pubs, 1):
        pub_id = pub.get("author_pub_id", "")
        key = pub_id.replace(":", "_").replace("/", "_") if pub_id else f"unknown_{i}"
        bib0 = pub.get("bib", {})

        title_basic = bib0.get("title", "").strip()
        year_basic  = str(bib0.get("pub_year", "")).strip()
        cite_basic  = bib0.get("citation", "").strip()

        print(f"[{i:3d}/{len(all_pubs)}] {title_basic[:70]}")

        # Attempt scholarly.fill() unless blocked
        filled_bib = {}
        if not use_crossref_only:
            try:
                pub_filled = scholarly.fill(pub)
                filled_bib = pub_filled.get("bib", {})
                consec_fails = 0
                time.sleep(FILL_PAUSE)
            except Exception as e:
                consec_fails += 1
                print(f"         scholarly.fill FAILED ({e}) [{consec_fails} consec]")
                if consec_fails >= MAX_FILL_FAILS:
                    print(f"         Switching to CrossRef-only mode for remaining pubs.")
                    use_crossref_only = True
                time.sleep(FILL_PAUSE * 2)

        # Pick best available data
        title  = filled_bib.get("title", title_basic).strip() or title_basic
        authors = filled_bib.get("author", "").strip()
        year   = str(filled_bib.get("pub_year", year_basic) or year_basic).strip()
        cite   = cite_basic  # citation string is the same either way
        pub_url = pub.get("pub_url", "") or pub_filled.get("pub_url", "") if not use_crossref_only and filled_bib else pub.get("pub_url", "")

        # If no authors from Scholar, try CrossRef
        if not authors:
            print(f"         CrossRef author lookup for: {title[:55]}")
            authors = crossref_authors(title)
            if authors:
                print(f"         ✓ CrossRef: {authors[:70]}")
            else:
                print(f"         ✗ No authors found")

        # Parse venue
        parsed = parse_citation(cite)
        entry_type = parsed.pop("entry_type", "article")

        fields: dict = {}
        fields["title"] = title
        if authors:
            fields["author"] = authors
        if year:
            fields["year"] = year
        if "journal" in parsed:
            fields["journal"] = parsed["journal"]
        if "booktitle" in parsed:
            fields["booktitle"] = parsed["booktitle"]
        for k in ("volume", "number", "pages", "arxiv", "doi"):
            if k in parsed:
                fields[k] = parsed[k]
        if pub_url:
            fields["html"] = pub_url

        fields["keywords"] = existing_kw.get(key, "other")
        fields["bibtex_show"] = "true"

        entry_str = make_entry(key, entry_type, fields)
        entries.append(entry_str)

        venue = fields.get("journal") or fields.get("booktitle", "")
        auth_preview = authors[:60] if authors else "(no authors)"
        print(f"         → {auth_preview}")
        print(f"           {venue[:60]}, {year}")

    # Write
    print(f"\n{'='*60}")
    print(f"Processed: {len(entries)} / {len(all_pubs)}")
    BIB_FILE.write_text("\n\n\n".join(entries) + "\n", "utf-8")
    print(f"Wrote {BIB_FILE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
