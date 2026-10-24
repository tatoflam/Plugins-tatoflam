---
name: wiki-next
description: Suggest what to do next — 3-5 concrete actions for today — by reading this week's todo file (the plan), what the wiki vault says actually happened (digests matched to todo items, recent diaries), and today's/tomorrow's calendar. Also lists done-candidates and overdue items. Read-only. Use when the user asks "次なにやる？", "今日やること", "what should I do next", "next", or runs /wiki-next — typically from a phone via Remote Control.
---

# /wiki-next

Answer "what should I do next?" from the plan (todo, future) and the
record (vault, past). **Read-only**: never write to the vault or the todo
repo, never commit. The output is read on a phone — keep it to ~20 lines.

## Paths

- **Vault**: `~/repo/github/tatoflam/v`
- **todo**: `${WIKI_TODO_DIR:-~/repo/gitlab/tatoflam/todo}` (`git -C <todo> pull -q` first is OK; it does not modify files)
- **Schema**: `${CLAUDE_PLUGIN_ROOT}/schema.md` §"todo loop"

## Procedure

1. **Plan.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/todo_parse.py --projects`
   (today's week). If no week file covers today, use the latest one and
   say so.
2. **Record.** For this week's date range, read the `todo:` frontmatter
   of digests in `_staging/` and `_staging/archive/` whose filename date
   or `captured:` JST date is within the range. Build per item: last touched date,
   progress (`advanced` / `done-candidate` / `touched`), session ids.
   Also skim the last 3 days of `02_diary/` (持ち越し sections especially).
3. **Calendar.** If a Google Calendar tool is available, list today's and
   tomorrow's events (JST). If not, skip and say so on the last line.
4. **Choose 3-5 actions for today.** Rank by, in order:
   - overdue or due within 2 days (`due`, `overdue`, or dates in the text
     that fall today/tomorrow), and calendar events that need preparation;
   - ⭐ items with momentum (advanced in the last 3 days — finish them);
   - ⭐ items stuck longest (`star_weeks` high, never touched this week) —
     suggest the smallest next step, not "進める";
   - 持ち越し from recent diaries.
   Each action: one line, concrete verb, why (期限 / 滞留N週 / 昨日の続き / 予定あり).
   Fit them around the calendar (don't suggest deep work in a day full
   of meetings).
5. **Done-candidates.** Items with `progress: done-candidate` evidence
   and no done mark in the week file → "完了印を付けてよさそう".
6. **Overdue.** Items past their due date without a done mark.

## Output format

```
## 今日やること（YYYY-MM-DD 曜）
1. <action> — <why>
2. …
（予定: HH:MM <event>, …）

## 完了にしてよさそう
- <item> — <evidence: date, session id8 / page>

## 期限切れ
- <item>（〆M/D）

_読めなかった情報源: <calendar | todo | none>_
```

Omit empty sections. Japanese, plain words.

## Guardrails

- **Read-only.** No file writes in either repo, no commits, no pushes.
- Never mark anything done — only suggest.
- Never invent progress: every "done-candidate" and "昨日の続き" must
  cite a digest/diary.
- If the todo repo is missing, answer from the vault only and say so.
