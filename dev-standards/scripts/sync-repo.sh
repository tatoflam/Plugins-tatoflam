#!/usr/bin/env bash
# Copy the dev-standards hook and rules into a repository, so that Claude Code on the web
# (which loads neither ~/.claude nor plugins) enforces the same checks.
#
#   sync-repo.sh <repo>          copy files and merge hooks into <repo>/.claude/settings.json
#   sync-repo.sh --check <repo>  exit 1 if the repo copy has drifted from this plugin
#
# Writes only under <repo>/.claude/. Commit the result yourself.
set -euo pipefail

check=0
if [[ "${1:-}" == "--check" ]]; then
  check=1
  shift
fi
repo="${1:?usage: sync-repo.sh [--check] <repo>}"
repo="$(cd "$repo" && pwd)"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin="$(dirname "$here")"

# source → destination (relative to the repo)
files=(
  "$here/check-edit.py:.claude/hooks/check-edit.py"
  "$here/ensure-tools.sh:.claude/hooks/ensure-tools.sh"
  "$here/ruff.toml:.claude/hooks/ruff.toml"
  "$plugin/templates/coding-standards.md:.claude/rules/coding-standards.md"
)

if ((check)); then
  drift=0
  for pair in "${files[@]}"; do
    src="${pair%%:*}" dst="$repo/${pair#*:}"
    if ! cmp -s "$src" "$dst"; then
      echo "drift: ${pair#*:}"
      drift=1
    fi
  done
  exit "$drift"
fi

command -v jq >/dev/null || { echo "sync-repo.sh: jq is required" >&2; exit 1; }

for pair in "${files[@]}"; do
  src="${pair%%:*}" dst="$repo/${pair#*:}"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
done
chmod +x "$repo/.claude/hooks/check-edit.py" "$repo/.claude/hooks/ensure-tools.sh"

# Merge our two hooks into settings.json, replacing earlier copies of them and keeping
# everything else.
settings="$repo/.claude/settings.json"
[[ -f "$settings" ]] || echo '{}' >"$settings"
tmp="$(mktemp)"
jq --indent 2 '
  def ours: (.hooks // []) | any((.command // "") | test("/\\.claude/hooks/(check-edit\\.py|ensure-tools\\.sh)$"));
  def put(event; entry): .hooks[event] = ([(.hooks[event] // [])[] | select(ours | not)] + [entry]);
  put("SessionStart"; {
    matcher: "startup|resume",
    hooks: [{type: "command", command: "${CLAUDE_PROJECT_DIR}/.claude/hooks/ensure-tools.sh", args: [], timeout: 300}]
  })
  | put("PostToolUse"; {
    matcher: "Write|Edit",
    hooks: [{type: "command", command: "${CLAUDE_PROJECT_DIR}/.claude/hooks/check-edit.py", args: [], timeout: 90}]
  })
' "$settings" >"$tmp"
mv "$tmp" "$settings"

echo "synced dev-standards into $repo/.claude/ — review and commit:"
git -C "$repo" status --short -- .claude/ 2>/dev/null || true
