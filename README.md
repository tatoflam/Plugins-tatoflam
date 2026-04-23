# Plugins-tatoflam

Personal Claude Code plugin marketplace by [@tatoflam](https://github.com/tatoflam).

## Plugins

| Name | Description |
|---|---|
| [claude-wiki](./claude-wiki) | Karpathy-style LLM wiki. SessionEnd hook + `/wiki-ingest` skill turn conversations across every project into an 8-category Obsidian vault. |

## Install

```bash
/plugin marketplace add tatoflam/Plugins-tatoflam
/plugin install <plugin-name>@plugins-tatoflam
```

Or locally:

```jsonc
// ~/.claude/settings.json
{
  "extraKnownMarketplaces": {
    "plugins-tatoflam": {
      "source": {
        "source": "directory",
        "path": "$HOME/repo/github/tatoflam/Plugins-tatoflam"
      }
    }
  }
}
```

## License

MIT.
