"""
Fetches current lab members from the CSL Lab website
(csl-lab-upenn.github.io) and saves them as YAML data.
Excludes investigators (PI and Co-PI).
"""

import json
import yaml
from urllib.request import Request, urlopen
from pathlib import Path


LAB_SITE = "https://csl-lab-upenn.github.io"
OUTPUT_FILE = "_data/lab-members.yaml"


def fetch_page(url):
    """Fetch a page and return its text content."""
    request = Request(url=url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(request).read().decode("utf-8")


def parse_members_from_html(html):
    """
    Parse member info from the CSL lab team page HTML.
    Looks for member cards with name, role, and image.
    """
    members = []

    # Simple HTML parsing - look for member patterns
    # The lab site uses a consistent structure for team members
    import re

    # Find all member blocks - they contain image, name, role
    # Pattern: <img src="/images/Name.ext" ... > followed by name and role text
    # The site uses a card-based layout

    # Find image tags with /images/ paths
    img_pattern = re.compile(
        r'<img[^>]*src="(/images/[^"]+)"[^>]*>',
        re.IGNORECASE
    )

    # Find member sections - look for the team page structure
    # Each member has: image, name (h4 or strong), role (p or span)
    member_pattern = re.compile(
        r'<img[^>]*src="(/images/([^"]+))"[^>]*>.*?'
        r'(?:<h\d[^>]*>|<strong>|<b>)\s*([^<]+)\s*(?:</h\d>|</strong>|</b>).*?'
        r'(?:<p[^>]*>|<span[^>]*>|<small>)\s*([^<]+)\s*(?:</p>|</span>|</small>)',
        re.DOTALL | re.IGNORECASE
    )

    for match in member_pattern.finditer(html):
        image_path = match.group(1)
        name = match.group(3).strip()
        role = match.group(4).strip()

        # Skip investigators
        if "Investigator" in role or "Principal" in role:
            continue

        members.append({
            "name": name,
            "role": role,
            "image": f"{LAB_SITE}{image_path}",
        })

    return members


def main():
    print("Fetching lab members from CSL Lab website...")

    try:
        html = fetch_page(f"{LAB_SITE}/team/")
    except Exception:
        try:
            html = fetch_page(f"{LAB_SITE}/")
        except Exception as e:
            print(f"Error fetching lab website: {e}")
            return

    members = parse_members_from_html(html)

    if not members:
        print("WARNING: No members found. Keeping existing data.")
        return

    # Save to YAML
    path = Path(OUTPUT_FILE)
    note = "# DO NOT EDIT, GENERATED AUTOMATICALLY FROM CSL LAB WEBSITE\n\n"
    with open(path, "w") as f:
        f.write(note)
        yaml.dump(members, f, default_flow_style=False, sort_keys=False)

    print(f"Saved {len(members)} lab members to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
