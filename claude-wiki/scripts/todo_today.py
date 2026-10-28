#!/usr/bin/env python3
"""Build today's todo digest (for the 08:00 morning notification).

Reads the week file covering DATE through todo_parse.py and prints JSON
{"title": ..., "message": ...} for `notify send`. Buckets:

  今日      the day's `### MMDD` Todo section (if the week file has one),
            plus items whose due date or a mentioned date is today
  期限超過  due date passed and not done
  近日      due/mentioned date within the next --ahead days
  ⭐️        starred and not done, grouped by top-level heading

Dates in the past (e.g. `10/26済`, `10/26時点`) are annotations, not events,
and never surface. Done items (`[x]`, `~~...~~`) drop out everywhere.

Usage:
  todo_today.py --todo-dir DIR [--date YYYY-MM-DD] [--ahead 7] [--text]
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WD = "月火水木金土日"
SEP = " › "
DAY_RE = re.compile(r"^###\s+(\d{2})(\d{2})\b")


def md(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.month}/{d.day}({WD[d.weekday()]})"


def leaf(it):
    """Item text with its parent for context, e.g. `学保連 › ⭐️11/3 運動会`."""
    p = it["path"]
    return SEP.join(p[-2:])


def daily_section(path, day):
    """Bullets under `### MMDD …` → `#### Todo`, stopping at `#### Done`."""
    want = f"{day.month:02d}{day.day:02d}"
    out, inside, todo = [], False, False
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("### ") or line.startswith("## ") or line.startswith("# "):
                m = DAY_RE.match(line)
                inside = bool(m and m.group(1) + m.group(2) == want)
                todo = False
                continue
            if inside and line.startswith("#### "):
                todo = "todo" in line.lower()
                continue
            if inside and todo and line.strip():
                if re.match(r"^\s*[-*+]\s+(\[[xX]\]|~~)", line):
                    continue
                out.append(line.replace("\t", "  ").rstrip())
    return out


def build(todo_dir, today, ahead):
    raw = subprocess.run(
        [sys.executable, os.path.join(HERE, "todo_parse.py"), "--todo-dir", todo_dir,
         "--date", today.isoformat()],
        check=True, capture_output=True, text=True).stdout
    data = json.loads(raw)
    week = data["week"]
    items = [i for i in data["items"] if not i["done"]]
    t = today.isoformat()
    horizon = (today + dt.timedelta(days=ahead)).isoformat()

    def upcoming(it):
        ds = sorted({d for d in it["dates"] + ([it["due"]] if it["due"] else []) if t < d <= horizon})
        return ds[0] if ds else None

    todays = [i for i in items if i["due"] == t or t in i["dates"]]
    overdue = [i for i in items if i["overdue"]]
    soon = sorted(((upcoming(i), i) for i in items if i not in todays and upcoming(i)),
                  key=lambda x: x[0])
    starred = [i for i in items if i["star"]]
    daily = daily_section(os.path.join(todo_dir, week["file"]), today)

    lines = []
    if week["end"] < t or week["start"] > t:
        lines += [f"※ 今週のファイルがまだ無いので {week['file']} を表示", ""]
    if daily or todays:
        lines.append("■ 今日")
        lines += daily
        lines += [f"- {leaf(i)}" for i in todays]
        lines.append("")
    if overdue:
        lines.append("■ 期限超過")
        lines += [f"- {leaf(i)}（〆{md(i['due'])}）" for i in overdue]
        lines.append("")
    if soon:
        lines.append(f"■ 近日（{ahead}日以内）")
        lines += [f"- {md(d)} {leaf(i)}" for d, i in soon]
        lines.append("")
    if starred:
        lines.append("■ ⭐️ 今週の重点")
        groups = {}
        for i in starred:
            groups.setdefault(i["path"][0], []).append(i)
        for head, its in groups.items():
            names = [SEP.join(i["path"][-2:]) if len(i["path"]) > 2 else i["path"][-1] for i in its]
            lines.append(f"- {head}: " + " / ".join(n.replace("⭐️", "").replace("⭐", "").strip() for n in names))
    if not lines:
        lines.append("今日の項目はありません")

    counts = [f"今日{sum(1 for l in daily if l.startswith('- ')) + len(todays)}"]
    if overdue:
        counts.append(f"期限超過{len(overdue)}")
    counts.append(f"⭐️{len(starred)}")
    title = f"ToDo {md(t)}: " + " / ".join(counts)
    return {"title": title, "message": "\n".join(lines).rstrip(), "week": week["file"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--todo-dir", required=True)
    ap.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--ahead", type=int, default=7)
    ap.add_argument("--text", action="store_true", help="print title + message instead of JSON")
    a = ap.parse_args()
    r = build(a.todo_dir, a.date, a.ahead)
    if a.text:
        print(r["title"]); print(); print(r["message"])
    else:
        json.dump(r, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
