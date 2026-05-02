#!/usr/bin/env python3
"""
Retry downloading PDFs that failed in download_pdfs.py.
Uses requests with browser-like headers, publisher-specific URL patterns,
and Semantic Scholar as a fallback.

Usage:
    python bin/retry_pdfs.py [--dry-run] [--bib PATH] [--pdf-dir PATH]
"""

import argparse
import os
import re
import time
import json
import requests

EMAIL = "sharathchandra92@gmail.com"
BIB_PATH = "_bibliography/papers.bib"
PDF_DIR = "assets/pdf"

# Full browser headers — most important for 403-blocked sites
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

UNPAYWALL = "https://api.unpaywall.org/v2/{doi}?email={email}"
S2_API    = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf,externalIds"

# ── BibTeX helpers (same as download_pdfs.py) ────────────────────────────────

ENTRY_RE = re.compile(r"@(\w+)\{([^,]+),\s*(.*?)\n\}", re.DOTALL)
FIELD_RE  = re.compile(r"^\s*(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}\s*,?\s*$", re.MULTILINE)


def parse_bib(text):
    entries = []
    for m in ENTRY_RE.finditer(text):
        raw   = m.group(0)
        etype = m.group(1).lower()
        key   = m.group(2).strip()
        body  = m.group(3)
        fields = {fm.group(1).lower(): fm.group(2) for fm in FIELD_RE.finditer(body)}
        entries.append((raw, etype, key, fields))
    return entries


def inject_pdf_field(entry_text, pdf_value):
    entry_text = re.sub(r"\n\s*pdf\s*=\s*\{[^}]*\}\s*,?", "", entry_text)
    entry_text = re.sub(r"\n\}$", f"\n  pdf = {{{pdf_value}}},\n}}", entry_text)
    return entry_text


# ── PDF finders ───────────────────────────────────────────────────────────────

def s2_pdf_url(doi, session):
    """Try Semantic Scholar API for open-access PDF URL."""
    try:
        r = session.get(S2_API.format(doi=doi), timeout=10)
        if r.status_code == 200:
            data = r.json()
            oa = data.get("openAccessPdf")
            if oa and oa.get("url"):
                return oa["url"]
    except Exception:
        pass
    return None


def unpaywall_all_urls(doi, session):
    """Return list of all pdf URLs from Unpaywall (not just best)."""
    try:
        r = session.get(UNPAYWALL.format(doi=doi, email=EMAIL), timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        urls = []
        for loc in (data.get("oa_locations") or []):
            u = loc.get("url_for_pdf") or loc.get("url")
            if u:
                urls.append(u)
        return list(dict.fromkeys(urls))  # dedupe, preserve order
    except Exception:
        return []


def pnas_pdf_url(doi):
    """PNAS open-access PDF — try several URL patterns."""
    base = doi.replace("10.1073/pnas.", "")
    return [
        f"https://www.pnas.org/doi/pdf/10.1073/pnas.{base}?download=true",
        f"https://www.pnas.org/doi/epdf/10.1073/pnas.{base}",
        f"https://www.pnas.org/content/pnas/{base.split('.')[0]}/{base.split('.')[-1]}/{base}.full.pdf",
    ]


def pmc_pdf_url(doi, session):
    """Resolve PMC article ID via NCBI eutils, then build PDF URL."""
    try:
        r = session.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pmc", "term": doi, "retmode": "json"},
            timeout=10,
        )
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if ids:
            pmcid = ids[0]
            return f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
    except Exception:
        pass
    return None


def osf_pdf_url(doi):
    """Build OSF/PsyArXiv direct download URL from DOI."""
    # DOIs like 10.31234/osf.io/XXXXX or 10.17605/osf.io/XXXXX
    m = re.search(r"osf\.io/([a-z0-9]+)(?:_v\d+)?", doi, re.I)
    if m:
        slug = m.group(1)
        return [
            f"https://osf.io/download/{slug}/",
            f"https://psyarxiv.com/{slug}/download",
        ]
    return []


def jama_pdf_url(doi, session):
    """JAMA Network Open – resolve article page then extract PDF link."""
    try:
        r = session.get(
            f"https://doi.org/{doi}",
            headers={**BROWSER_HEADERS, "Accept": "text/html"},
            timeout=15,
            allow_redirects=True,
        )
        # Look for PDF download link in the HTML
        m = re.search(r'href="(/journals/[^"]+articlepdf[^"]+)"', r.text)
        if m:
            return "https://jamanetwork.com" + m.group(1)
    except Exception:
        pass
    return None


def publisher_specific_urls(doi, session):
    """Return candidate PDF URLs based on publisher patterns."""
    urls = []
    if "pnas.org" in doi or doi.startswith("10.1073/pnas"):
        urls += pnas_pdf_url(doi)
    if "osf.io" in doi or "31234" in doi or "17605" in doi:
        urls += osf_pdf_url(doi)
    if "10.1001/jamanetwork" in doi:
        u = jama_pdf_url(doi, session)
        if u:
            urls.append(u)
    return urls


# ── PDF downloader ────────────────────────────────────────────────────────────

def try_download(session, pdf_url, dest_path):
    """Attempt download from url. Returns True on success."""
    try:
        r = session.get(
            pdf_url,
            headers=BROWSER_HEADERS,
            timeout=30,
            allow_redirects=True,
            stream=True,
        )
        if r.status_code != 200:
            print(f"    HTTP {r.status_code}")
            return False
        content_type = r.headers.get("Content-Type", "")
        data = r.content
        if b"%PDF" not in data[:8] and "pdf" not in content_type.lower():
            print(f"    Not a PDF ({content_type[:60]})")
            return False
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bib", default=BIB_PATH)
    ap.add_argument("--pdf-dir", default=PDF_DIR)
    args = ap.parse_args()

    os.makedirs(args.pdf_dir, exist_ok=True)

    bib_text = open(args.bib).read()
    entries  = parse_bib(bib_text)
    print(f"Parsed {len(entries)} entries\n")

    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    updated_bib = bib_text
    downloaded = skipped = failed = 0

    for raw, etype, key, fields in entries:
        doi = fields.get("doi", "").strip()
        if not doi:
            continue

        pdf_filename = re.sub(r"[^\w\-.]", "_", key) + ".pdf"
        pdf_path = os.path.join(args.pdf_dir, pdf_filename)

        # Skip if already downloaded
        if os.path.exists(pdf_path):
            skipped += 1
            continue

        # Check if bib already has a local pdf field pointing to a file
        existing_pdf = fields.get("pdf", "").strip()
        if existing_pdf and "://" not in existing_pdf:
            if os.path.exists(os.path.join(args.pdf_dir, existing_pdf)):
                skipped += 1
                continue

        print(f"[retry] {key}  doi:{doi}")

        # Collect candidate PDF URLs, most specific first
        candidates = []
        candidates += publisher_specific_urls(doi, session)

        # Semantic Scholar
        s2_url = s2_pdf_url(doi, session)
        if s2_url:
            print(f"  S2  → {s2_url[:80]}")
            candidates.append(s2_url)

        # All Unpaywall locations (not just best)
        uw_urls = unpaywall_all_urls(doi, session)
        for u in uw_urls:
            if u not in candidates:
                candidates.append(u)

        # PMC NCBI lookup
        pmc_url = pmc_pdf_url(doi, session)
        if pmc_url:
            candidates.append(pmc_url)

        time.sleep(0.3)

        if not candidates:
            print("  → no candidates found\n")
            failed += 1
            continue

        ok = False
        for url in candidates:
            print(f"  try → {url[:90]}")
            if args.dry_run:
                print("  [dry-run]\n")
                ok = True
                break
            ok = try_download(session, url, pdf_path)
            if ok:
                size_kb = os.path.getsize(pdf_path) // 1024
                print(f"  ✓ {pdf_filename} ({size_kb} KB)\n")
                new_raw = inject_pdf_field(raw, pdf_filename)
                updated_bib = updated_bib.replace(raw, new_raw, 1)
                downloaded += 1
                break

        if not ok:
            print("  ✗ all candidates failed\n")
            failed += 1

    if not args.dry_run and updated_bib != bib_text:
        with open(args.bib, "w") as f:
            f.write(updated_bib)
        print(f"Updated {args.bib}")

    print(f"\nDone: {downloaded} new, {skipped} already had PDF, {failed} still failed")


if __name__ == "__main__":
    main()
