# Wiki Schema

Inspired by Karpathy's LLM-wiki pattern
(https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
The vault uses a PKM-style layout with eight top-level categories.

- **Vault path (default)**: `~/repo/github/tatoflam/v` — Obsidian vault,
  intended to be pushed to GitHub by the user.
- **Runtime state**: `~/.claude/wiki/state/` — user-specific, never
  committed to either this plugin or the vault.

## Categories

| #  | Folder         | Purpose |
|----|----------------|---------|
| 00 | `00_self/`     | Profile, values, skills inventory, self-description |
| 01 | `01_inbox/`    | **Bidirectional hopper.** Unsorted captures and ingest failures. |
| 02 | `02_diary/`    | Daily log. One file per day: `YYYY-MM-DD.md`. |
| 03 | `03_work/`     | Work: projects, meetings, professional learnings |
| 04 | `04_life/`     | Private life: family, hobbies, daily living |
| 05 | `05_learn/`    | Learnings: tech notes, reading notes, study |
| 06 | `06_output/`   | **Artifacts published externally** by the user, LLMs, or services they run. Store the artifact if small; otherwise a link catalog. |
| 07 | `07_archive/`  | Deprecated or completed. |

## `01_inbox/` is bidirectional

- **Out**: `/wiki-ingest` puts anything it cannot confidently classify here,
  prepended with a `> [!question] Needs sorting` callout citing the source
  session or inbox file.
- **In**: The user drops raw notes here by hand any time. On the next
  `/wiki-ingest`, those notes are processed together with the session
  transcripts from the queue and moved into 00/02-07 if classifiable.

## `06_output/` auto-detection

Add a page whenever the session or an inbox note contains evidence of an
**external publication** — e.g., a Gmail draft sent, a Threads/X post
created, a URL returned by a deploy, a PR opened, a doc shared via
Google Drive, a file uploaded somewhere public. Rules:

- Small artifact (≤ ~200 lines): paste verbatim inside the `06_output/` page.
- Large artifact: link-only page with title, URL, date, originating session.
- Group by month: `06_output/YYYY-MM.md` is the default index file; create a
  dedicated page only when one artifact deserves more than a bullet.

## `02_diary/` granularity

One file per day: `02_diary/YYYY-MM-DD.md`. Ingest **appends** to the current
day's file; it never overwrites prior entries. Entry minimum:

```markdown
## HH:MM  <short headline>
- session: <id>  cwd: <repo-leaf>
- <2-5 bullets: what was done, decisions, surprises>
- see also: [[...]]
```

## Page template (non-diary)

```markdown
---
title: <short title>
category: 0X_<name>
tags: []
sources: [<session-id or inbox-file>, ...]
updated: YYYY-MM-DD
---

# <title>

## Summary
<2-4 lines>

## Details
...

## Links
- [[...]]
```

## Ingestion rules

1. **Two input sources per run**: `~/.claude/wiki/state/queue.jsonl` +
   every `.md` file directly under `<vault>/01_inbox/` (non-recursive,
   exclude hidden files).
2. **Always write a diary entry** for each session processed. Multiple
   sessions on the same day append — do not clobber.
3. **Classification first, writing second.** A single input may produce
   multiple outputs (diary entry + 05_learn page + 06_output link).
4. **Low confidence → inbox.** Leave the content in `01_inbox/` with a
   `> [!question] Needs sorting` callout listing candidate categories.
5. **`06_output/` requires evidence of external publication.** Do not
   file internal notes there.
6. **Prefer update > create.** Grep for existing pages and merge.
7. **Contradictions**: `> [!warning] Contradiction` callout rather than
   silent overwrite.
8. **Cross-link**: every new page must contain ≥ 1 `[[wiki-link]]`.
9. **Audit trail**: append to `~/.claude/wiki/state/ingest-log.jsonl`
   one line per input processed.
10. **Commit, never push.** `git commit` in the vault after a batch; the
    user decides when to `git push`.

## Non-goals

- Writing `index.md` at vault root — Obsidian's graph view supplants it.
- Touching `ようこそ.md` or `make folders composition.md` — those are the
  user's welcome notes; leave alone.
- Pushing to GitHub from ingest — the user controls when to `git push`.
