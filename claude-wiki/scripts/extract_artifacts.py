#!/usr/bin/env python3
"""Extract deliverables (artifacts) from Claude Code transcripts and keep a
machine-owned monthly catalog in the vault.

What counts as a deliverable:
  - Write/Edit of a document-type file (html pdf docx pptx xlsx csv png svg)
    outside scratch/temp dirs and outside ~/.claude
  - Artifact publish results ("Published <path> at <url>")
  - PR URLs printed by `gh pr create`
  - Hosting URLs printed by `wrangler pages deploy` / `firebase deploy`
Code edits themselves are not deliverables.

Catalog line (one per deliverable, key = path or URL):
  - 2026-10-24 | html | <title> | <path-or-url> | <repo> | session:<id8>[,<id8>…]

Usage:
  extract_artifacts.py --transcript F [--offset N]            # JSON to stdout
  extract_artifacts.py --transcript F --catalog-dir D --write # merge into catalog
  extract_artifacts.py --vault-files --write                    # register 06_output/files/* and <project>/files/*
  extract_artifacts.py --scan ~/.claude/projects --since 2026-08-18 \
      --capture-conf ~/.claude/wiki/config/capture.conf --catalog-dir D --write
"""
import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import subprocess
import sys

DOC_EXT = {".html", ".htm", ".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".png", ".svg"}
HOME = os.path.expanduser("~")
VAULT = os.path.expanduser(os.environ.get("WIKI_VAULT", "~/repo/github/tatoflam/v"))
# App source trees are code, not deliverables.
SKIP_PARTS = ("/src/", "/public/", "/static/", "/templates/", "/components/", "/node_modules/",
              "/dist/", "/build/", "/site/", "/.venv/", "/test", "/fixtures/", "/.playwright-mcp/")
SKIP_NAMES = {"index.html", "template.html", "404.html"}
SKIP_PREFIXES = ("/tmp/", "/private/tmp/", "/private/var/", "/var/folders/", HOME + "/.claude/")
PUBLISHED_RE = re.compile(r"Published (\S+) at (https://claude\.ai/\S+?)(?=[\s\"\\]|$)")
PR_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
DEPLOY_RE = re.compile(r"https://[\w.-]+\.(?:pages\.dev|web\.app|firebaseapp\.com)(?:/[\w./-]*)?")
JST = dt.timezone(dt.timedelta(hours=9))


def vault_file_globs():
    """Where deliverables made inside the vault live: project folders' files/
    (03_work|04_life/NNN_slug/files/**) and 06_output/files/YYYY-MM/ for the rest."""
    return [os.path.join(VAULT, "06_output/files/*/*"),
            os.path.join(VAULT, "0[34]_*/[0-9][0-9][0-9]_*/files/**/*")]


def jst_date(ts):
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST).date().isoformat()
    except Exception:
        return dt.datetime.now(JST).date().isoformat()


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(text_of(c.get("text", "") if isinstance(c, dict) else c) for c in content)
    return ""


def html_title(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            head = f.read(20000)
        m = re.search(r"<title[^>]*>(.*?)</title>", head, re.S | re.I)
        if m:
            return html.unescape(re.sub(r"\s+", " ", m.group(1)).strip())
    except OSError:
        pass
    return os.path.basename(path)


def repo_of(path):
    d = path if os.path.isdir(path) else os.path.dirname(path)
    while d and not os.path.isdir(d):
        d = os.path.dirname(d)
    try:
        top = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        if not top:
            return ""
        url = subprocess.run(["git", "-C", top, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        m = re.search(r"[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", url)
        name = m.group(1) if m else os.path.basename(top)
        h = subprocess.run(["git", "-C", top, "log", "-1", "--format=%h", "--", path],
                           capture_output=True, text=True, timeout=5).stdout.strip()
        return f"{name}@{h}" if h else name
    except Exception:
        return ""


def display_path(path):
    if path.startswith(VAULT + "/"):
        return "[[" + path[len(VAULT) + 1:] + "]]"
    return path


def extract(transcript, offset=0):
    found = {}
    pending = {}  # tool_use_id -> (name, input, ts)
    session = os.path.splitext(os.path.basename(transcript))[0]
    with open(transcript, "rb") as f:
        f.seek(offset)
        for raw in f:
            try:
                o = json.loads(raw)
            except Exception:
                continue
            msg = o.get("message")
            if not isinstance(msg, dict) or not isinstance(msg.get("content"), list):
                continue
            ts = o.get("timestamp", "")
            for b in msg["content"]:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    name, inp = b.get("name", ""), b.get("input") or {}
                    if name in ("Write", "Edit"):
                        p = inp.get("file_path", "")
                        if (os.path.splitext(p)[1].lower() in DOC_EXT and not p.startswith(SKIP_PREFIXES)
                                and not any(x in p for x in SKIP_PARTS)
                                and os.path.basename(p) not in SKIP_NAMES):
                            found.setdefault(p, {"kind": os.path.splitext(p)[1][1:].lower(), "key": p,
                                                 "date": jst_date(ts), "local": p})
                    elif name == "Artifact" and inp.get("action", "publish") == "publish" and inp.get("file_path"):
                        pending[b.get("id")] = (name, inp, ts)
                    elif name == "Bash":
                        cmd = inp.get("command", "")
                        if "gh pr create" in cmd or re.search(r"(wrangler\s+pages\s+deploy|firebase\s+deploy)", cmd):
                            pending[b.get("id")] = (name, inp, ts)
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                    name, inp, ts0 = pending.pop(b["tool_use_id"])
                    out = text_of(b.get("content"))
                    if name == "Artifact":
                        m = PUBLISHED_RE.search(out)
                        if m:
                            url = m.group(2)
                            found[url] = {"kind": "artifact", "key": url, "date": jst_date(ts0),
                                          "local": inp.get("file_path"),
                                          "title": inp.get("title") or (inp.get("description") or "")[:40]}
                    else:
                        for url in PR_RE.findall(out) if "gh pr create" in inp.get("command", "") else []:
                            found.setdefault(url, {"kind": "pr", "key": url, "date": jst_date(ts0)})
                        for url in DEPLOY_RE.findall(out):
                            found.setdefault(url, {"kind": "deploy", "key": url, "date": jst_date(ts0)})
    items = []
    for it in found.values():
        local = it.get("local")
        if it["kind"] == "pr":
            m = re.search(r"github\.com/([\w.-]+/([\w.-]+))/pull/(\d+)", it["key"])
            it["title"], it["repo"] = f"{m.group(2)}#{m.group(3)}", m.group(1)
        elif it["kind"] == "deploy":
            it["title"] = it["key"].split("://", 1)[1].split("/")[0]
            it["repo"] = ""
        else:
            if it["kind"] != "artifact" and local and not os.path.exists(local):
                moved = [m for g in vault_file_globs() for m in glob.glob(g, recursive=True)
                         if os.path.basename(m) == os.path.basename(local)]
                if moved:
                    it["key"] = it["local"] = local = moved[0]
                else:
                    it["note"] = "missing"
            if it["kind"] == "artifact" and local and os.path.isabs(local) and os.path.exists(local) and local.endswith((".html", ".htm")):
                it["title"] = html_title(local)
            if not it.get("title"):
                it["title"] = html_title(local) if local and local.endswith((".html", ".htm")) else os.path.basename(local or it["key"])
            it["repo"] = repo_of(local) if local and it["kind"] != "artifact" else ""
        it["session"] = session[:8]
        items.append(it)
    return items


LINE_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) \| (\w+) \| (.*?) \| (.*?) \| (.*?) \| session:([\w,]+)\s*$")


def load_catalog(catalog_dir):
    rows = {}  # key -> (file, idx)
    files = {}
    for path in sorted(glob.glob(os.path.join(catalog_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        files[path] = lines
        for i, line in enumerate(lines):
            m = LINE_RE.match(line)
            if m:
                rows[m.group(4)] = (path, i)
    return rows, files


HEADER = """---
title: {month} 成果物カタログ（自動）
category: 06_output
tags: [type:catalog]
---

# {month} 成果物カタログ

> [!info] 機械専用
> /wiki-ingest が transcript から抽出して追記する。手で編集しない。人向けのまとめは [[06_output/{month}]]。
> 書式: 日付 | 種別 | タイトル | パス or URL | リポジトリ@コミット | セッション

"""


def write_catalog(catalog_dir, items):
    os.makedirs(catalog_dir, exist_ok=True)
    rows, files = load_catalog(catalog_dir)
    added = updated = 0
    for it in sorted(items, key=lambda x: x["date"]):
        disp = it["key"] if it["kind"] in ("artifact", "pr", "deploy") else display_path(it["key"])
        title = it["title"].replace("|", "／")
        if it.get("kind") == "artifact" and it.get("local"):
            title += f" ({os.path.basename(it['local'])})"
        if disp in rows:
            path, i = rows[disp]
            m = LINE_RE.match(files[path][i])
            sessions = m.group(6).split(",")
            if it["session"] not in sessions:
                sessions.append(it["session"])
            new = f"- {max(m.group(1), it['date'])} | {m.group(2)} | {m.group(3)} | {disp} | {it['repo'] or m.group(5)} | session:{','.join(sessions)}"
            if new != files[path][i]:
                files[path][i] = new
                updated += 1
            continue
        month = it["date"][:7]
        path = os.path.join(catalog_dir, f"{month}.md")
        if path not in files:
            files[path] = HEADER.format(month=month).splitlines()
        files[path].append(f"- {it['date']} | {it['kind']} | {title} | {disp} | {it['repo']} | session:{it['session']}")
        rows[disp] = (path, len(files[path]) - 1)
        added += 1
    for path, lines in files.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return added, updated


def capture_rules(conf):
    allow, deny = [], []
    if conf and os.path.exists(conf):
        for line in open(conf, encoding="utf-8"):
            parts = line.split()
            if len(parts) == 2 and parts[0] in ("allow", "deny"):
                (allow if parts[0] == "allow" else deny).append(parts[1].rstrip("/"))
    return allow, deny


def transcript_cwd(path):
    with open(path, "rb") as f:
        for raw in f:
            try:
                o = json.loads(raw)
            except Exception:
                continue
            if o.get("cwd"):
                return o["cwd"]
    return ""


def allowed(cwd, allow, deny):
    under = lambda p: cwd == p or cwd.startswith(p + "/")
    if any(under(p) for p in deny):
        return False
    return any(under(p) for p in allow)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--scan")
    ap.add_argument("--since")
    ap.add_argument("--capture-conf", default=os.path.join(HOME, ".claude/wiki/config/capture.conf"))
    ap.add_argument("--catalog-dir", default=os.path.join(VAULT, "06_output/catalog"))
    ap.add_argument("--vault-files", action="store_true",
                    help="also register files under <vault>/06_output/files/ and project folders' files/ that no transcript produced")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    items = []
    if a.transcript:
        items = extract(a.transcript, a.offset)
    elif a.scan:
        allow, deny = capture_rules(a.capture_conf)
        since = dt.date.fromisoformat(a.since) if a.since else dt.date.min
        for t in glob.glob(os.path.join(os.path.expanduser(a.scan), "*", "*.jsonl")):
            if dt.date.fromtimestamp(os.path.getmtime(t)) < since:
                continue
            if not allowed(transcript_cwd(t), allow, deny):
                continue
            items += [i for i in extract(t) if i["date"] >= since.isoformat()]
    elif not a.vault_files:
        ap.error("--transcript, --scan or --vault-files is required")
    if a.vault_files:
        seen = {i["key"] for i in items}
        for p in sorted({m for g in vault_file_globs() for m in glob.glob(g, recursive=True)}):
            if p in seen or os.path.splitext(p)[1].lower() not in DOC_EXT:
                continue
            d = dt.datetime.fromtimestamp(os.path.getmtime(p), JST).date().isoformat()
            items.append({"kind": os.path.splitext(p)[1][1:].lower(), "key": p, "local": p, "date": d,
                          "title": html_title(p) if p.endswith((".html", ".htm")) else os.path.basename(p),
                          "repo": repo_of(p), "session": "manual"})

    if a.write:
        added, updated = write_catalog(a.catalog_dir, items)
        print(json.dumps({"found": len(items), "added": added, "updated": updated}, ensure_ascii=False))
    else:
        json.dump(items, sys.stdout, ensure_ascii=False, indent=1)
        print()


if __name__ == "__main__":
    main()
