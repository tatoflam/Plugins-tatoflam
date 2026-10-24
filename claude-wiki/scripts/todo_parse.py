#!/usr/bin/env python3
"""Parse a todo repository of weekly markdown files into JSON.

Weekly files are named YYYYMMDD-MMDD.md (start date - end month/day). The
week a file covers comes from the filename only; the H1 inside is ignored
because it is often stale after copy-forward.

Every bullet is an item; its `path` is the chain of ancestor bullet texts.
Optional conventions understood (none are required):
  (〆10/15)        due date
  - [x] ...       done (also `~~text~~`)
  ⭐ / ⭐️          starred

Item identity across weeks = normalized path. `first_seen` is the start of
the contiguous run of weeks (ending at the target week) in which the item
appears, so an item that was dropped and re-added restarts its age.

Usage:
  todo_parse.py --todo-dir DIR [--date YYYY-MM-DD | --file NAME] [--projects]
  todo_parse.py --todo-dir DIR --list-weeks

--projects attaches mapped vault pages/tags from DIR/_projects.yml and lists
headings that have no mapping (`unmapped`).
"""
import argparse
import datetime as dt
import fnmatch
import json
import os
import re
import sys

WEEK_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})\.md$")
BULLET_RE = re.compile(r"^(\s*)[-*+]\s+(.*\S)?\s*$")
DUE_RE = re.compile(r"[（(]\s*〆\s*(\d{1,2})/(\d{1,2})\s*[)）]")
UNTIL_RE = re.compile(r"(\d{1,2})/(\d{1,2})\s*まで")
DATE_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])")
STAR = "⭐"
SEP = " › "


def list_weeks(todo_dir):
    weeks = []
    for name in os.listdir(todo_dir):
        m = WEEK_RE.match(name)
        if not m:
            continue
        y, mo, d, emo, ed = map(int, m.groups())
        try:
            start = dt.date(y, mo, d)
        except ValueError:
            continue  # template files like 20260000_template.md
        ey = y + 1 if emo < mo else y
        try:
            end = dt.date(ey, emo, ed)
        except ValueError:
            continue
        weeks.append({"file": name, "start": start, "end": end})
    weeks.sort(key=lambda w: w["start"])
    return weeks


def pick_week(weeks, date=None, file=None):
    if file:
        for w in weeks:
            if w["file"] == file:
                return w
        raise SystemExit(f"week file not found: {file}")
    date = date or dt.date.today()
    covering = [w for w in weeks if w["start"] <= date <= w["end"]]
    if covering:
        return covering[-1]
    earlier = [w for w in weeks if w["start"] <= date]
    if not earlier:
        raise SystemExit(f"no week file on or before {date}")
    return earlier[-1]


def normalize(text):
    t = text.replace("️", "").replace(STAR, "")
    t = re.sub(r"^\[[ xX]\]\s*", "", t)
    t = t.replace("~~", "")
    t = DUE_RE.sub("", t)
    t = re.sub(r"[\s　、。,.:：・!！?？]+", "", t)
    return t.lower()


def resolve_md(md, week_start):
    """Month/day → date, choosing the year that puts it nearest the week."""
    mo, d = md
    best = None
    for y in (week_start.year - 1, week_start.year, week_start.year + 1):
        try:
            cand = dt.date(y, mo, d)
        except ValueError:
            continue
        if best is None or abs((cand - week_start).days) < abs((best - week_start).days):
            best = cand
    return best


def parse_file(path, week_start):
    items = []
    stack = []  # [(indent, text)]
    section = None
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n")
            if line.startswith("#"):
                section = line.lstrip("#").strip()
                stack = []
                continue
            m = BULLET_RE.match(line)
            if not m:
                continue
            indent = len(m.group(1).expandtabs(2))
            text = (m.group(2) or "").strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            if not text:
                continue
            stack.append((indent, text))
            ptexts = [t for _, t in stack]
            done = bool(re.match(r"^\[[xX]\]", text)) or (text.startswith("~~") and text.rstrip().endswith("~~"))
            due = None
            m_due = DUE_RE.search(text) or UNTIL_RE.search(text)
            if m_due:
                due = resolve_md((int(m_due.group(1)), int(m_due.group(2))), week_start)
            dates = []
            for dm in DATE_RE.finditer(DUE_RE.sub("", text)):
                try:
                    r = resolve_md((int(dm.group(1)), int(dm.group(2))), week_start)
                except Exception:
                    r = None
                if r:
                    dates.append(r.isoformat())
            items.append({
                "id": SEP.join(ptexts),
                "path": ptexts,
                "text": text,
                "depth": len(ptexts) - 1,
                "section": section,
                "line": lineno,
                "star": STAR in text,
                "done": done,
                "due": due.isoformat() if due else None,
                "dates": dates,
                "_key": tuple(normalize(t) for t in ptexts),
            })
    return items


def parse_projects(path):
    """Tiny parser for the restricted _projects.yml format:

    - todo: ["狭山市AP", "めぐる: *"]
      v: [03_work/sayama-ap]
      tags: [project:sayama-ap]
    """
    entries = []
    if not os.path.exists(path):
        return entries
    cur = None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.split(" #", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
            if not line.strip():
                continue
            s = line.strip()
            if s.startswith("- "):
                cur = {}
                entries.append(cur)
                s = s[2:].strip()
            if cur is None or ":" not in s:
                continue
            key, val = s.split(":", 1)
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                parts = [p.strip().strip('"').strip("'") for p in val[1:-1].split(",")]
                cur[key.strip()] = [p for p in parts if p]
            else:
                cur[key.strip()] = val.strip('"').strip("'")
    return entries


def _destar(t):
    return t.replace("\ufe0f", "").replace(STAR, "").strip()


def match_projects(item_path, entries):
    item_path = [_destar(t) for t in item_path]
    hits = []
    for e in entries:
        for pat in e.get("todo", []):
            segs = [_destar(p) for p in pat.split("›")]
            if len(segs) <= len(item_path) and all(
                fnmatch.fnmatchcase(item_path[i], segs[i]) for i in range(len(segs))
            ):
                hits.append(e)
                break
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--todo-dir", default=os.path.expanduser(
        os.environ.get("WIKI_TODO_DIR", "~/repo/gitlab/tatoflam/todo")))
    ap.add_argument("--date")
    ap.add_argument("--file")
    ap.add_argument("--projects", action="store_true")
    ap.add_argument("--list-weeks", action="store_true")
    ap.add_argument("--starred-only", action="store_true")
    a = ap.parse_args()

    weeks = list_weeks(a.todo_dir)
    if a.list_weeks:
        json.dump([{**w, "start": w["start"].isoformat(), "end": w["end"].isoformat()} for w in weeks],
                  sys.stdout, ensure_ascii=False, indent=1)
        return
    date = dt.date.fromisoformat(a.date) if a.date else None
    target = pick_week(weeks, date, a.file)

    parsed = {w["file"]: parse_file(os.path.join(a.todo_dir, w["file"]), w["start"]) for w in weeks
              if w["start"] <= target["start"]}
    history = [w for w in weeks if w["start"] <= target["start"]]

    items = parsed[target["file"]]
    present = {w["file"]: {i["_key"]: i for i in parsed[w["file"]]} for w in history}
    for it in items:
        first = target
        star_since = target if it["star"] else None
        star_run = it["star"]
        for w in reversed(history[:-1]):
            prev = present[w["file"]].get(it["_key"])
            if not prev:
                break
            first = w
            if star_run and prev["star"]:
                star_since = w
            else:
                star_run = False
        it["first_seen"] = first["start"].isoformat()
        it["age_weeks"] = (target["start"] - first["start"]).days // 7
        it["star_since"] = star_since["start"].isoformat() if star_since else None
        it["star_weeks"] = (target["start"] - star_since["start"]).days // 7 if star_since else None
        today = date or dt.date.today()
        it["overdue"] = bool(it["due"] and not it["done"] and dt.date.fromisoformat(it["due"]) < today)

    out = {
        "week": {"file": target["file"], "start": target["start"].isoformat(), "end": target["end"].isoformat()},
        "weeks_in_history": len(history),
        "items": [],
    }
    if a.projects:
        entries = parse_projects(os.path.join(a.todo_dir, "_projects.yml"))
        for it in items:
            hits = match_projects(it["path"], entries)
            it["vault"] = sorted({v for e in hits for v in e.get("v", [])})
            it["tags"] = sorted({t for e in hits for t in e.get("tags", [])})
        # a heading (depth 0/1) is unmapped when neither it nor anything under it maps
        unmapped = []
        for it in items:
            if it["depth"] > 1 or it["vault"]:
                continue
            prefix = it["id"] + SEP
            if not any(o["vault"] for o in items if o["id"].startswith(prefix)):
                unmapped.append(it["id"])
        out["unmapped"] = unmapped
    for it in items:
        it.pop("_key", None)
        if a.starred_only and not it["star"]:
            continue
        out["items"].append(it)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
