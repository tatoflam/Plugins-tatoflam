# claude-wiki

A Claude Code plugin that turns your conversation history across every
project into a compounding, Obsidian-friendly knowledge base — inspired by
[Karpathy's LLM wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Two-layer architecture

The pipeline separates **reliable capture** from **thoughtful curation**:

```
SessionEnd hook ──▶ queue.jsonl ──▶ /wiki-ingest ──▶ _staging/ + 02_diary/   (capture layer)
                                    (non-interactive,      │
                                     conflict-free)        ▼
                                                     /wiki-distill ──▶ 00/03/04/05/06/07 + home.md   (knowledge layer)
                                                     (attended)             │
                                                                            ▼
                                                                      /wiki-query
                                                                  (answers with citations)
```

1. A **SessionEnd hook** enqueues every Claude Code session's transcript
   pointer to `~/.claude/wiki/state/queue.jsonl`.
2. **`/wiki-ingest`** (runs non-interactively from the hook) drains the
   queue AND any notes dropped into `01_inbox/`, writing one **digest
   per input into `_staging/`** plus a user-activity diary entry. It
   never touches curated pages, so it can never conflict with your open
   editors — every session lands on first processing, before transcript
   retention (~30 days) can delete the source.
3. **`/wiki-distill`** (run attended, on demand) promotes staged digests
   into curated pages with a stable structure — `Summary / 現在の状態 /
   決定事項 / 手順・Runbook / 経緯 / Links` — updates the self-model in
   `00_self/`, and maintains `home.md` as the human entry point.
4. **`/wiki-query`** answers questions from the knowledge layer with
   citations: state questions from 現在の状態, decision questions from
   決定事項, how-to from 手順・Runbook, persona questions from 00_self.
   Undistilled staging content is used only as a labeled fallback.
5. Supporting skills: **`/wiki-lint`** (audit contradictions/orphans/
   stale), **`/wiki-status`** (queue + staging backlog + page stats).

The vault itself is a separate, publishable git repo — Obsidian opens it
directly; push it to GitHub when you want.

## Categories (00-07)

| # | Folder | Layer | Purpose |
|---|---|---|---|
| 00 | `00_self/` | knowledge | Digital-twin core: profile, values, skills, goals, preferences |
| 01 | `01_inbox/` | raw | Bidirectional: unsorted inputs + ingest failures |
| 02 | `02_diary/` | capture | `YYYY-MM-DD.md` — user activity, append-only, no telemetry |
| 03 | `03_work/` | knowledge | Work: projects, meetings, pro learnings |
| 04 | `04_life/` | knowledge | Private life |
| 05 | `05_learn/` | knowledge | Tech notes, reading notes, study |
| 06 | `06_output/` | knowledge | Externally-published artifacts (by you, LLMs, services) |
| 07 | `07_archive/` | knowledge | Deprecated / completed |

Plus `_staging/` (captured digests awaiting distill; `_staging/archive/`
after) and root files `home.md` (curated entry point), `index.md`
(auto catalog), `log.md` (operation telemetry), `_schema.md` (mirror).

Full definitions and rules in [schema.md](./schema.md).

## Install

```bash
# The repo at https://github.com/tatoflam/Plugins-tatoflam is a marketplace.
# Register it once and install this plugin:
/plugin marketplace add tatoflam/Plugins-tatoflam
/plugin install claude-wiki@plugins-tatoflam
```

Or from a local clone:

```bash
# In ~/.claude/settings.json:
"extraKnownMarketplaces": {
  "plugins-tatoflam": {
    "source": {
      "source": "directory",
      "path": "$HOME/repo/github/tatoflam/Plugins-tatoflam"
    }
  }
}
# then:  /plugin install claude-wiki@plugins-tatoflam
```

## Configuration

The vault path is hard-coded to `~/repo/github/tatoflam/v` in the skills
and schema.md. Fork and edit if yours is elsewhere — all references use
`~/...` style paths so replacing the vault location is a text-search
operation.

Runtime state lives in `~/.claude/wiki/state/` (queue, cursors,
ingest-log, hook-errors). The hook auto-creates this on first use.

## Operation

1. Work normally in any project. On session end, the hook enqueues and
   ingest captures to `_staging/` automatically.
2. Drop raw notes into `01_inbox/` whenever.
3. Run `/wiki-distill` when the staging backlog builds up (ingest and
   `/wiki-status` tell you) — this is where knowledge gets organized.
4. Ask the vault things with `/wiki-query`; browse via `home.md` in
   Obsidian; `git push` when you like.
5. Run `/wiki-lint` weekly, `/wiki-status` any time.

## Why not just RAG over transcripts?

Karpathy's argument: transcripts are raw and noisy. A curated wiki
compounds value — every ingest strengthens the graph. The critical
reception of that gist is valid (token bloat at scale, provenance
concerns), so this plugin mitigates by:

- Splitting capture (mechanical, lossless) from curation (attended,
  quality-controlled) so neither degrades the other
- Preferring updates over new pages (de-duplication)
- Requiring cross-links on every edit (graph stays connected)
- Flagging contradictions rather than overwriting silently
- Requiring published-evidence for `06_output/` (no fake artifacts)
- Keeping provenance: digests are archived, never deleted; every page
  cites its source sessions
- `/wiki-lint` for periodic health checks

## Not included / by design

- No auto-push to GitHub from skills. User (or their hook) controls when
  to publish.
- No vector search / embeddings. Obsidian's graph + `rg` is enough at
  personal scale. Reconsider at ~500 pages.
- No writing into the vault from query-time skills. `/wiki-ingest`
  writes the capture layer; `/wiki-distill` writes the knowledge layer.
- `/wiki-distill` is deliberately NOT hooked to run non-interactively —
  curation quality needs an attending human.
