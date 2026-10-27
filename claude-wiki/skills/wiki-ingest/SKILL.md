---
name: wiki-ingest
description: Drain both the session queue AND the manual inbox into the vault's capture layer. Reads session transcripts enqueued by the SessionEnd hook, plus any .md the user dropped into 01_inbox/, writes one digest per input into _staging/ (with a proposed classification for /wiki-distill and a match against the todo week), extracts deliverables into 06_output/catalog/, regenerates the day's diary roll-up, and commits to the vault. Never touches curated pages. Use when the user says "ingest", "update wiki", "取り込み", "wiki更新", or runs /wiki-ingest.
---

# /wiki-ingest

Capture new Claude Code sessions and user-dropped inbox notes into the
**capture layer** (`_staging/` + `02_diary/` + `06_output/catalog/`) of the vault at
`~/repo/github/tatoflam/v`. The canonical rules live in the plugin's
`schema.md` (sibling of this directory) — **read it first**.

This skill is the reliable, non-interactive half of the pipeline. It
NEVER writes to curated pages (00/03/04/05/06/07) — integration is
`/wiki-distill`'s job, run attended. Because staging writes are new-file
creations, there is nothing to conflict with and nothing to defer:
**every enqueued session lands on first processing**, before Claude
Code's ~30-day transcript retention can delete the source.

## Paths

- **Vault**: `~/repo/github/tatoflam/v` (Obsidian vault; its own git repo).
- **Staging**: `<vault>/_staging/` (digests) and `<vault>/_staging/archive/`
  (distilled digests — owned by /wiki-distill, never write there).
- **Runtime state**: `~/.claude/wiki/state/`
  - `queue.jsonl` — session pointers enqueued by the SessionEnd hook.
  - `cursors.json` — `{ "<transcript_path>": <byte_offset> }` for
    incremental reads.
  - `ingest-log.jsonl` — machine-parseable audit trail.
  - `hook-errors.log` — hook failures (tail if something seems missing).
- **Schema**: `${CLAUDE_PLUGIN_ROOT}/schema.md` (the plugin's own schema).
- **todo repo** (read-only): `${WIKI_TODO_DIR:-~/repo/gitlab/tatoflam/todo}`.
  If it is missing, skip todo matching (`todo:` omitted) and say so in
  the report — never fail the ingest over it.

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

Load the todo week once per distinct session date (JST):
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/todo_parse.py --date <YYYY-MM-DD> --projects
```
Keep `week.file`, the items (`id`, `path`, `vault`, `tags`, `star`) for
matching in step 2.

### 2. Process each input item
For each session in the queue AND each inbox file:

a. **Read the content.**
   - Sessions: read transcript from `cursors[path]` to end. Parse only
     `"type":"user"` and `"type":"assistant"` lines. Cap at the last ~200
     turns. If truncated, note it in the digest.
   - Inbox: read the file verbatim.

b. **Extract signal.** Drop tool-call noise, resolved typos, transient
   errors. Keep: decisions, requirements, surprising findings, named
   entities, external links, artifacts published anywhere. Verbose is
   fine — distill compresses later; losing signal here loses it forever.

c. **Classify (as a proposal).** Score the content against
   00/03/04/05/06/07 and pick the integration target page (grep the
   vault for an existing page on the same subject — prefer update >
   create, but you are only *proposing*; distill re-judges).
   03_work / 04_life are project folders (schema.md §"Project folders"):
   write `target:` as the existing page's real path
   (`03_work/012_meguru-crm/meguru-crm`, or a sub-page in that folder),
   found with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault_paths.py resolve <category>/<slug>`;
   for a new project write `<category>/<slug>` — distill assigns the number.

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

   **Wiki meta-session check**: if the session's only content is running
   `/wiki-*` skills (ingest/distill/lint/status runs, including this
   skill's own prior runs), do NOT create a digest or diary entry —
   acknowledge it in the `log.md` line summary and mark it processed.

c2. **Match against the todo week.** Using the item list from step 1
   (items carry the vault pages / tags mapped via `_projects.yml`),
   decide which todo items this session advanced. Prefer the deepest
   matching item; at most ~3 items. For each: `confidence` (high = the
   session plainly worked on that item; medium = same project, plausibly
   that item; low = guess) and `progress` (`advanced` = real movement,
   `done-candidate` = the session shows the item is finished, e.g. a
   filing submitted, a PR merged that closes it; `touched` = discussed
   only). If nothing matches, `unplanned: true`. Never decide "done" —
   only the user's mark is completion.

d. **Write the digest** to `_staging/<YYYY-MM-DD>-<session8>.md`
   (sessions) or `_staging/<YYYY-MM-DD>-inbox-<slug>.md` (inbox), using
   the frontmatter from schema.md §"_staging/":
   `session / captured / target / category / tags / confidence / todo`.
   New file creation only —
   if the name collides (same session re-captured), suffix `-2`.

e. **Low confidence → inbox.** If no category scores clearly, still
   write the digest (with `confidence: low` and your best-guess target)
   AND leave/create the note in `01_inbox/` with a
   `> [!question] Needs sorting\n> Candidate categories: <list>`
   callout so the user sees it.

f. **Extract deliverables** (sessions only), *before* moving the cursor:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_artifacts.py \
     --transcript <path> --offset <cursors[path] or 0> --write
   ```
   It merges into `<vault>/06_output/catalog/YYYY-MM.md` (dedup by
   path/URL). If a session wrote a deliverable at the vault root, move it
   with `git mv` (or `mv` if untracked) to the project folder's `files/`
   when it belongs to an existing project, otherwise to
   `06_output/files/YYYY-MM/`, and run `extract_artifacts.py --vault-files --write`.

g. **Mark source processed.**
   - Sessions: set `cursors[path]` to current byte length; flip
     `processed: true` in the queue.
   - Missing transcript (never landed / deleted): log
     `<ISO>  session=<id>  skip=missing_transcript` to `hook-errors.log`,
     flip `processed: true`, count it in the report.
   - Inbox files captured into a digest: delete the original (its content
     lives in the digest; git history preserves the original).
   - Inbox files that stayed (low confidence): keep in place with the
     question callout.

### 2b. Regenerate the diary for every touched date
For each JST date that received a new digest this run (its filename
date and its `captured` date) (and is
2026-10-24 or later), rebuild `02_diary/<date>.md` from scratch using
**all** digests of that date — in `_staging/` and `_staging/archive/`,
a digest belongs to date D when its filename date is D **or** its
`captured:` timestamp falls on D in JST (filenames carry the session's
*start* date, so a session running 10-22 → 10-24 is only found via
`captured`; use the part of its body that happened on D) — plus that
date's lines in `06_output/catalog/`. Format: schema.md §"`02_diary/` rules"
(今日のまとめ / 予定に対して / 予定外 / 出したもの / 持ち越し + folded
session index). 予定に対して comes from digests' `todo.items` (group by
todo heading); 予定外 from `todo.unplanned: true`. Body ≈ 30 lines; no
command arguments, test counts or telemetry. Links to projects use the
folder path (`[[03_work/012_meguru-crm/meguru-crm]]`); resolve each
digest's `target:` / `todo` vault refs with `vault_paths.py resolve`
before writing them. Overwrite the file (it is machine-owned). Wiki meta-sessions contribute nothing. Dates before
2026-10-24 are never rewritten.

### 3. Audit trail (machine)
Append one JSONL line per input to `~/.claude/wiki/state/ingest-log.jsonl`:
```json
{"ts":"<ISO>","source_type":"session|inbox","source_id":"<id or path>",
 "digest":"_staging/2026-07-09-ab12cd34.md","diary":true,
 "confidence":"high","unsortable":false}
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
   chronological. 03_work / 04_life list every page inside the project
   folders (`- [[03_work/012_meguru-crm/meguru-crm]]`, sub-pages after
   their main page), in folder-number order; never list `files/`. Exclude dotfiles, `_staging/`, and the root welcome
   notes (`ようこそ.md`, `make folders composition.md`). Include
   `01_inbox` as a count line only: `_<N> pending items_`.

b. **Append to `<vault>/log.md`** (create if missing with a header):
   ```
   - <ISO>  op:ingest  S=<sessions> I=<inbox> staged=<D> diary=<E> missing=<K> staging_backlog=<B>
   ```
   `staging_backlog` = count of `.md` files directly under `_staging/`
   after this run (i.e., not yet distilled). Telemetry detail
   (meta-acks, missing ids, races) goes in a parenthetical on this line
   — never in the diary.

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
git add _staging 02_diary 06_output/catalog 06_output/files 03_work/*/files 04_life/*/files index.md log.md _schema.md 01_inbox
git diff --cached --quiet || git commit -m "capture: <S> sessions + <I> inbox → <D> digests (backlog <B>)"
```
Scope `git add` to capture-layer paths — never `git add -A` (it would
sweep up the user's in-progress edits to curated pages). **Do NOT push.**

### 7. Report
```
Sessions processed: <S>    Inbox items processed: <I>
Digests written: <D>    Diaries regenerated: <E>    Deliverables: +<A>    Missing transcripts: <K>
Todo: week <file> — matched <M>, unplanned <U>, done-candidates <C>
Staging backlog (awaiting /wiki-distill): <B>

Needs your attention:
- 01_inbox/<file>  candidates: [03_work, 05_learn]
  (rationale: ...)
```
If `B >= 10` or the oldest digest is > 7 days old, end with:
"Staging backlog is piling up — run `/wiki-distill` to integrate it."
Otherwise end with a single actionable next step.

## Guardrails

- **Never write to curated pages** (00/03/04/05/07, `06_output/YYYY-MM.md`
  or `home.md`). Capture goes to `_staging/`, `02_diary/<date>.md`,
  `06_output/catalog/`, `06_output/files/` and project folders' `files/` only. There is no
  dirty-target defer anymore — capture files are machine-owned.
- **Never write to the todo repo.** It is read-only for ingest.
- **Never write to `_staging/archive/`** — that's distill's output.
- **Idempotent**: `cursors.json` + `ingest-log.jsonl` ensure re-runs are
  no-ops on already-processed content.
- **Concurrent-run stand-down**: if another ingest is mid-flight
  (uncommitted `_staging/` files with mtime seconds ago, or a running
  worker pid), yield without writing — log the stand-down to
  `hook-errors.log`.
- **Never write runtime state into the vault.** Queue, cursors, logs all
  live under `~/.claude/wiki/state/`.
- **Never edit vault welcome files**: `ようこそ.md`,
  `make folders composition.md` at vault root — pre-existing user notes.
- **Never push to GitHub.**
- **Never delete pages.**
- **Per-run caps**: 20 sessions + 50 inbox files. Leftover stays queued.
- **Hook failures** (missing transcript, etc.) go to
  `~/.claude/wiki/state/hook-errors.log`; skip and continue the batch.
