# claude-wiki

A Claude Code plugin that turns your conversation history across every
project into a compounding, Obsidian-friendly knowledge base — inspired by
[Karpathy's LLM wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## What it does

1. A **SessionEnd hook** enqueues every Claude Code session's transcript
   pointer to `~/.claude/wiki/state/queue.jsonl`.
2. The **`/wiki-ingest`** skill drains that queue AND any notes the user
   manually dropped into the vault's `01_inbox/`, classifies each into
   eight categories (00-07), appends a per-day diary entry, and commits
   to the vault's git repo.
3. Three supporting skills: **`/wiki-query`** (read the vault),
   **`/wiki-lint`** (audit contradictions/orphans/stale), **`/wiki-status`**
   (queue + page stats).

The vault itself is a separate, publishable git repo — Obsidian opens it
directly; push it to GitHub when you want.

## Categories (00-07)

| # | Folder | Purpose |
|---|---|---|
| 00 | `00_self/` | Profile, values, skills |
| 01 | `01_inbox/` | Bidirectional: unsorted inputs + ingest failures |
| 02 | `02_diary/` | `YYYY-MM-DD.md` — one file per day, append-only |
| 03 | `03_work/` | Work: projects, meetings, pro learnings |
| 04 | `04_life/` | Private life |
| 05 | `05_learn/` | Tech notes, reading notes, study |
| 06 | `06_output/` | Externally-published artifacts (by you, LLMs, services) |
| 07 | `07_archive/` | Deprecated / completed |

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

1. Work normally in any project. On session end, the hook enqueues.
2. Drop raw notes into `01_inbox/` whenever.
3. Run `/wiki-ingest` to drain both sources into the vault.
4. Browse in Obsidian; `git push` the vault when you like.
5. Run `/wiki-lint` weekly, `/wiki-status` any time.

## Why not just RAG over transcripts?

Karpathy's argument: transcripts are raw and noisy. A curated wiki
compounds value — every ingest strengthens the graph. The critical
reception of that gist is valid (token bloat at scale, provenance
concerns), so this plugin mitigates by:

- Preferring updates over new pages (de-duplication)
- Requiring cross-links on every edit (graph stays connected)
- Flagging contradictions rather than overwriting silently
- Requiring published-evidence for `06_output/` (no fake artifacts)
- `/wiki-lint` for periodic health checks

## Not included / by design

- No auto-push to GitHub. User controls when to publish.
- No vector search / embeddings. Obsidian's graph + `rg` is enough at
  personal scale. Reconsider at ~500 pages.
- No writing into the vault from query-time skills. Only `/wiki-ingest`
  edits the vault.
