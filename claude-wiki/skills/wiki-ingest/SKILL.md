---
name: wiki-ingest
description: Drain both the session queue AND the manual inbox into the 00-07 wiki vault. Reads session transcripts enqueued by the SessionEnd hook, plus any .md the user dropped into 01_inbox/, classifies each into the appropriate category (00_self / 02_diary / 03_work / 04_life / 05_learn / 06_output / 07_archive), appends a daily diary entry, and commits to the vault. Unclassifiable items stay in 01_inbox/ with a question callout. Use when the user says "ingest", "update wiki", "取り込み", "wiki更新", or runs /wiki-ingest.
---

# /wiki-ingest

Fold new Claude Code sessions and user-dropped inbox notes into the vault at
`~/repo/github/tatoflam/v`. The canonical rules live in the plugin's
`schema.md` (sibling of this directory) — **read it before editing any page**.

## Paths

- **Vault**: `~/repo/github/tatoflam/v` (Obsidian vault; its own git repo;
  pushed to GitHub by the user — never by this skill).
- **Runtime state**: `~/.claude/wiki/state/`
  - `queue.jsonl` — session pointers enqueued by the SessionEnd hook.
  - `cursors.json` — `{ "<transcript_path>": <byte_offset> }` for
    incremental reads.
  - `ingest-log.jsonl` — machine-parseable audit trail.
  - `hook-errors.log` — hook failures (tail if something seems missing).
- **Schema**: `${CLAUDE_PLUGIN_ROOT}/schema.md` (the plugin's own schema).

## Inputs

1. **Queue**: `~/.claude/wiki/state/queue.jsonl` — lines where `processed == false`.
2. **Inbox**: every `.md` file directly under `~/repo/github/tatoflam/v/01_inbox/`
   (non-recursive, exclude dotfiles and files referenced by
   `state/ingest-log.jsonl` in the last 7 days without modification).

If both are empty, report "nothing to ingest" and stop.

## Procedure

### 1. Load state
Parse `queue.jsonl` and `cursors.json`. List inbox files. Skip inbox files
already processed recently unless their mtime advanced.

### 2. Process each input item
For each session in the queue AND each inbox file:

a. **Read the content.**
   - Sessions: read transcript from `cursors[path]` to end. Parse only
     `"type":"user"` and `"type":"assistant"` lines. Cap at the last ~200
     turns. If truncated, note in the diary entry.
   - Inbox: read the file verbatim.

b. **Extract signal.** Drop tool-call noise, resolved typos, transient
   errors. Keep: decisions, requirements, surprising findings, named
   entities, external links, artifacts published anywhere.

c. **Classify.** Score the content against 00/03/04/05/06/07. A single
   input usually produces multiple outputs.

   Category hints:
   - **00_self**: self-reflection statements about identity, values, skills.
     Rare — be conservative.
   - **03_work**: tied to a repo/cwd under `hlab-`, `meguruit/`,
     `Bizuayeu/`, or explicit work keywords (meeting, deliverable, client).
   - **04_life**: family, hobbies, health, personal finance.
   - **05_learn**: new technical knowledge, library gotchas, reading
     notes, reusable patterns.
   - **06_output**: **only with evidence of external publication** — Gmail
     draft sent, Threads/X post made, PR opened, deploy URL returned,
     Google Drive share. See schema.md §"06_output/ auto-detection".
   - **07_archive**: explicit "we dropped this", "deprecated", "replaced".

d. **Low confidence → inbox.** If no category scores clearly:
   - For a session: create
     `01_inbox/session-<id>-<YYYY-MM-DD>.md` with extracted notes AND a
     `> [!question] Needs sorting\n> Candidate categories: <list>`
     callout at the top.
   - For an inbox file: leave it in place; prepend the callout.

e. **Always write the diary entry.** Regardless of classification, append
   to `02_diary/<YYYY-MM-DD>.md`. Create the file if missing. Never
   overwrite prior entries.

f. **Prefer update > create.** Grep the vault for existing pages on the
   same subject and merge. Use the page template from schema.md.

g. **Contradictions**: `> [!warning] Contradiction` callout with both
   versions and source ids. No silent overwrite.

h. **Cross-link.** Every edit leaves the page with ≥ 1 `[[wiki-link]]`.

i. **Cite every edit.** Update frontmatter `sources:` (array of session
   ids or inbox filenames) and set `updated:` to today's date.

j. **Mark source processed.**
   - Sessions: set `cursors[path]` to current byte length.
   - Inbox files moved: `git mv` to the destination folder, rename if
     needed to match the destination page.
   - Inbox files merged into an existing page: delete after the merge
     commits successfully.
   - Inbox files that stayed: keep in place with the question callout.

### 3. Audit trail
Append one JSONL line per input to `~/.claude/wiki/state/ingest-log.jsonl`:
```json
{"ts":"<ISO>","source_type":"session|inbox","source_id":"<id or path>",
 "pages_touched":["02_diary/2026-04-23.md","05_learn/..."],
 "unsortable":false}
```

### 4. Queue bookkeeping
Rewrite `queue.jsonl` flipping `processed: true`. Keep processed lines 30
days for audit, then drop.

### 5. Commit in vault
```
cd ~/repo/github/tatoflam/v
git add -A
git diff --cached --quiet || git commit -m "ingest: <S> sessions + <I> inbox, <M> pages touched"
```
If the vault is not yet a git repo, skip the commit and say so in the
report. **Do NOT push.**

### 6. Report
```
Sessions processed: <S>    Inbox items processed: <I>
Pages touched: <M>
Moved to category: <N>    Left in inbox (needs sorting): <K>

Needs your attention:
- 01_inbox/<file>  candidates: [03_work, 05_learn]
  (rationale: ...)
```
End with a single actionable next step.

## Guardrails

- **Idempotent**: `cursors.json` + `ingest-log.jsonl` ensure re-runs are
  no-ops on already-processed content.
- **Never write runtime state into the vault.** Queue, cursors, logs all
  live under `~/.claude/wiki/state/`.
- **Never edit vault welcome files**: `ようこそ.md`,
  `make folders composition.md` at vault root — pre-existing user notes.
- **Never push to GitHub.**
- **Never delete pages**; archive via `git mv` into `07_archive/` with an
  `> [!info] Archived YYYY-MM-DD (source:<id>)` callout.
- **Per-run caps**: 20 sessions + 50 inbox files. Leftover stays queued.
- **Hook failures** (missing transcript, etc.) go to
  `~/.claude/wiki/state/hook-errors.log`; skip and continue the batch.
