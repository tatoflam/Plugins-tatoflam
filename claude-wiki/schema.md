# Wiki Schema

Inspired by Karpathy's LLM-wiki pattern
(https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
The vault uses a PKM-style layout with eight top-level categories, split
into a **capture layer** (machine-written, conflict-free) and a
**knowledge layer** (curated, stable structure).

- **Vault path (default)**: `~/repo/github/tatoflam/v` — Obsidian vault,
  intended to be pushed to GitHub by the user.
- **Runtime state**: `~/.claude/wiki/state/` — user-specific, never
  committed to either this plugin or the vault.

## Two-layer architecture

| Layer | What | Written by | Where |
|---|---|---|---|
| **Capture layer** (append-only, machine-owned, conflict-free) | Per-session digests + daily diary + operation logs | `/wiki-ingest` (non-interactive, SessionEnd hook) | `<vault>/_staging/`, `<vault>/02_diary/`, `<vault>/log.md` |
| **Knowledge layer** (curated, stable topic structure, human-browsable) | 00/03/04/05/06/07 category pages + `home.md` | `/wiki-distill` (attended) + the user | `<vault>/00_self/` `03_work/` `04_life/` `05_learn/` `06_output/` `07_archive/` |

**The division of labor is strict**: ingest captures reliably and never
touches curated pages (so it can never conflict with the user's open
editors, and transcripts are persisted before retention deletes them);
distill integrates thoughtfully and is run attended (so quality issues
are caught by a human). Raw sources remain the Claude Code transcripts
at `~/.claude/projects/**/*.jsonl` (immutable, LLM read-only) and the
manual drop zone `<vault>/01_inbox/` (bidirectional hopper).

## `_staging/` — the capture layer

`/wiki-ingest` writes one file per processed input:

```
_staging/<YYYY-MM-DD>-<session8>.md      (sessions: first 8 chars of the id)
_staging/<YYYY-MM-DD>-inbox-<slug>.md    (inbox items)
```

Digest frontmatter (all fields required unless noted):

```yaml
---
session: <full session id, or inbox filename>
captured: <ISO timestamp of ingest>
target: <proposed integration page, e.g. 03_work/todobot>   # best guess
category: 0X_<name>          # proposed category
tags: []                     # proposed tags per taxonomy below
confidence: high|medium|low
diary_pending: <text>        # optional — see diary rules below
---
```

Body: the extracted signal (decisions, requirements, findings, entities,
links, publications) in plain markdown. Verbose is fine — distill will
compress. **Never edit curated pages from ingest**; `target` is a
proposal that distill re-judges at integration time.

- `_staging/archive/` holds digests already integrated by distill.
  Distill **moves** (never deletes) processed digests there, so
  provenance survives. Exclude `_staging/archive/` from Obsidian graph
  and search.
- Digest files are machine-owned: the user should not edit them (edits
  are tolerated but may be overwritten by re-capture).

## Wiki meta files (auto-maintained at vault root)

| File | Role | Maintained by |
|---|---|---|
| `<vault>/index.md` | Catalog of every page grouped by category. Regenerated from the filesystem at the end of every `/wiki-ingest` and `/wiki-distill` run. **Do not hand-edit.** | `/wiki-ingest`, `/wiki-distill` |
| `<vault>/home.md` | **Human entry point.** Active work/life projects, recent major decisions, link to 00_self. Curated prose, not a catalog. | `/wiki-distill` |
| `<vault>/log.md` | Append-only chronological record of every `/wiki-*` operation (ingest/distill/query/lint/status). One line per invocation. **Operational telemetry goes here and only here.** | every `/wiki-*` skill |
| `<vault>/_schema.md` | Read-only mirror of this file. Overwritten on every ingest. **Do not hand-edit.** | `/wiki-ingest` |

Log line format:
```
- YYYY-MM-DDTHH:MM:SSZ  op:<ingest|distill|query|lint|status>  <one-line summary>
```

Examples:
```
- 2026-07-09T02:30:00Z  op:ingest   S=3 I=1 staged=4 diary=2 staging_backlog=9
- 2026-07-09T09:15:00Z  op:distill  staged=9 pages=5 self=1 home=updated
- 2026-07-09T10:00:00Z  op:query    "when did we fix the auth bug?" → 03_work/meguru-pm-report
```

## Categories

| #  | Folder         | Layer | Purpose |
|----|----------------|-------|---------|
| 00 | `00_self/`     | knowledge | **The digital-twin core.** Profile, values, skills, goals, preferences. Updated by distill from accumulated signals. |
| 01 | `01_inbox/`    | raw   | **Bidirectional hopper.** Unsorted manual captures and ingest failures. |
| 02 | `02_diary/`    | capture | Daily log of **user activity**. One file per day: `YYYY-MM-DD.md`. No operational telemetry. |
| 03 | `03_work/`     | knowledge | Work: projects, meetings, professional learnings |
| 04 | `04_life/`     | knowledge | Private life: family, hobbies, daily living |
| 05 | `05_learn/`    | knowledge | Learnings: tech notes, reading notes, study |
| 06 | `06_output/`   | knowledge | **Artifacts published externally.** Store the artifact if small; otherwise a link catalog. |
| 07 | `07_archive/`  | knowledge | Deprecated or completed. |

## Curated page standard structure (03_work / 04_life)

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
<3-5 lines: what this is, why it matters>

## 現在の状態
<latest snapshot — distill overwrites this each run; the displaced
 previous state moves into 経緯 with its date>

## 決定事項
- YYYY-MM-DD: <decision> — <reason>   (cumulative, never silently removed)

## 手順・Runbook
<reproducible operations, commands, checklists — only if applicable>

## 経緯
<compressed timeline of key events; details resolve via frontmatter
 sources, [[02_diary/...]] links, and _staging/archive/>

## Links
- [[...]]
```

The three query archetypes map onto this structure: *今どうなってる？*
→ 現在の状態, *なぜそう決めた？* → 決定事項, *どうやるんだっけ？* →
手順・Runbook. **Never create session-dated H2 append silos** — that is
the anti-pattern this schema replaces.

05_learn keeps its Summary/Details shape but follows the same principle:
**stable headings = topics; chronology is quarantined into a 経緯 or
observation-log subsection.** 00_self pages are free-form curated prose.

## Tag taxonomy

All non-diary pages carry a `tags:` frontmatter array. Tags use a
prefixed, colon-separated form (`<facet>:<slug>`) so they roll up
cleanly in Obsidian's tag pane and survive as stable filter keys.

### Primary tag (required)

Every page carries at least one **primary tag** identifying its subject
within the category:

| Category   | Primary tag form     | Examples |
|------------|----------------------|----------|
| 00_self    | `aspect:<slug>`      | `aspect:profile`, `aspect:values`, `aspect:skills`, `aspect:goals`, `aspect:preferences` |
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

### Tag behavior

- **Ingest (staging digests)**: propose tags in the digest frontmatter;
  always propose the primary tag for the proposed category.
- **Distill (curated pages)**: on create, assign the primary tag; on
  update, merge new tags without dropping prior ones unless the content
  clearly no longer applies.
- **Archive (`git mv` to `07_archive/`)**: preserve existing tags,
  append `status:archived` and `archived:YYYY-MM-DD`.

## `02_diary/` rules

One file per day: `02_diary/YYYY-MM-DD.md`. Ingest **appends**; it never
overwrites prior entries. Diary records **what the user (and Claude)
accomplished** — shipped features, decisions made, things published,
problems solved.

```markdown
## HH:MM  <short headline of the accomplishment>
- session: <id8>  cwd: <repo-leaf>
- <1-3 bullets: what was done / decided / published>
- see also: [[...]]
```

**Prohibited in diary**: run numbers, queue statistics, defer/meta-ack
bookkeeping, missing-transcript accounting, cursor positions — all
operational telemetry belongs in `log.md` and
`~/.claude/wiki/state/ingest-log.jsonl` only. **Wiki meta-sessions**
(sessions whose only content is running `/wiki-*` skills) get **no
diary entry at all** — ack them in `log.md`.

If the day's diary file is dirty (user editing), do **not** defer the
item: put the would-be diary text into the digest's `diary_pending:`
frontmatter field; distill lands it later.

## `01_inbox/` is bidirectional

- **Out**: `/wiki-ingest` leaves anything it cannot confidently classify
  here with a `> [!question] Needs sorting` callout citing the source.
- **In**: The user drops raw notes here by hand any time. On the next
  `/wiki-ingest`, classifiable notes become staging digests
  (`_staging/<date>-inbox-<slug>.md`) and the originals are removed;
  unclassifiable notes stay with the callout.

## `06_output/` auto-detection

Flag evidence of an **external publication** in the digest — e.g., a
Gmail draft sent, a Threads/X post created, a URL returned by a deploy,
a PR opened, a doc shared via Google Drive. Distill files it:

- Small artifact (≤ ~200 lines): paste verbatim inside the `06_output/` page.
- Large artifact: link-only entry with title, URL, date, originating session.
- Group by month: `06_output/YYYY-MM.md` is the default index file; create a
  dedicated page only when one artifact deserves more than a bullet.

## Ingestion rules (`/wiki-ingest` — capture layer)

1. **Two input sources per run**: `~/.claude/wiki/state/queue.jsonl` +
   every `.md` file directly under `<vault>/01_inbox/` (non-recursive,
   exclude hidden files).
2. **One digest file per input, into `_staging/`.** New file creation
   only — never modify curated pages, never defer waiting for them.
3. **Persist before retention.** Read the transcript on first
   processing and write the digest in the same run, so transcript
   deletion (~30-day retention) can never lose knowledge.
4. **Diary entry per substantive session** (user-activity format above;
   meta-sessions skipped; dirty diary → `diary_pending` in the digest).
5. **Low confidence → inbox** with the `> [!question]` callout.
6. **Audit trail (machine)**: append to `~/.claude/wiki/state/ingest-log.jsonl`
   one line per input processed.
7. **Meta refresh**: regenerate `index.md`, append one line to `log.md`
   (including the current staging backlog count), mirror `_schema.md`.
8. **Commit, never push** from the skill (the hook may push afterwards).

## Distillation rules (`/wiki-distill` — knowledge layer)

1. **Group staging digests by integration target** (re-judging the
   proposed `target`), then merge each group into the curated page
   using the standard structure. Prefer update > create.
2. **現在の状態 is overwritten; nothing else is silently lost.** The
   displaced state moves into 経緯 with its date. 決定事項 is
   cumulative. Contradictions that cannot be resolved get a
   `> [!warning] Contradiction` callout with both versions.
3. **Compress 経緯**; details stay reachable via `sources:`, diary
   links, and `_staging/archive/`.
4. **Update frontmatter** on every touched page: merge `sources:`, set
   `updated:`, apply tags per taxonomy.
5. **Cross-link**: every touched page ends with ≥ 1 `[[wiki-link]]`.
6. **Self-model pass**: scan the batch for self signals (preferences,
   judgment criteria, skill changes, goal progress) and update 00_self
   (profile / skills / values / goals / preferences) when warranted.
7. **Land `diary_pending`** entries into their diary files.
8. **Move processed digests to `_staging/archive/`** — never delete.
9. **Maintain `home.md`** (active projects, recent major decisions,
   00_self link) and regenerate `index.md`.
10. **Append one line to `log.md`**, then commit. Distill runs attended;
    if a curated target is dirty, resolve it with the user on the spot.

## Non-goals

- Touching `ようこそ.md` or `make folders composition.md` — those are the
  user's welcome notes; leave alone.
- Pushing to GitHub from skills — the hook/user controls `git push`.
- Hand-editing `index.md`, `log.md`, or `_schema.md` — they are
  auto-maintained. For `log.md`, append-only via skill code; never rewrite
  history.
- Editing digest files by hand — capture is machine-owned; fix content
  at the curated page (knowledge layer) instead.
