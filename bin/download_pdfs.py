#!/usr/bin/env python3
"""
Download open-access PDFs for all papers in _bibliography/papers.bib
using the Unpaywall API, then update the bib file with pdf fields.

Usage:
    python bin/download_pdfs.py [--dry-run] [--bib PATH] [--pdf-dir PATH]
"""

import argparse
import os
import re
import time
import urllib.request
import urllib.error
import json

EMAIL = "sharathchandra92@gmail.com"  # required by Unpaywall
BIB_PATH = "_bibliography/papers.bib"
PDF_DIR = "assets/pdf"
UNPAYWALL = "https://api.unpaywall.org/v2/{doi}?email={email}"
HEADERS = {"User-Agent": f"scholarly-pdf-downloader/1.0 (mailto:{EMAIL})"}

# ── BibTeX parser ────────────────────────────────────────────────────────────

ENTRY_RE = re.compile(
    r"@(\w+)\{([^,]+),\s*(.*?)\n\}",
    re.DOTALL,
)
FIELD_RE = re.compile(
    r"^\s*(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}\s*,?\s*$",
    re.MULTILINE,
)


def parse_bib(text):
    """Return list of (entry_text, entry_type, key, fields_dict)."""
    entries = []
    for m in ENTRY_RE.finditer(text):
        raw = m.group(0)
        etype = m.group(1).lower()
        key = m.group(2).strip()
        body = m.group(3)
        fields = {}
        for fm in FIELD_RE.finditer(body):
            fields[fm.group(1).lower()] = fm.group(2)
        entries.append((raw, etype, key, fields))
    return entries


def inject_pdf_field(entry_text, pdf_value):
    """Add or replace the pdf field in a bib entry string."""
    # Remove existing pdf field if present
    entry_text = re.sub(
        r"\n\s*pdf\s*=\s*\{[^}]*\}\s*,?", "", entry_text
    )
    # Insert before closing brace
    entry_text = re.sub(
        r"\n\}$",
        f"\n  pdf = {{{pdf_value}}},\n}}",
        entry_text,
    )
    return entry_text


# ── Unpaywall lookup ─────────────────────────────────────────────────────────

def unpaywall_pdf_url(doi):
    """Return (pdf_url, host) or (None, None) from Unpaywall."""
    url = UNPAYWALL.format(doi=doi, email=EMAIL)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        # prefer best_oa_location, then any oa_location with pdf
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf")
        host = best.get("host_type", "")
        if not pdf_url:
            for loc in (data.get("oa_locations") or []):
                if loc.get("url_for_pdf"):
                    pdf_url = loc["url_for_pdf"]
                    host = loc.get("host_type", "")
                    break
        return pdf_url, host
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None   # DOI not in Unpaywall
        print(f"  [warn] Unpaywall HTTP {e.code} for {doi}")
        return None, None
    except Exception as e:
        print(f"  [warn] Unpaywall error for {doi}: {e}")
        return None, None


# ── PDF download ─────────────────────────────────────────────────────────────

def download_pdf(pdf_url, dest_path):
    """Download pdf_url → dest_path. Returns True on success."""
    req = urllib.request.Request(pdf_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
        # Reject HTML masquerading as PDF
        if b"%PDF" not in data[:8] and "pdf" not in content_type.lower():
            print(f"  [skip] Not a PDF ({content_type}): {pdf_url}")
            return False
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  [fail] Download error: {e}")
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
    entries = parse_bib(bib_text)

    print(f"Parsed {len(entries)} entries from {args.bib}")

    updated_bib = bib_text
    downloaded = 0
    skipped_no_doi = 0
    skipped_no_oa = 0
    skipped_exists = 0
    failed = 0

    for raw, etype, key, fields in entries:
        doi = fields.get("doi", "").strip()
        if not doi:
            skipped_no_doi += 1
            continue

        # Already has a local pdf field pointing to a local file?
        existing_pdf = fields.get("pdf", "").strip()
        if existing_pdf and "://" not in existing_pdf:
            pdf_path = os.path.join(args.pdf_dir, existing_pdf)
            if os.path.exists(pdf_path):
                print(f"[exists] {key}: {existing_pdf}")
                skipped_exists += 1
                continue

        pdf_filename = re.sub(r"[^\w\-.]", "_", key) + ".pdf"
        pdf_path = os.path.join(args.pdf_dir, pdf_filename)

        # Skip if already downloaded
        if os.path.exists(pdf_path):
            print(f"[exists] {key}: {pdf_filename}")
            skipped_exists += 1
            # Still make sure bib has the pdf field
            if "pdf" not in fields:
                new_raw = inject_pdf_field(raw, pdf_filename)
                updated_bib = updated_bib.replace(raw, new_raw, 1)
            continue

        print(f"[lookup] {key} — doi:{doi}")
        pdf_url, host = unpaywall_pdf_url(doi)
        time.sleep(0.3)  # be polite to Unpaywall

        if not pdf_url:
            print(f"  → no open-access PDF found")
            skipped_no_oa += 1
            continue

        print(f"  → {host}: {pdf_url}")

        if args.dry_run:
            print(f"  [dry-run] would download → {pdf_filename}")
            downloaded += 1
            continue

        ok = download_pdf(pdf_url, pdf_path)
        if ok:
            size_kb = os.path.getsize(pdf_path) // 1024
            print(f"  ✓ saved {pdf_filename} ({size_kb} KB)")
            new_raw = inject_pdf_field(raw, pdf_filename)
            updated_bib = updated_bib.replace(raw, new_raw, 1)
            downloaded += 1
        else:
            failed += 1

    if not args.dry_run and updated_bib != bib_text:
        with open(args.bib, "w") as f:
            f.write(updated_bib)
        print(f"\nUpdated {args.bib} with pdf fields.")

    print(
        f"\nDone: {downloaded} downloaded, {skipped_exists} already existed, "
        f"{skipped_no_oa} no OA PDF, {skipped_no_doi} no DOI, {failed} failed"
    )


if __name__ == "__main__":
    main()
