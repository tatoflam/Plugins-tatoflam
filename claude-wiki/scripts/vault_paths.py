#!/usr/bin/env python3
"""Resolve vault page references across the flat and the project-folder layouts.

03_work / 04_life hold one folder per project: <category>/NNN_<slug>/, with the
main page <slug>.md and optional sub-pages beside it (vault-project-folders).
References written before the move — `_projects.yml` v paths, digest
`target:` fields, old wiki-links — still say <category>/<slug>; resolve()
maps them to the project's main page, and falls back to a flat
<category>/<slug>.md so a vault that has not been migrated keeps working.

Usage:
  vault_paths.py resolve <ref> [<ref> ...]   # JSON {ref: path-or-null}
  vault_paths.py next <category>              # next free folder number, e.g. 035
  vault_paths.py projects [<category>]        # JSON list of project folders
"""
import json
import os
import re
import sys

VAULT = os.path.expanduser(os.environ.get("WIKI_VAULT", "~/repo/github/tatoflam/v"))
PROJECT_CATEGORIES = ("03_work", "04_life")
FOLDER_RE = re.compile(r"^(\d{3})_([a-z0-9][a-z0-9-]*)$")


def projects(category, vault=VAULT):
    """Project folders of a category, ordered by number."""
    base = os.path.join(vault, category)
    out = []
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        m = FOLDER_RE.match(name)
        if m and os.path.isdir(os.path.join(base, name)):
            out.append({"category": category, "number": m.group(1), "slug": m.group(2),
                        "folder": f"{category}/{name}",
                        "main": f"{category}/{name}/{m.group(2)}"})
    return out


def next_number(category, vault=VAULT):
    """Highest existing number + 1. Gaps are never refilled."""
    nums = [int(p["number"]) for p in projects(category, vault)]
    return f"{(max(nums) + 1) if nums else 1:03d}"


def _exists(rel, vault):
    return os.path.isfile(os.path.join(vault, rel + ".md"))


def resolve(ref, vault=VAULT):
    """Vault-relative page path (no .md) for a reference, or None if no page exists.

    Accepts `03_work/slug`, `03_work/NNN_slug`, `03_work/NNN_slug/page`, with
    or without `.md`, `#heading` or `|alias`. Non-project categories are
    returned as-is when the page exists.
    """
    ref = ref.strip().split("|", 1)[0].split("#", 1)[0].strip().strip("/")
    if ref.endswith(".md"):
        ref = ref[:-3]
    parts = ref.split("/")
    if parts[0] not in PROJECT_CATEGORIES or len(parts) < 2:
        return ref if _exists(ref, vault) else None
    category = parts[0]
    if len(parts) >= 3:  # category/NNN_slug/page — already a folder path
        if _exists(ref, vault):
            return ref
        m = FOLDER_RE.match(parts[1])
        slug, page = (m.group(2) if m else parts[1]), parts[-1]
    else:
        m = FOLDER_RE.match(parts[1])
        slug, page = (m.group(2) if m else parts[1]), None
    flat = f"{category}/{slug}"
    if _exists(flat, vault):
        return flat
    # own category first, then the other one (a project may have moved, e.g.
    # 04_life/sayama-* → 03_work/NNN_sorato-sayama/)
    cats = [category] + [c for c in PROJECT_CATEGORIES if c != category]
    for cat in cats:
        for p in projects(cat, vault):
            if p["slug"] == slug:
                cand = f"{p['folder']}/{page}" if page else p["main"]
                return cand if _exists(cand, vault) else (p["main"] if _exists(p["main"], vault) else None)
    # a sub-page referenced by its old flat path (e.g. 04_life/sayama-land-contract)
    for cat in cats:
        for p in projects(cat, vault):
            cand = f"{p['folder']}/{slug}"
            if _exists(cand, vault):
                return cand
    return None


def main(argv):
    if not argv or argv[0] not in ("resolve", "next", "projects"):
        print(__doc__, file=sys.stderr)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "resolve":
        print(json.dumps({r: resolve(r) for r in args}, ensure_ascii=False, indent=1))
    elif cmd == "next":
        print(next_number(args[0]))
    else:
        cats = args or list(PROJECT_CATEGORIES)
        print(json.dumps([p for c in cats for p in projects(c)], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
