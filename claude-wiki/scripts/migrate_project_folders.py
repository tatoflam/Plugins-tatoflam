#!/usr/bin/env python3
"""One-off migration: flat 03_work/04_life pages → numbered project folders.

  migrate_project_folders.py --plan  --groups groups.json --out mapping.md
  migrate_project_folders.py --apply --mapping mapping.md [--drafts DIR] [--dry-run]

--plan numbers every project by its first recorded date and writes a
reviewable mapping table. groups.json bundles several pages into one
project and assigns deliverable files:

  {"projects": [{"category": "03_work", "slug": "sayama-ap",
                 "pages": ["04_life/sayama-land-contract", ...]}],
   "files": {"06_output/files/2026-10/pqc-aws-report.html": "03_work/pqc-aws-advisory"}}

First recorded date = the earliest of: the session-start dates of the
page's `sources:` (from digest filenames in _staging/archive/), the
earliest dated line under `## 経緯`, and the first 02_diary day that links
to the page; else the page's `updated:`. Dates inside body text are not used (contract
dates, deadlines etc. would skew the order).

--apply reads the (possibly hand-edited) mapping.md and, inside the vault:
git-mv pages and files, copies main pages for bundles from --drafts,
rewrites [[03_work|04_life/...]] and moved-file links in every .md
(keeping #heading and |alias; frontmatter target: is left alone), and
prints dangling-link counts before/after. It does not commit.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_paths  # noqa: E402

VAULT = vault_paths.VAULT
CATS = vault_paths.PROJECT_CATEGORIES
LINK_RE = re.compile(r"\[\[((?:03_work|04_life)/[^\]|#]+?)(\.md)?([#|][^\]]*)?\]\]")
FILE_LINK_RE = re.compile(r"\[\[(06_output/files/[^\]|#]+)([#|][^\]]*)?\]\]")
DATE_RE = re.compile(r"(20\d\d-\d\d-\d\d)")
SKIP_DIRS = {".git", ".obsidian", ".claude", "openspec", "node_modules"}


def read(rel):
    with open(os.path.join(VAULT, rel), encoding="utf-8") as f:
        return f.read()


def session_dates():
    """session id8 → earliest digest filename date (session start)."""
    out = {}
    for p in glob.glob(os.path.join(VAULT, "_staging/archive/*.md")) + glob.glob(os.path.join(VAULT, "_staging/*.md")):
        m = re.match(r"(\d{4}-\d{2}-\d{2})-([0-9a-f]{8})", os.path.basename(p))
        if m:
            d, sid = m.groups()
            out[sid] = min(out.get(sid, d), d)
    return out


def diary_dates():
    """page ref "cat/slug" → earliest 02_diary date that links to it."""
    out = {}
    for p in glob.glob(os.path.join(VAULT, "02_diary", "*.md")):
        d = os.path.basename(p)[:10]
        if not DATE_RE.fullmatch(d):
            continue
        for m in LINK_RE.finditer(open(p, encoding="utf-8").read()):
            ref = m.group(1).rstrip("/")
            out[ref] = min(out.get(ref, d), d)
    return out


def first_date(rel, sdates, ddates):
    """Earliest of: sources' session-start dates, dated lines under 経緯,
    the first diary that links to the page. Falls back to updated:."""
    text = read(rel + ".md")
    cands = []
    m = re.search(r"^sources:\s*\[(.*)\]\s*$", text, re.M)
    if m:
        for s_ in m.group(1).split(","):
            sid = s_.strip().strip("'\"")[:8]
            if sid in sdates:
                cands.append((sdates[sid], f"source {sid}"))
    hist = re.search(r"^## 経緯\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if hist:
        ds = DATE_RE.findall(hist.group(1))
        if ds:
            cands.append((min(ds), "経緯"))
    if rel in ddates:
        cands.append((ddates[rel], "diary"))
    if cands:
        return min(cands)
    up = re.search(r"^updated:\s*(\S+)", text, re.M)
    return (up.group(1) if up else "9999-12-31"), "updated"


def plan(groups_path, out_path):
    groups = json.load(open(groups_path)) if groups_path else {"projects": [], "files": {}}
    sdates = session_dates()
    ddates = diary_dates()
    grouped = {}
    for g in groups.get("projects", []):
        for p in g["pages"]:
            grouped[p] = g
    projects = {}  # (category, slug) → {"pages": [...], "date":..., "basis":...}
    for cat in CATS:
        for path in sorted(glob.glob(os.path.join(VAULT, cat, "*.md"))):
            rel = os.path.relpath(path, VAULT)[:-3]
            g = grouped.get(rel)
            key = (g["category"], g["slug"]) if g else (cat, os.path.basename(rel))
            d, basis = first_date(rel, sdates, ddates)
            pr = projects.setdefault(key, {"pages": [], "date": d, "basis": f"{basis} ({rel})"})
            pr["pages"].append(rel)
            if d < pr["date"]:
                pr["date"], pr["basis"] = d, f"{basis} ({rel})"
    for g in groups.get("projects", []):
        missing = [p for p in g["pages"] if p not in projects.get((g["category"], g["slug"]), {}).get("pages", [])]
        if missing:
            sys.exit(f"group {g['slug']}: pages not found: {missing}")
    lines = ["# 移行対応表（vault-project-folders）", "",
             "番号は最初の記録日（sources のセッション開始日 → 経緯 → updated）の順。",
             "この表を直してから `--apply --mapping` に渡す。列: 番号 | 新フォルダ | 主ページ | 旧ページ（; 区切り） | 根拠日 | 根拠", ""]
    for cat in CATS:
        rows = sorted(((v["date"], k[1], v) for k, v in projects.items() if k[0] == cat))
        lines += [f"## {cat}", "", "| 番号 | フォルダ | 主ページ | 旧ページ | 根拠日 | 根拠 |", "|---|---|---|---|---|---|"]
        for i, (d, slug, v) in enumerate(rows, 1):
            folder = f"{cat}/{i:03d}_{slug}"
            lines.append(f"| {i:03d} | {folder} | {slug} | {'; '.join(v['pages'])} | {d} | {v['basis']} |")
        lines.append("")
    lines += ["## files", "", "| 旧パス | 案件（category/slug） |", "|---|---|"]
    for src, proj in sorted(groups.get("files", {}).items()):
        lines.append(f"| {src} | {proj} |")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {out_path}: {sum(1 for k in projects if k[0]=='03_work')} work, "
          f"{sum(1 for k in projects if k[0]=='04_life')} life projects")


def parse_mapping(path):
    projects, files = [], []
    section = None
    for line in open(path, encoding="utf-8"):
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if not line.startswith("| ") or line.startswith("| 番号") or line.startswith("| 旧パス") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if section in CATS:
            num, folder, main, pages = cells[:4]
            projects.append({"folder": folder, "main": main, "pages": [p.strip() for p in pages.split(";") if p.strip()]})
        elif section == "files":
            files.append((cells[0], cells[1]))
    return projects, files


def md_files():
    for root, dirs, fs in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in fs:
            if f.endswith(".md"):
                yield os.path.join(root, f)


def dangling():
    n = 0
    for p in md_files():
        for m in LINK_RE.finditer(open(p, encoding="utf-8").read()):
            if not vault_paths.resolve(m.group(1)):
                n += 1
    return n


def git(*args, dry=False):
    if dry:
        print("git", *args)
        return
    subprocess.run(["git", "-C", VAULT, *args], check=True)


def apply(mapping_path, drafts, dry):
    projects, files = parse_mapping(mapping_path)
    before = dangling()
    page_map = {}   # old "cat/slug" and "slug" → new "cat/NNN_x/page"
    by_project = {}  # "cat/slug" of the project → folder
    for pr in projects:
        folder = pr["folder"]
        cat, name = folder.split("/", 1)
        slug = vault_paths.FOLDER_RE.match(name).group(2)
        by_project[f"{cat}/{slug}"] = folder
        os.makedirs(os.path.join(VAULT, folder), exist_ok=True) if not dry else None
        for old in pr["pages"]:
            page = os.path.basename(old)
            new = f"{folder}/{page}"
            git("mv", old + ".md", new + ".md", dry=dry)
            for c in CATS:
                page_map[f"{c}/{page}"] = new
        main = f"{folder}/{pr['main']}"
        if not dry and not os.path.exists(os.path.join(VAULT, main + ".md")):
            src = os.path.join(drafts or "", pr["main"] + ".md")
            if not drafts or not os.path.exists(src):
                sys.exit(f"{folder}: main page {pr['main']}.md is missing and no draft in --drafts")
            with open(src, encoding="utf-8") as f, open(os.path.join(VAULT, main + ".md"), "w", encoding="utf-8") as g:
                g.write(f.read())
            git("add", main + ".md")
        for c in CATS:  # the project's own slug (e.g. 03_work/sayama-ap) → main page
            page_map.setdefault(f"{c}/{slug}", main)
    file_map = {}
    for src, proj in files:
        folder = by_project.get(proj) or by_project.get(proj.split("/", 1)[0] + "/" + proj.split("/", 1)[1])
        if not folder:
            sys.exit(f"files: unknown project {proj} for {src}")
        dst = f"{folder}/files/{os.path.basename(src)}"
        if not dry:
            os.makedirs(os.path.join(VAULT, folder, "files"), exist_ok=True)
        git("mv", src, dst, dry=dry)
        file_map[src] = dst

    def fix(text):
        def page_sub(m):
            ref, ext, tail = m.group(1), m.group(2) or "", m.group(3) or ""
            new = page_map.get(ref.rstrip("/"))
            return f"[[{new}{tail}]]" if new else m.group(0)

        def file_sub(m):
            new = file_map.get(m.group(1))
            return f"[[{new}{m.group(2) or ''}]]" if new else m.group(0)
        return FILE_LINK_RE.sub(file_sub, LINK_RE.sub(page_sub, text))

    changed = 0
    for p in md_files():
        t = open(p, encoding="utf-8").read()
        n = fix(t)
        if n != t:
            changed += 1
            if not dry:
                open(p, "w", encoding="utf-8").write(n)
    after = dangling() if not dry else None
    print(json.dumps({"projects": len(projects), "pages_moved": sum(len(p["pages"]) for p in projects),
                      "files_moved": len(file_map), "md_rewritten": changed,
                      "dangling_before": before, "dangling_after": after}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--groups")
    ap.add_argument("--out", default="mapping.md")
    ap.add_argument("--mapping")
    ap.add_argument("--drafts")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.plan:
        plan(a.groups, a.out)
    elif a.apply:
        if not a.mapping:
            ap.error("--apply needs --mapping")
        apply(a.mapping, a.drafts, a.dry_run)
    else:
        ap.error("--plan or --apply")


if __name__ == "__main__":
    main()
