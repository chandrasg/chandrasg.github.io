#!/usr/bin/env python3
"""
Enrich papers.bib using CrossRef and Semantic Scholar APIs.

For each entry that needs enrichment (missing authors OR truncated title):
  1. Try Semantic Scholar title search
  2. Try CrossRef title search
  3. If found: update title, add authors, update journal/venue, add DOI

CrossRef is generous: 50 req/sec. Semantic Scholar: ~1/sec without API key.

Usage:
  python bin/enrich_crossref.py
  python bin/enrich_crossref.py --dry-run
  python bin/enrich_crossref.py --limit 20
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

BIB_FILE = Path("_bibliography/papers.bib")
UA       = "bib-enrich/1.0 (mailto:sharathg@cis.upenn.edu; academic research)"
CR_WORKS = "https://api.crossref.org/works"
S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = "title,authors,year,venue,journal,externalIds,isOpenAccess,openAccessPdf"


# ─── BibTeX parsing ──────────────────────────────────────────────────────────

def parse_bib(path: Path) -> list[dict]:
    text = path.read_text("utf-8")
    entries = []
    for raw in re.findall(r"@\w+\{[^@]+", text, re.DOTALL):
        raw = raw.strip()
        m = re.match(r"@(\w+)\{([^,\n]+),", raw)
        if not m:
            if raw:
                entries.append({"_raw": raw, "_type": None, "_key": None, "_fields": {}})
            continue
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", raw, re.DOTALL):
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
    "volume", "number", "pages", "doi", "arxiv", "html",
    "keywords", "bibtex_show",
]


def entry_str(e: dict) -> str:
    if not e.get("_type"):
        return e["_raw"]
    f = e["_fields"]
    ordered = [k for k in _FIELD_ORDER if k in f]
    ordered += sorted(k for k in f if k not in _FIELD_ORDER)
    lines = [f"@{e['_type']}{{{e['_key']},"]
    for k in ordered:
        v = str(f[k]).replace("\n", " ").strip()
        if not v:
            continue
        lines.append(f"  {k} = {{{v}}},")
    lines.append("}")
    return "\n".join(lines)


def write_bib(path: Path, entries: list[dict]) -> None:
    path.write_text("\n\n\n".join(entry_str(e) for e in entries) + "\n", "utf-8")


# ─── Text matching ────────────────────────────────────────────────────────────

def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return " ".join(t.split())

def similarity(a: str, b: str) -> float:
    wa = set(norm(a).split())
    wb = set(norm(b).split())
    if not wa:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


# ─── HTTP ────────────────────────────────────────────────────────────────────

def fetch(url: str, pause: float = 0.5) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"    [http] {url[:80]}: {e}", file=sys.stderr)
        return None
    finally:
        time.sleep(pause)


# ─── CrossRef ────────────────────────────────────────────────────────────────

def crossref_lookup(title: str) -> dict | None:
    """Search CrossRef by title, return best matching item or None."""
    q = urllib.parse.quote(title[:120])
    data = fetch(f"{CR_WORKS}?query.title={q}&rows=5&select=title,author,published,container-title,volume,issue,page,DOI,type", pause=0.4)
    if not data:
        return None
    for item in data.get("message", {}).get("items", []):
        cand = (item.get("title") or [""])[0]
        if similarity(title, cand) >= 0.65:
            return item
    return None


def cr_extract(item: dict) -> dict:
    f: dict = {}
    titles = item.get("title", [])
    if titles:
        f["title"] = re.sub(r"<[^>]+>", "", titles[0])
    authors = item.get("author", [])
    parts = []
    for a in authors:
        given = a.get("given", "")
        family = a.get("family", "")
        if family:
            parts.append(f"{given} {family}".strip())
    if parts:
        f["author"] = " and ".join(parts)
    for dk in ("published", "published-print", "published-online"):
        dp = item.get(dk, {}).get("date-parts", [[]])
        if dp and dp[0]:
            f["year"] = str(dp[0][0])
            break
    ct = item.get("container-title", [])
    if ct:
        raw = ct[0]
        is_conf = bool(re.search(
            r"\b(proceedings|workshop|conference|symposium|annual|ACL|EMNLP|"
            r"NAACL|ICWSM|CHI|CSCW|CVPR|ICCV|AAAI|IJCAI|ICML|NeurIPS|KDD|"
            r"WWW|WSDM|WebSci|INTERSPEECH|ICASSP|ICIP|WASSA|CLPsych)\b",
            raw, re.I
        ))
        if is_conf:
            f["booktitle"] = raw
        else:
            f["journal"] = raw
    if item.get("volume"):
        f["volume"] = str(item["volume"])
    if item.get("issue"):
        f["number"] = str(item["issue"])
    if item.get("page"):
        f["pages"] = str(item["page"]).replace("-", "--")
    if item.get("DOI"):
        f["doi"] = item["DOI"]
    return f


# ─── Semantic Scholar ─────────────────────────────────────────────────────────

def s2_lookup(title: str) -> dict | None:
    q = urllib.parse.quote(title[:120])
    data = fetch(f"{S2_SEARCH}?query={q}&fields={S2_FIELDS}&limit=5", pause=1.5)
    if not data:
        return None
    for paper in data.get("data", []):
        if similarity(title, paper.get("title", "")) >= 0.70:
            return paper
    return None


def s2_extract(paper: dict) -> dict:
    f: dict = {}
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
    arxiv = (paper.get("externalIds") or {}).get("ArXiv")
    if arxiv:
        f["arxiv"] = arxiv
    oapdf = paper.get("openAccessPdf") or {}
    return f


# ─── Journal name extraction from existing journal field ─────────────────────

def clean_journal_field(journal_str: str) -> str:
    """
    The imported journal field often has: 'Journal Name Vol, Pages, Year'
    Extract just the journal name.
    """
    if not journal_str:
        return ""
    # Remove trailing year
    j = re.sub(r",\s*\d{4}\s*$", "", journal_str).strip()
    # Remove trailing pages like ', 43-49'
    j = re.sub(r",\s*\d+[-–]\d+\s*$", "", j).strip()
    # Remove trailing volume/issue like ' 18' or ' 18 (3)'
    j = re.sub(r"\s+\d+(?:\s*\(\d+\))?\s*$", "", j).strip()
    j = j.rstrip(",").strip()
    return j


# ─── Needs enrichment? ────────────────────────────────────────────────────────

def needs_enrichment(e: dict) -> bool:
    f = e["_fields"]
    if not f.get("title"):
        return False
    # Missing authors
    if not f.get("author", "").strip():
        return True
    # Truncated title (last char not punctuation)
    title = f.get("title", "").strip()
    if title and title[-1] not in ".!?)}'\"":
        return True
    # Journal field contains volume/page info (poorly formatted)
    journal = f.get("journal", "")
    if journal and re.search(r",\s*\d{4}\s*$", journal):
        return True
    return False


# ─── Merge ────────────────────────────────────────────────────────────────────

def merge(existing: dict, new: dict) -> tuple[dict, bool]:
    f = dict(existing)
    changed = False
    for k, v in new.items():
        if not v:
            continue
        cur = f.get(k, "").strip()
        if not cur:
            f[k] = v
            changed = True
        elif k == "title" and len(v) > len(cur) + 3:
            f[k] = v
            changed = True
        elif k == "journal" and re.search(r",\s*\d{4}\s*$", cur):
            # Replace poorly formatted journal with clean one
            f[k] = v
            changed = True
        elif k == "doi" and not cur:
            f[k] = v
            changed = True
    return f, changed


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--s2-first", action="store_true",
                    help="Try Semantic Scholar before CrossRef (slower, may hit 429)")
    args = ap.parse_args()

    entries = parse_bib(BIB_FILE)
    print(f"Loaded {len(entries)} entries from {BIB_FILE}.")

    # Also clean up journal fields for entries that don't need full enrichment
    cleaned_journals = 0
    for e in entries:
        if e.get("_type") and e["_fields"].get("journal"):
            j = e["_fields"]["journal"]
            if re.search(r",\s*\d{4}\s*$", j):
                cleaned = clean_journal_field(j)
                if cleaned and cleaned != j:
                    e["_fields"]["journal"] = cleaned
                    cleaned_journals += 1

    print(f"Pre-cleaned {cleaned_journals} journal fields.")

    # Find entries needing enrichment
    need = [e for e in entries if e.get("_key") and needs_enrichment(e)]
    if args.limit:
        need = need[:args.limit]
    print(f"Need enrichment: {len(need)} entries.\n")

    enriched = found_s2 = found_cr = not_found = 0

    for i, e in enumerate(need, 1):
        title = e["_fields"].get("title", "").strip()
        key = e["_key"]
        print(f"[{i:3d}/{len(need)}] {title[:65]}")

        new_f: dict = {}

        # Try Semantic Scholar first if requested
        if args.s2_first:
            paper = s2_lookup(title)
            if paper:
                new_f = s2_extract(paper)
                if new_f.get("author"):
                    print(f"         S2 ✓  {new_f.get('author','')[:60]}")
                    found_s2 += 1

        # CrossRef (always try if no authors yet)
        if not new_f.get("author"):
            item = crossref_lookup(title)
            if item:
                new_f = cr_extract(item)
                if new_f.get("author"):
                    print(f"         CR ✓  {new_f.get('author','')[:60]}")
                    print(f"               {new_f.get('journal') or new_f.get('booktitle','')[:50]}")
                    found_cr += 1
                else:
                    print(f"         CR found paper but no authors")
            else:
                print(f"         ✗ not found")
                not_found += 1
                continue

        if not new_f:
            not_found += 1
            continue

        merged, changed = merge(e["_fields"], new_f)
        if changed:
            if not args.dry_run:
                e["_fields"] = merged
            enriched += 1
        else:
            print(f"         ~ no new data")

    print(f"\n{'='*60}")
    print(f"Enriched: {enriched}  |  S2: {found_s2}  |  CR: {found_cr}  |  Not found: {not_found}")
    print(f"Journal fields pre-cleaned: {cleaned_journals}")

    if args.dry_run:
        print("Dry run — not writing.")
        return 0

    write_bib(BIB_FILE, entries)
    print(f"Wrote {BIB_FILE} ({len(entries)} entries).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
