#!/usr/bin/env python3
"""
Sync current lab members into _data/lab-members.yaml from the CSL lab site repo.

Reads each _members/*.md front matter from csl-lab-upenn/csl-lab-upenn.github.io
(the lab site's source of truth) instead of scraping its rendered HTML.

Included: members whose `group` is not `alum`, excluding the PI and
investigators (this site is the PI's own page). Ordered and labelled using
the lab site's own member_roles.yaml and types.yaml.

Usage:
  python bin/sync_lab_members.py            # write _data/lab-members.yaml
  python bin/sync_lab_members.py --dry-run  # print, don't write
"""

import argparse
import os
import re
import sys

import requests
import yaml

REPO = "csl-lab-upenn/csl-lab-upenn.github.io"
BRANCH = "main"
SITE = "https://csl-lab-upenn.github.io"
OUT = "_data/lab-members.yaml"
EXCLUDED_ROLES = {"pi", "coi"}
NO_PHOTO = {"", "images/fallback.svg"}

session = requests.Session()
if os.environ.get("GITHUB_TOKEN"):
    session.headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"


def raw(path):
    r = session.get(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{path}", timeout=30)
    r.raise_for_status()
    return r.text


def front_matter(text):
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    return yaml.safe_load(m.group(1)) if m else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    role_order = yaml.safe_load(raw("_data/member_roles.yaml"))
    role_labels = {
        k: v["description"]
        for k, v in yaml.safe_load(raw("_data/types.yaml")).items()
        if isinstance(v, dict) and "description" in v
    }

    listing = session.get(
        f"https://api.github.com/repos/{REPO}/contents/_members?ref={BRANCH}", timeout=30
    )
    listing.raise_for_status()

    members = []
    for item in listing.json():
        if not item["name"].endswith(".md"):
            continue
        fm = front_matter(raw(f"_members/{item['name']}"))
        role = fm.get("role")
        if fm.get("group") == "alum" or role in EXCLUDED_ROLES or not fm.get("name"):
            continue
        image = fm.get("image", "")
        member = {
            "name": fm["name"],
            "role": role_labels.get(role, role),
            "_rank": role_order.index(role) if role in role_order else len(role_order),
        }
        if image not in NO_PHOTO:
            member["image"] = f"{SITE}/{image.lstrip('/')}"
        members.append(member)

    if not members:
        print("No members found, keeping existing file", file=sys.stderr)
        return 1

    members.sort(key=lambda m: (m["_rank"], m["name"]))
    for m in members:
        del m["_rank"]

    print(f"{len(members)} current members:")
    for m in members:
        print(f"  {m['name']} — {m['role']}" + ("" if "image" in m else " (no photo)"))

    if args.dry_run:
        return 0

    with open(OUT, "w") as f:
        f.write("# DO NOT EDIT, GENERATED AUTOMATICALLY FROM CSL LAB WEBSITE\n\n")
        yaml.dump(members, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
