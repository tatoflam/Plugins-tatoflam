---
name: wiki-status
description: Quick status of the wiki vault and ingest queue. Shows queue depth, inbox backlog, last ingest time, page count by category, and git status of the vault. Use when the user asks "wiki status", "キューは？", or runs /wiki-status.
---

# /wiki-status

One-shot status readout. No edits.

## Paths

- **Vault**: `~/repo/github/tatoflam/v`
- **Runtime state**: `~/.claude/wiki/state/`

## Procedure

1. **Queue** — count lines in `~/.claude/wiki/state/queue.jsonl` where
   `processed == false` vs total.
2. **Inbox backlog** — count `.md` files under
   `~/repo/github/tatoflam/v/01_inbox/` (non-recursive, excluding dotfiles).
3. **Last ingest** — latest `ts` in `~/.claude/wiki/state/ingest-log.jsonl`,
   or `git -C <vault> log -1 --format=%cI` as fallback.
4. **Pages per category** — `find <vault>/0X_* -name '*.md' | wc -l` per
   folder, 00-07.
5. **Git state** — `git -C <vault> status --porcelain | wc -l` (count of
   uncommitted changes). If not a git repo, say so.
6. **Hook errors** — tail of `~/.claude/wiki/state/hook-errors.log` if
   present.

## Output format

```
Queue:         <P> pending / <T> total
Inbox:         <N> items
Last ingest:   <ISO-timestamp or "never">
Pages:
  00 self        <N>
  01 inbox       <N>
  02 diary       <N>
  03 work        <N>
  04 life        <N>
  05 learn       <N>
  06 output      <N>
  07 Archive     <N>
Vault git:     <clean | N uncommitted | not a git repo>
Hook errors:   <none | last 3 lines>
```

## Guardrails

- **Read-only.** Never edit.
- Fast: bash + basic file operations only, no LLM reasoning required.
