---
name: wiki-weekly
description: Weekly loop between the wiki vault (past) and the todo repo (future). Runs unattended distill, writes the weekly review (plan vs actual per todo item) to 02_diary/weekly/, and writes next week's todo draft as a proposal file under the todo repo's _proposals/ — never touching the user's week files. Normally launched Sunday 08:00 JST by launchd via wiki-weekly.sh; can be run by hand. Use when the user says "週次", "weekly", "来週の予定案", or runs /wiki-weekly.
---

# /wiki-weekly

One pass of the plan → actual → next-plan loop. The AI **proposes**; the
user decides and edits their own week file. Rules: schema.md §"todo
loop" and §"`02_diary/` rules".

## Paths

- **Vault**: `~/repo/github/tatoflam/v`
- **todo**: `${WIKI_TODO_DIR:-~/repo/gitlab/tatoflam/todo}`
- **Scripts**: `${CLAUDE_PLUGIN_ROOT}/scripts/` (`todo_parse.py`, `extract_artifacts.py`)

Git pull/push of both repos is done by `wiki-weekly.sh` around this
skill. When run by hand, `git pull --rebase` both repos first and leave
pushing to the user (or the script).

## Dates

- `today` = run date (JST). **Review week** = ISO week containing
  `today` (Mon–Sun; on Sunday that is the week just ending).
- **Next week** = the Monday after `today` through the following Sunday.
  Proposal filename = `<YYYYMMDD of that Monday>-<MMDD of that Sunday>.md`.
- **Plan file** for the review = `todo_parse.py --date <today>` (the
  user's week files sometimes span two weeks; that's fine).

## Procedure

### 1. Ingest leftovers
Run the `/claude-wiki:wiki-ingest` skill so this week's sessions are in
staging. If it fails, continue and note it.

### 2. Unattended distill
Run `/claude-wiki:wiki-distill --unattended`. If it fails, continue with
digests + diaries only and note it in both outputs.

### 3. Build the per-item record
- `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/todo_parse.py --date <today> --projects`
- Read `todo:` frontmatter of every digest of the review week (in
  `_staging/` and `_staging/archive/`; filename date or `captured:` JST
  date within the week).
- Per item: sessions + dates, best progress (`done-candidate` >
  `advanced` > `touched`), confidence.
- 予定外: digests with `todo.unplanned: true`, grouped by `target`/project
  (resolve `target:` with `scripts/vault_paths.py resolve`, so old flat
  targets group with their project folder).
- Links you write use the project folder path
  (`[[03_work/012_meguru-crm/meguru-crm]]`). In the 対応表の追加候補
  section, propose `v:` entries as `<category>/<slug>` — that form stays
  valid across renumbering and is resolved by the scripts.
- 出したもの: review-week lines of `06_output/catalog/`.
- 確認待ち: files in `_staging/review/`.

### 4. Write the weekly review — `02_diary/weekly/<YYYY>-W<ww>.md`
Machine-owned; overwrite.

```markdown
---
title: <YYYY>-W<ww> 週次レビュー
category: 02_diary
week: <Mon YYYY-MM-DD>..<Sun YYYY-MM-DD>
todo_file: <week file>
generated: <ISO>
---

# <YYYY>-W<ww>（M/D–M/D）

## まとめ
<3 lines: where the week went (planned vs unplanned share, biggest moves)>

## 予定 vs 実績
### <top heading>
- 🟢 <item> — 進んだ: <1 line> （[[02_diary/<date>]], `<id8>`）
- ✅ <item> — 完了候補: <evidence>
- ⚪ <item> — 手付かず（⭐ N週）
- 🔴 <item> — 期限切れ（〆M/D）

## 予定外
- <project> — <1 line> [[<page>]]

## 出したもの
- <title> — <link>

## 確認待ち（次の付き添い distill で解消）
- [[_staging/review/<file>]] — <1 line>

## 要確認の突き合わせ
- `<id8>` → <item>（low）
```
Only list ⭐ items and items with activity under 予定 vs 実績; put
un-starred untouched items in a single collapsed callout.

### 5. Write the proposal — `<todo>/_proposals/<next week file>`
Create `_proposals/` if needed. **Never modify any other file in the
todo repo.** Start from the current week file's text.

```markdown
# 提案: <next week file stem>（<today> /wiki-weekly）

> AI の提案です。採用するものだけ自分の週ファイルへ反映してください。
> 週ごとに別ファイル。同じ週に週次を再実行したときだけ上書きされます。

## 要約
完了候補 N / 期限切れ N / 判断してほしい N / 予定外の取り込み候補 N / 対応表 N

## 完了候補（下書きから外しました）
- <item> — <evidence>

## 期限切れ（下書きでは先頭に 🔴 を付けました）
- <item>（〆M/D）

## 判断してほしい（⭐ が 4 週以上）
- <item> — ⭐ N週（M/D〜）。やめる / 分ける / 期限を付ける / そのまま
  - 案: <smallest next step or split>

## 予定外で動いた案件（見出しの追加候補）
- <project> — 今週 N セッション。例: `- <見出し案>`

## 対応表の追加候補（_projects.yml）
- `<heading>` → <vault page> / <tags>

## 下書き
<the full proposed week file: H1 = next week stem; same structure as the
current file; done-candidates removed; overdue prefixed with 🔴;
long-stuck ⭐ items kept as-is (the user decides). Add nothing the user
didn't plan except under a final `## AI 追加候補` section.>
```

### 6. Log + commit
- Append to `<vault>/log.md`:
  `- <ISO>  op:weekly  week=<YYYY-Www> items=<N> advanced=<A> done_cand=<D> overdue=<O> stuck=<S> unplanned=<U> proposal=<file> distill=<ok|failed> ingest=<ok|failed>`
- Vault: `git add 02_diary/weekly log.md` (+ whatever ingest/distill
  staged themselves) and commit `weekly: <YYYY-Www> review + proposal`.
- todo: `git -C <todo> add _proposals/<file>` only, commit
  `proposal: <file> (/wiki-weekly)`.
- Do not push (the script does).

### 7. Report
Print exactly one line first, for the notification:
`WEEKLY_SUMMARY: <YYYY-Www> 完了候補N 期限切れN 判断N 予定外N → _proposals/<file>`
then the review's まとめ.

## Guardrails

- **todo repo: only `_proposals/<new file>` may be created.** Never edit
  week files, `_projects.yml`, or other proposals. Before committing,
  `git -C <todo> status --porcelain` must show nothing but that file;
  otherwise abort the todo commit and report.
- Never mark items done; never delete stuck items from the draft.
- Every claim of progress cites a digest/diary.
- Idempotent per week: re-running overwrites this week's review and
  this week's proposal file (same names), nothing else.
