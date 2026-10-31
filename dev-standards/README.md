# dev-standards

Coding standards enforced by tools rather than by long prose.

- **Skill `coding-standards`** names the references (OWASP ASVS, CWE Top 25, PEP 8, Google Shell Style)
  and how to suppress a false positive narrowly.
- **PostToolUse hook** (`Write|Edit`) runs on the edited file:
  - `ruff` with `E9,F,B,S` (pyflakes, bugbear, bandit rules) — `scripts/ruff.toml`, used only when the
    repo has no ruff config of its own
  - `shellcheck -S warning` for `.sh` / bash / sh shebangs
  - `gitleaks stdin` for secrets

  ruff / shellcheck findings are reported **only when the edit introduced them**: for `Edit` the baseline is
  the pre-edit text rebuilt from `old_string` / `new_string` (exact even when another session has
  uncommitted changes in the same file); for `Write` it is the `HEAD` version; a new file has none.
  Findings are matched by (rule, line text), so rewriting a line that already had a finding reports it
  again. Secrets are always reported. Exit 2 puts the findings in front of Claude.
  A linter that crashes is reported, not treated as a clean pass.
- **SessionStart hook** prints which of `ruff` / `shellcheck` / `gitleaks` are missing. In cloud sessions
  (`CLAUDE_CODE_REMOTE=true`) it installs them into `~/.local/bin` first.

Division of labour: this hook looks at one edit; `/security-review` looks at a branch before a PR.

## Local install

```bash
brew install ruff shellcheck gitleaks jq      # macOS
# Linux: uv tool install ruff; sudo apt-get install shellcheck jq; gitleaks from its GitHub release
```

```
/plugin install dev-standards --marketplace tatoflam/Plugins-tatoflam
```

Or, where the marketplace is already registered as `plugins-tatoflam`:

```jsonc
// ~/.claude/settings.json
{ "enabledPlugins": { "dev-standards@plugins-tatoflam": true } }
```

## Claude Code on the web

Cloud sessions load neither `~/.claude` nor plugins — not even ones a repo enables in its own
`.claude/settings.json`. So the same hook is copied into each repo:

```bash
dev-standards/scripts/sync-repo.sh <repo>          # copies into <repo>/.claude/, merges settings.json
dev-standards/scripts/sync-repo.sh --check <repo>  # exit 1 if the repo copy drifted
```

This writes `.claude/hooks/{check-edit.py,ensure-tools.sh,ruff.toml}`, `.claude/rules/coding-standards.md`
and two hook entries in `.claude/settings.json` (other keys are kept). Commit them. When a repo copy
exists, the plugin's hooks step aside so local sessions do not run the checks twice.

Tools are installed by the SessionStart hook on every cloud start. To make that a cached one-time step,
paste the install part of `ensure-tools.sh` into the environment's **Setup script** at claude.ai/code.
