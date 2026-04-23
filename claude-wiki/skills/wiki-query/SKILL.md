---
name: wiki-query
description: Answer a question using the curated wiki at ~/repo/github/tatoflam/v/ without touching raw session transcripts. Use when the user asks knowledge-base questions like "wikiで調べて", "what do we know about X", or runs /wiki-query.
---

# /wiki-query

Answer questions from the curated vault. This is the fast path — the wiki is
a compounding artifact, not a raw-document search. If the wiki cannot answer,
say so and suggest `/wiki-ingest` (new sessions may not be ingested yet).

## Paths

- **Vault**: `~/repo/github/tatoflam/v` — categories:
  `00_self`, `01_inbox`, `02_diary`, `03_work`, `04_life`, `05_learn`,
  `06_output`, `07_archive`.
- **Queue status** (for freshness caveat): `~/.claude/wiki/state/queue.jsonl`.
- **Schema reference**: `${CLAUDE_PLUGIN_ROOT}/schema.md`.

## Procedure

1. **Parse the question.** Identify entities (repos, people, terms,
   technologies, dates). Map to likely categories.
2. **Search the vault.** Use `rg`/`grep` under the vault root:
   - Start with frontmatter `title:` and filenames.
   - Then full-text for entities.
   - Resolve `[[wiki-links]]` to follow backlinks one hop.
   - Date-scoped questions ("what did I work on last week?") → read
     `02_diary/*.md` in the date range.
3. **Synthesize.** Answer from the pages found, citing each claim with the
   page path: `(from [[0X_<folder>/<page>]])`. Quote frontmatter `sources:`
   when the user asks for provenance.
4. **Freshness check.** If the queue has unprocessed items or the target
   page has an old `updated:`, say so at the end:
   `Queue has N unprocessed sessions + K inbox items — run /wiki-ingest for latest.`
5. **Never fabricate.** If the vault is silent, say so plainly.

## Guardrails

- **Read-only.** Never edit any file under the vault.
- **No raw-transcript fallback.** Do not open `~/.claude/projects/**/*.jsonl`
  unless the user explicitly asks.
- **No web fallback.** Don't web search unless the user explicitly asks.
- **Caveat inbox citations.** `01_inbox/` entries are drafts — note that
  when quoting them ("(draft, may not reflect final view)").
- If the user asks how the wiki itself works, point them to
  `${CLAUDE_PLUGIN_ROOT}/schema.md`.
