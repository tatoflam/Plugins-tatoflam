#!/usr/bin/env bash
# SessionStart hook: make sure the linters check-edit.py needs are on PATH.
#   cloud (CLAUDE_CODE_REMOTE=true): install what is missing
#   local: install nothing, only say what is missing
# Whatever is still missing is printed so it enters Claude's context: a hook that silently
# skips a linter must not look like a clean pass.
#
# Same step-aside rule as check-edit.py: with --plugin, defer to the repo copy if present.
set -u

if [[ "${1:-}" == "--plugin" && -f "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/ensure-tools.sh" ]]; then
  exit 0
fi

GITLEAKS_VERSION=8.30.1
BIN="$HOME/.local/bin"

missing() {
  local t out=""  # a string, not an array: an empty array trips set -u on macOS bash 3.2
  for t in ruff shellcheck gitleaks; do
    command -v "$t" >/dev/null 2>&1 || out="${out:+$out }$t"
  done
  echo "$out"
}

install_cloud() {
  mkdir -p "$BIN"
  export PATH="$BIN:$PATH"
  if ! command -v ruff >/dev/null 2>&1; then
    if command -v uv >/dev/null 2>&1; then
      uv tool install --quiet ruff
    elif command -v pipx >/dev/null 2>&1; then
      pipx install --quiet ruff
    else
      # Debian/Ubuntu mark the system Python as externally managed (PEP 668).
      python3 -m pip install --quiet --user ruff \
        || python3 -m pip install --quiet --user --break-system-packages ruff
    fi
  fi
  if ! command -v shellcheck >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    { sudo -n apt-get install -y -qq shellcheck || apt-get install -y -qq shellcheck; } >/dev/null 2>&1
  fi
  if ! command -v gitleaks >/dev/null 2>&1; then
    local arch tmp
    case "$(uname -m)" in
      x86_64) arch=x64 ;;
      aarch64 | arm64) arch=arm64 ;;
      *) arch="" ;;
    esac
    if [[ -n "$arch" ]]; then
      tmp="$(mktemp -d)"
      curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${arch}.tar.gz" \
        | tar -xz -C "$tmp" gitleaks && mv "$tmp/gitleaks" "$BIN/"
      rm -rf "$tmp"
    fi
  fi
  # Later hook processes inherit PATH from the session, not from this script.
  if [[ -n "${CLAUDE_ENV_FILE:-}" ]]; then
    echo "export PATH=\"$BIN:\$PATH\"" >>"$CLAUDE_ENV_FILE"
  fi
}

if [[ "${CLAUDE_CODE_REMOTE:-}" == "true" && -n "$(missing)" ]]; then
  install_cloud >/dev/null 2>&1
fi

gone="$(missing)"
if [[ -n "$gone" ]]; then
  echo "dev-standards: not on PATH: ${gone}. The edit hook skips these checks until they are installed (see the dev-standards README)."
fi
exit 0
