# Wiki Schema

Inspired by Karpathy's LLM-wiki pattern
(https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
The vault uses a PKM-style layout with eight top-level categories.

- **Vault path (default)**: `~/repo/github/tatoflam/v` — Obsidian vault,
  intended to be pushed to GitHub by the user.
- **Runtime state**: `~/.claude/wiki/state/` — user-specific, never
  committed to either this plugin or the vault.

## Three-layer mapping (Karpathy's schema)

| Layer | What | Where |
|---|---|---|
| **1. Raw sources** (immutable, human-curated, LLM read-only) | Claude Code session transcripts | `~/.claude/projects/**/*.jsonl` |
| **1.5 Staging** (mutable intake, LLM may move) | Manually-dropped notes | `<vault>/01_inbox/*.md` |
| **2. Wiki** (LLM writes, humans browse) | All 00/02-07 category pages + `index.md` + `log.md` + `_schema.md` | `<vault>/**` |
| **3. Schema** (human + LLM co-evolved) | Ingestion rules, category definitions, skill behavior | `${CLAUDE_PLUGIN_ROOT}/schema.md` (canonical) + each `SKILL.md` |

`01_inbox/` is explicitly "Layer 1.5" — it accepts raw input like Layer 1
but is mutated by ingest like staging. Contents are either moved out
(classified) or left with a `> [!question] Needs sorting` callout.

## Wiki meta files (auto-maintained at vault root)

| File | Role | Maintained by |
|---|---|---|
| `<vault>/index.md` | Catalog of every page grouped by category. Regenerated from filesystem at the end of every `/wiki-ingest` run. **Do not hand-edit.** | `/wiki-ingest` |
| `<vault>/log.md` | Append-only chronological record of every `/wiki-*` operation (ingest/query/lint/status). One line per invocation. | every `/wiki-*` skill |
| `<vault>/_schema.md` | Read-only mirror of this file. Exists so the schema is visible when browsing the vault in Obsidian without access to the plugin repo. Overwritten on every ingest. **Do not hand-edit.** | `/wiki-ingest` |

Log line format:
```
- YYYY-MM-DDTHH:MM:SSZ  op:<ingest|query|lint|status>  <one-line summary>
```

Examples:
```
- 2026-04-23T02:30:00Z  op:ingest  S=3 I=1 pages=8 unsortable=0
- 2026-04-23T09:15:00Z  op:query   "when did we fix the auth bug?" → 03_work/meguru-pm-report
- 2026-04-23T10:00:00Z  op:lint    contradictions=2 orphans=5 stale=3
```

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

## Tag taxonomy

All non-diary pages carry a `tags:` frontmatter array. Tags use a
prefixed, colon-separated form (`<facet>:<slug>`) so they roll up
cleanly in Obsidian's tag pane and survive as stable filter keys.

### Primary tag (required)

Every page carries at least one **primary tag** identifying its subject
within the category:

| Category   | Primary tag form     | Examples |
|------------|----------------------|----------|
| 00_self    | `aspect:<slug>`      | `aspect:profile`, `aspect:values`, `aspect:skills`, `aspect:goals` |
| 03_work    | `project:<slug>`     | `project:meguru-pm-report`, `project:yahatayama-rokujizo` |
| 04_life    | `domain:<slug>`      | `domain:house`, `domain:finance`, `domain:family`, `domain:health`, `domain:hobby` |
| 05_learn   | `topic:<slug>`       | `topic:claude-code`, `topic:google-sheets`, `topic:real-estate-law` |
| 06_output  | `channel:<slug>`     | `channel:github`, `channel:gmail`, `channel:drive`, `channel:blog` |
| 07_archive | inherit origin tags + `status:archived` + `archived:<YYYY-MM-DD>` | |

### Secondary tags (optional, repeatable)

- `tech:<slug>` — language / framework / tool (`tech:python`,
  `tech:obsidian`, `tech:sqlite`)
- `stage:<slug>` — lifecycle (`stage:planning`, `stage:active`,
  `stage:handoff`, `stage:done`)
- `client:<slug>` — for 03_work pages (`client:meguru`)
- `entity:<slug>` — named non-tech entity (`entity:sayama-property`,
  `entity:riel-sekine`)
- `status:<slug>` — `status:archived` (07), `status:blocked`, etc.
- Free-form bare tags (`budgeting`, `onboarding`) are allowed when no
  prefix fits, but a page must carry at least one prefixed tag.

### Slug rules

- lowercase, hyphen-separated
- ASCII preferred; Japanese OK for entity names when there is no clean
  romanization (`entity:八幡山六地蔵`)
- singular form (`meeting`, not `meetings`)
- **reuse > invent** — grep existing pages for similar slugs first;
  `/wiki-lint` flags near-duplicate slugs for consolidation

### Valid facet prefixes

`aspect`, `project`, `domain`, `topic`, `channel`, `tech`, `stage`,
`client`, `entity`, `status`, `archived`.

Any other prefix is treated as a free-form tag (allowed but not
recognized as primary).

### Ingest behavior (tags)

- **Create**: derive tags from classification signals. Always assign the
  primary tag for the category.
- **Update**: merge new tags into existing; never drop a tag unless the
  content clearly no longer applies.
- **Archive (`git mv` to `07_archive/`)**: preserve existing tags,
  append `status:archived` and `archived:YYYY-MM-DD`.

Existing pages predating this taxonomy are grandfathered; ingest
normalizes them opportunistically on the next update that touches them.
`/wiki-lint` reports pages still missing a primary tag so the user can
prioritize cleanup.

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
9. **Audit trail (machine)**: append to `~/.claude/wiki/state/ingest-log.jsonl`
   one line per input processed.
10. **Wiki meta refresh** (at the end of every `/wiki-ingest`):
    - Regenerate `<vault>/index.md` from the filesystem (alphabetical
      within each category, skip dotfiles and root welcome notes).
    - Append one-line entry to `<vault>/log.md`.
    - Copy `${CLAUDE_PLUGIN_ROOT}/schema.md` to `<vault>/_schema.md`
      (only if different) with a prepended note:
      `> Read-only mirror. Canonical copy is ${CLAUDE_PLUGIN_ROOT}/schema.md. Overwritten on next /wiki-ingest.`
11. **Commit, never push.** `git commit` in the vault after a batch; the
    user decides when to `git push`.

## Non-goals

- Touching `ようこそ.md` or `make folders composition.md` — those are the
  user's welcome notes; leave alone.
- Pushing to GitHub from ingest — the user controls when to `git push`.
- Hand-editing `index.md`, `log.md`, or `_schema.md` — they are
  auto-maintained. For `log.md`, append-only via skill code; never rewrite
  history.
