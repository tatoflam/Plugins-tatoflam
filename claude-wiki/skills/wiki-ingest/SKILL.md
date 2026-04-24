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

d2. **Dirty-target gate (defer if the user is editing).** Before any write:
   - Enumerate the target files this item will touch:
     `02_diary/<YYYY-MM-DD>.md` (always, per step e) plus any vault page
     the classification (c/d) will create or modify. Use the *update >
     create* match from step f to identify the existing page you would
     touch — a read-only grep, no write yet.
   - For each target path, run
     `git -C <vault> status --porcelain -- <path>`. Non-empty output
     means the working copy is dirty — the user may be live-editing the
     file in Obsidian/VSCode. Writing would race with the editor's
     in-memory buffer and get silently overwritten on the next save.
   - If *any* content target is dirty, **defer the whole item**:
     - Leave `processed: false` in the queue (retried on next run).
     - Append one line to `~/.claude/wiki/state/hook-errors.log`:
       `<ISO>  session=<id>  skip=dirty_working_copy  files=[<p1>, ...]`
     - Do not emit a row in `ingest-log.jsonl` (no audit trail for
       deferred work — it will be logged when it actually lands).
     - Count the item under "Deferred" in the final report and skip to
       the next queue item.
   - Skill-owned meta files (`log.md`, `index.md`, `_schema.md`) are not
     user-editable and are excluded from this check.

e. **Always write the diary entry.** Regardless of classification, append
   to `02_diary/<YYYY-MM-DD>.md`. Create the file if missing. Never
   overwrite prior entries.

f. **Prefer update > create.** Grep the vault for existing pages on the
   same subject and merge. Use the page template from schema.md.

g. **Contradictions**: `> [!warning] Contradiction` callout with both
   versions and source ids. No silent overwrite.

h. **Cross-link.** Every edit leaves the page with ≥ 1 `[[wiki-link]]`.

i. **Cite and tag every edit.** Update frontmatter on every page you
   touch:
   - `sources:` — append the session id or inbox filename if not
     already present.
   - `updated:` — set to today's date.
   - `tags:` — apply the taxonomy in schema.md §"Tag taxonomy":
     - **Create**: assign the primary tag for the category
       (`project:<slug>` for 03_work, `domain:<slug>` for 04_life,
       `topic:<slug>` for 05_learn, `channel:<slug>` for 06_output,
       `aspect:<slug>` for 00_self) plus any obvious secondary tags
       (`tech:`, `client:`, `entity:`, `stage:`).
     - **Update**: merge new tags into the existing array without
       dropping prior entries. If the page predates the taxonomy and
       has only bare tags (e.g. `[meguruit, python]`), add the primary
       prefixed tag alongside them — do not rewrite existing bare tags.
     - **Archive** (moving to `07_archive/`): preserve existing tags,
       append `status:archived` and `archived:<YYYY-MM-DD>`.
   - Follow schema.md slug rules: lowercase, hyphen-separated, singular,
     reuse before invent.

j. **Mark source processed.**
   - Sessions: set `cursors[path]` to current byte length.
   - Inbox files moved: `git mv` to the destination folder, rename if
     needed to match the destination page.
   - Inbox files merged into an existing page: delete after the merge
     commits successfully.
   - Inbox files that stayed: keep in place with the question callout.

**Also run the dirty-target gate before the meta refresh in step 4.** If
the current ingest has already written to at least one content page,
proceed — but if *all* sessions deferred and no content pages changed,
skip steps 4–6 and exit with a "nothing to commit (all deferred)"
report.

### 3. Audit trail (machine)
Append one JSONL line per input to `~/.claude/wiki/state/ingest-log.jsonl`:
```json
{"ts":"<ISO>","source_type":"session|inbox","source_id":"<id or path>",
 "pages_touched":["02_diary/2026-04-23.md","05_learn/..."],
 "unsortable":false}
```

### 4. Wiki meta refresh

Do all three before the commit step:

a. **Regenerate `<vault>/index.md`** from the filesystem. Overwrite
   entirely (no hand edits expected). Structure:
   ```markdown
   # Index
   Auto-generated by /wiki-ingest. Do not hand-edit.
   Last generated: <ISO>.

   ## 00 self
   - [[00_self/<name>]]
   ...
   ## 02 diary
   - [[02_diary/YYYY-MM-DD]]  (most recent first)
   ...
   ## 07 archive
   - [[07_archive/<name>]]
   ```
   Alphabetical within each section except `02_diary` which is reverse
   chronological. Exclude dotfiles and the root welcome notes
   (`ようこそ.md`, `make folders composition.md`). Include `01_inbox`
   as a count line only: `_<N> pending items_`.

b. **Append to `<vault>/log.md`** (create if missing with a header):
   ```
   - <ISO>  op:ingest  S=<sessions> I=<inbox> pages=<M> unsortable=<K>
   ```

c. **Mirror schema to `<vault>/_schema.md`.** Read
   `${CLAUDE_PLUGIN_ROOT}/schema.md`, prepend:
   ```
   > [!info] Read-only mirror
   > Canonical copy: `${CLAUDE_PLUGIN_ROOT}/schema.md`.
   > Overwritten by /wiki-ingest. Do not hand-edit.

   ```
   Then write the combined content to `<vault>/_schema.md`. Skip write
   if byte-identical to the existing file.

### 5. Queue bookkeeping
Rewrite `queue.jsonl` flipping `processed: true`. Keep processed lines 30
days for audit, then drop.

### 6. Commit in vault
```
cd ~/repo/github/tatoflam/v
git add -A
git diff --cached --quiet || git commit -m "ingest: <S> sessions + <I> inbox, <M> pages touched"
```
If the vault is not yet a git repo, skip the commit and say so in the
report. **Do NOT push.**

### 7. Report
```
Sessions processed: <S>    Inbox items processed: <I>
Deferred (dirty working copy): <D>
Pages touched: <M>
Moved to category: <N>    Left in inbox (needs sorting): <K>

Needs your attention:
- 01_inbox/<file>  candidates: [03_work, 05_learn]
  (rationale: ...)

Deferred this run (will retry when user commits/closes edits):
- session <id>  files=[02_diary/<date>.md, 03_work/<page>.md]
```
End with a single actionable next step.

## Guardrails

- **Idempotent**: `cursors.json` + `ingest-log.jsonl` ensure re-runs are
  no-ops on already-processed content.
- **Never write to a file with uncommitted modifications in the vault
  working copy.** The user may be live-editing it; our append would race
  with the editor buffer and get silently overwritten on save. Defer the
  session (see Procedure §2.d2) and retry on the next run.
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
