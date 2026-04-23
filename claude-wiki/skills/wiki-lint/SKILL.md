---
name: wiki-lint
description: Audit the wiki vault for contradictions, orphaned pages, stale content, missing frontmatter, broken wiki-links, and stuck inbox items. Reports findings and suggests fixes but does NOT auto-resolve. Use when the user asks to "lint the wiki", "check wiki health", or runs /wiki-lint.
---

# /wiki-lint

Periodic health check over `~/repo/github/tatoflam/v`. Reports findings;
the user decides what to fix. `/wiki-ingest` is forbidden from silently
resolving contradictions — that's this skill's job.

## Paths

- **Vault**: `~/repo/github/tatoflam/v` — do not edit unless the user
  explicitly says "fix" after seeing the report.
- **Audit log** (for diary-gap detection):
  `~/.claude/wiki/state/ingest-log.jsonl`.

## Checks

1. **Contradictions.** Grep for `> [!warning] Contradiction` blocks. List
   each with the page path and cited source ids.
2. **Stuck inbox items.** `.md` files under `01_inbox/` older than 14
   days, especially those with `> [!question] Needs sorting`.
3. **Orphans.** Pages in 00/03/04/05/06/07 with zero inbound
   `[[wiki-links]]` from other pages. Exclude `02_diary/` (expected to
   link out but not in) and root-level files (`ようこそ.md`,
   `make folders composition.md`).
4. **Stale pages.** Frontmatter `updated:` older than 90 days AND no
   recent `02_diary/` entry referencing them. Suggest refresh or
   `git mv` to `07_archive/`.
5. **Missing frontmatter.** Non-diary pages lacking `title`, `category`,
   `updated`, or `sources`.
6. **Broken wiki-links.** `[[target]]` where no matching file exists.
7. **Duplicate titles.** Two pages with identical `title:` frontmatter —
   candidate merges.
8. **Diary gaps.** Days with sessions in `ingest-log.jsonl` but no
   matching `02_diary/<date>.md` — indicates a past ingest bug.
9. **Git state.** Uncommitted changes in the vault — prior
   `/wiki-ingest` may have failed mid-batch.

## Output format

```
## Contradictions (<N>)
- 03_work/foo.md  (sources: a, b)

## Stuck inbox (<N>)
- 01_inbox/bar.md  (21 days old, candidates: [05_learn])

## Orphans (<N>)
## Stale (<N>)
## Missing frontmatter (<N>)
## Broken links (<N>)
## Duplicate titles (<N>)
## Diary gaps (<N>)

## Git
- <clean | N uncommitted files>
```

End with one-line summary + one recommended action.

After the report is printed, append one line to `<vault>/log.md`:
```
- <ISO>  op:lint  contradictions=<N> orphans=<N> stale=<N> broken=<N> stuck-inbox=<N>
```
This is the only write `/wiki-lint` makes in read-only mode.

## Guardrails

- **Effectively read-only** unless the user explicitly says "fix" after
  seeing the report. The only permitted write in read-only mode is the
  one-line append to `<vault>/log.md`.
- **Never auto-resolve contradictions.** Human judgment required.
- **Never edit vault welcome files** (`ようこそ.md`,
  `make folders composition.md`).
