---
name: wiki-distill
description: Promote captured session digests from _staging/ into the curated knowledge layer (00_self / 03_work / 04_life / 05_learn / 06_output). Groups digests by target page, merges them into the standard page structure (Summary / 現在の状態 / 決定事項 / 手順・Runbook / 経緯 / Links), updates the self-model in 00_self, maintains home.md, archives processed digests, and commits. Run attended. Use when the user says "distill", "整理", "蒸留", "wikiを整理", or runs /wiki-distill, or when ingest/status reports a staging backlog.
---

# /wiki-distill

Integrate the capture layer into the knowledge layer of the vault at
`~/repo/github/tatoflam/v`. The canonical rules live in the plugin's
`schema.md` — **read §"Distillation rules" and §"Curated page standard
structure" first**.

This is the thoughtful, attended half of the pipeline: `/wiki-ingest`
captures reliably; this skill turns those captures into knowledge a
query can answer from. Quality over speed — you are writing pages a
human (and `/wiki-query`) will trust.

## Paths

- **Vault**: `~/repo/github/tatoflam/v`
- **Input**: `.md` files directly under `<vault>/_staging/` (the backlog)
- **Output**: curated pages (00/03/04/05/06/07), `home.md`, `index.md`;
  processed digests move to `<vault>/_staging/archive/`
- **Schema**: `${CLAUDE_PLUGIN_ROOT}/schema.md`

If `_staging/` has no digests, report "nothing to distill" and stop.

## Procedure

### 1. Survey the backlog
Read every digest's frontmatter (`session / captured / target /
category / tags / confidence / diary_pending`). Group by `target`.
Re-judge each proposed target: grep the vault for a better existing
page (prefer update > create); low-confidence digests may need a
different category than proposed. Show the user the plan:
`<N> digests → <M> pages (X updates, Y creates)` before writing.

### 2. Handle dirty targets (attended — no defer)
For each target page, check `git -C <vault> status --porcelain -- <path>`.
If dirty, ask the user on the spot: commit their edits first, integrate
around them, or skip that group this run. Never silently overwrite
uncommitted user edits.

### 3. Integrate each group
For each target page, merge the group's digest bodies into the standard
structure (schema.md):

- **`## Summary`** — refresh if the project's nature changed.
- **`## 現在の状態`** — overwrite with the latest snapshot. Move the
  displaced previous state into `## 経緯` with its date. This section
  answers "今どうなってる？" — keep it current and self-contained.
- **`## 決定事項`** — append `- YYYY-MM-DD: <decision> — <reason>`.
  Cumulative; never silently remove. Answers "なぜそう決めた？".
- **`## 手順・Runbook`** — add/refresh reproducible operations.
  Answers "どうやるんだっけ？".
- **`## 経緯`** — append compressed timeline entries (1-2 lines per
  event). If the section has grown noisy, consolidate same-topic
  entries; details stay reachable via `sources:`, diary links, and
  `_staging/archive/`.
- **`## Links`** — keep ≥ 1 `[[wiki-link]]`; cross-link related pages.
- **Frontmatter** — merge digest `sources` into `sources:`, set
  `updated:` to today, merge tags per schema taxonomy.
- **Contradictions** you cannot resolve: keep both versions under a
  `> [!warning] Contradiction` callout with source ids. When the newer
  information clearly supersedes, replace and note the supersession in
  経緯.
- **06_output evidence** in any digest: file it in `06_output/YYYY-MM.md`
  per schema.md §"06_output/ auto-detection".
- **New pages** use the full standard template with the category's
  primary tag. **Never create session-dated H2 append silos.**
- 05_learn pages keep Summary/Details but the same principle applies:
  stable headings = topics; chronology quarantined.

### 4. Self-model pass (00_self)
Scan the whole batch for self signals: preferences (working style,
communication), judgment criteria, skill acquisitions, goal progress,
value statements. Update the matching 00_self page (`profile / skills /
values / goals / preferences`) with dated entries. Be conservative —
only durable signals, not one-off moods. If nothing qualifies, change
nothing.

### 5. Land pending diary entries
For each digest with `diary_pending:`, append the entry to its day's
`02_diary/<date>.md` (resolve dirtiness with the user as in step 2).

### 6. Archive processed digests
`git mv` each integrated digest to `_staging/archive/`. Never delete.
Digests you deliberately skipped (dirty target, user said later) stay
in `_staging/`.

### 7. Maintain home.md
Update `<vault>/home.md`: active 03_work / 04_life projects (one line
each: name + current-state gist), recent major decisions (last ~2
weeks), link to 00_self pages. Remove projects that became inactive or
archived. Curated prose — this is the human entry point, not a catalog.

### 8. Meta refresh + commit
- Regenerate `index.md` (same format as /wiki-ingest; exclude `_staging/`).
- Append to `log.md`:
  ```
  - <ISO>  op:distill  staged=<N> pages=<M> created=<C> self=<S> home=<updated|unchanged> backlog_left=<B>
  ```
- Commit:
  ```
  cd ~/repo/github/tatoflam/v
  git add -A _staging 00_self 03_work 04_life 05_learn 06_output 07_archive 02_diary home.md index.md log.md
  git diff --cached --quiet || git commit -m "distill: <N> digests → <M> pages (<C> new)"
  ```
  Do NOT push (hook/user decides).

### 9. Report
```
Digests distilled: <N> → pages touched: <M> (created: <C>)
Self-model updates: <list or none>
home.md: <updated|unchanged>
Skipped (left in staging): <K> — <reasons>
Backlog remaining: <B>
```
End with one actionable next step (e.g., remaining dirty page to commit).

## Guardrails

- **Attended only** — designed for interactive runs; do not wire into
  non-interactive hooks. Ask the user when judgment calls arise (dirty
  targets, ambiguous merges, contradictions).
- **Nothing is silently lost**: 現在の状態 displacement goes to 経緯;
  digests go to `_staging/archive/`, never deleted; 決定事項 is
  append-only.
- **Never edit** `ようこそ.md`, `make folders composition.md`, `_schema.md`,
  or rewrite `log.md` history.
- **Never push to GitHub.**
- **Per-run cap**: ~30 digests; if the backlog is larger, do the oldest
  first and report the remainder.
- **Idempotent-ish**: a digest is either in `_staging/` (pending) or
  `_staging/archive/` (done); re-running never double-integrates.
