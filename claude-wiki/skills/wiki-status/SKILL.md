---
name: wiki-status
description: Quick status of the wiki vault and pipeline. Shows queue depth, staging backlog (undistilled digests), inbox backlog, last ingest/distill time, page count by category, and git status of the vault. Use when the user asks "wiki status", "キューは？", "滞留は？", or runs /wiki-status.
---

# /wiki-status

One-shot status readout. No edits.

## Paths

- **Vault**: `~/repo/github/tatoflam/v`
- **Runtime state**: `~/.claude/wiki/state/`

## Procedure

1. **Queue** — count lines in `~/.claude/wiki/state/queue.jsonl` where
   `processed == false` vs total.
2. **Staging backlog** — count `.md` files directly under
   `<vault>/_staging/` (excluding `archive/`), plus the oldest digest's
   `captured:` date (or file mtime).
3. **Inbox backlog** — count `.md` files under `<vault>/01_inbox/`
   (non-recursive, excluding dotfiles).
4. **Last ingest** — latest `ts` in `~/.claude/wiki/state/ingest-log.jsonl`,
   or `git -C <vault> log -1 --format=%cI` as fallback.
5. **Last distill** — latest `op:distill` line in `<vault>/log.md`, or
   "never".
6. **Pages per category** — `find <vault>/0X_* -name '*.md' | wc -l` per
   folder, 00-07.
7. **Git state** — `git -C <vault> status --porcelain | wc -l` (count of
   uncommitted changes). If not a git repo, say so.
8. **Hook errors** — tail of `~/.claude/wiki/state/hook-errors.log` if
   present.
9. **Recent ops** — last 5 lines of `<vault>/log.md`.
10. **Weekly job** — latest `op:weekly` line in `<vault>/log.md` (ok or
    failed + stage), and the newest file in `<todo>/_proposals/`
    (`${WIKI_TODO_DIR:-~/repo/gitlab/tatoflam/todo}`) with whether the
    corresponding week file exists yet (exists = the user has adopted
    the week; missing = proposal unread/unadopted).
11. **Review queue** — count of `_staging/review/*.md`.
12. **Stray deliverables** — count of non-markdown, non-dot files at the
    vault root (should be 0; see /wiki-lint).

## Output format

```
Queue:           <P> pending / <T> total
Staging backlog: <B> digests awaiting /wiki-distill (oldest: <date>)
Inbox:           <N> items
Last ingest:     <ISO-timestamp or "never">
Last distill:    <ISO-timestamp or "never">
Pages:
  00 self        <N>
  01 inbox       <N>
  02 diary       <N>
  03 work        <N>
  04 life        <N>
  05 learn       <N>
  06 output      <N>
  07 archive     <N>
Vault git:       <clean | N uncommitted | not a git repo>
Hook errors:     <none | last 3 lines>
Weekly job:      <last op:weekly ts + ok|failed@stage, or "never">
Next proposal:   <_proposals/<file> — adopted|not yet adopted, or none>
Review queue:    <N> items awaiting attended /wiki-distill
Stray files:     <N> at vault root
Recent ops:      <last 5 lines of log.md>
```

If the staging backlog is ≥ 10 digests OR the oldest digest is > 7 days
old, end with: **"Staging backlog needs attention — run `/wiki-distill`."**

## Guardrails

- **Read-only.** Never edit.
- Fast: bash + basic file operations only, no LLM reasoning required.
