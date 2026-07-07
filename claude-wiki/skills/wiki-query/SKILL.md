---
name: wiki-query
description: Answer a question from the curated knowledge layer of the wiki at ~/repo/github/tatoflam/v/ — the vault's primary interface. Answers state/decision/how-to questions from the standard page sections, persona questions from 00_self, cites every claim, and discloses freshness (undistilled staging items). Use when the user asks knowledge-base questions like "wikiで調べて", "what do we know about X", "今どうなってる？", or runs /wiki-query.
---

# /wiki-query

Answer questions from the vault's **knowledge layer**. This is the
vault's primary interface — the whole pipeline (capture → distill)
exists so this skill can answer from organized knowledge instead of
raw logs. If the knowledge layer is silent, fall back transparently to
the capture layer (staging digests, diary), clearly labeled as
unorganized; never blur the two.

## Paths

- **Knowledge layer** (primary): `00_self/`, `03_work/`, `04_life/`,
  `05_learn/`, `06_output/`, `07_archive/`, `home.md`
- **Capture layer** (fallback, label it): `_staging/*.md` (undistilled),
  `02_diary/`, `01_inbox/` (drafts)
- **Queue status** (freshness caveat): `~/.claude/wiki/state/queue.jsonl`
- **Schema reference**: `${CLAUDE_PLUGIN_ROOT}/schema.md`

## Procedure

1. **Parse the question.** Identify entities (repos, people, terms,
   technologies, dates) and the question archetype:
   - *State* ("今どうなってる？", "what's the status of X") →
     target pages' `## 現在の状態`
   - *Decision* ("なぜそう決めた？", "why did we choose X") →
     `## 決定事項`
   - *How-to* ("どうやるんだっけ？", "how do I X") →
     `## 手順・Runbook`
   - *Persona* (preferences, values, goals, "私はどう考える？",
     "どういうスタイルが好み？") → **00_self is the primary source**
     (`preferences`, `values`, `goals`, `profile`, `skills`)
   - *History* ("いつ", "what happened around date X") → `## 経緯`,
     then `02_diary/` for the date range
2. **Search the knowledge layer first.** `home.md` for orientation,
   then `rg`/`grep`: frontmatter `title:` and filenames, then full-text
   for entities. Resolve `[[wiki-links]]` one hop for context.
3. **Fallback to the capture layer** only when the knowledge layer
   lacks the answer or is stale: grep `_staging/*.md` (NOT archive)
   and `02_diary/`. Anything used from there MUST be labeled:
   `⚠ 未整理情報（staging/diary）からの回答 — /wiki-distill 未実施分`.
4. **Synthesize with citations.** Every claim cites its page:
   `(from [[0X_<folder>/<page>]])`. Quote frontmatter `sources:` when
   the user asks for provenance. Keep knowledge-layer answers and
   capture-layer supplements visually separate.
5. **Freshness disclosure.** Check and report at the end when relevant:
   - undistilled digests in `_staging/` touching the question's topic →
     `Staging has N related undistilled digests — run /wiki-distill.`
   - unprocessed queue items → `Queue has N unprocessed sessions — run
     /wiki-ingest for latest.`
   - the cited page's `updated:` is old relative to the question → say so.
6. **Never fabricate.** If neither layer has the answer, say plainly
   "vault に情報がない" — do not guess.
7. **Log the query.** Append one line to `<vault>/log.md`:
   ```
   - <ISO>  op:query  "<question-trimmed-to-80-chars>" → <top-page-cited or "no-match">
   ```
   This is the only write `/wiki-query` is permitted to make.

## Guardrails

- **Effectively read-only.** The only permitted write is the single
  log.md line (step 7). Never edit any page.
- **Label the layer.** Knowledge-layer answers are authoritative;
  capture-layer content is always marked as 未整理 / draft.
- **No raw-transcript fallback.** Do not open `~/.claude/projects/**/*.jsonl`
  unless the user explicitly asks.
- **No web fallback.** Don't web search unless the user explicitly asks.
- **Caveat inbox citations.** `01_inbox/` entries are drafts — note that
  when quoting them ("(draft, may not reflect final view)").
- If the user asks how the wiki itself works, point them to
  `${CLAUDE_PLUGIN_ROOT}/schema.md`.
