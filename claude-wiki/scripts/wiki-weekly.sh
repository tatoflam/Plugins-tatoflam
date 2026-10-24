#!/usr/bin/env bash
# Weekly loop runner: pull vault + todo → claude -p /claude-wiki:wiki-weekly →
# push both → notify. Launched by launchd (com.tatoflam.wiki-weekly, Sunday
# 08:00 JST) on the host Mac; safe to run by hand.
#
#   wiki-weekly.sh            run now
#   wiki-weekly.sh --dry-run  pull and show what would run, no claude, no push
#
# Notification: macOS notification on this Mac, plus $WIKI_NOTIFY_CMD (if set
# in ~/.claude/wiki/config/weekly.conf) is run with the summary as $1 — hook
# for ntfy / mail / anything that reaches the phone.

set -u

VAULT="${WIKI_VAULT:-${HOME}/repo/github/tatoflam/v}"
TODO="${WIKI_TODO_DIR:-${HOME}/repo/gitlab/tatoflam/todo}"
STATE="${HOME}/.claude/wiki/state"
CONF_DIR="${HOME}/.claude/wiki/config"
LOG="${STATE}/weekly.log"
LOCK_DIR="${STATE}/weekly.lock"
TIMEOUT_SEC="${WIKI_WEEKLY_TIMEOUT_SEC:-3600}"
DRY=0; [[ "${1:-}" == "--dry-run" ]] && DRY=1

[[ -f "${CONF_DIR}/weekly.conf" ]] && . "${CONF_DIR}/weekly.conf"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"
# A stalled ssh (seen with GitLab on 2026-10-24) must not hang the job forever.
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o BatchMode=yes}"
mkdir -p "${STATE}"
exec >>"${LOG}" 2>&1

ts() { date -u +%FT%TZ; }
echo ""; echo "=== $(ts) wiki-weekly start (pid $$, dry=${DRY}) ==="

# volta's shim does not work under launchd; insist on the native binary.
CLAUDE="$(command -v claude || true)"
case "${CLAUDE}" in
  ""|*/.volta/*) [[ -x "${HOME}/.local/bin/claude" ]] && CLAUDE="${HOME}/.local/bin/claude" || { echo "native claude not found"; exit 1; } ;;
esac
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "unsetting ANTHROPIC_API_KEY (use the claude.ai login)"; unset ANTHROPIC_API_KEY
fi

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  owner="$(cat "${LOCK_DIR}/pid" 2>/dev/null || true)"
  if [[ -n "${owner}" ]] && kill -0 "${owner}" 2>/dev/null; then echo "another run (pid ${owner}) is active"; exit 0; fi
  rm -rf "${LOCK_DIR}"; mkdir "${LOCK_DIR}"
fi
echo $$ > "${LOCK_DIR}/pid"
trap 'rm -rf "${LOCK_DIR}"' EXIT

notify() {
  local msg="$1"
  /usr/bin/osascript -e "display notification \"${msg//\"/\'}\" with title \"wiki-weekly\"" 2>/dev/null || true
  if [[ -n "${WIKI_NOTIFY_CMD:-}" ]]; then ${WIKI_NOTIFY_CMD} "${msg}" || echo "notify cmd failed"; fi
}

fail() {
  local stage="$1"
  echo "FAILED at ${stage}"
  if [[ -d "${VAULT}/.git" && ${DRY} -eq 0 ]]; then
    printf -- '- %s  op:weekly  failed@%s (see ~/.claude/wiki/state/weekly.log)\n' "$(ts)" "${stage}" >> "${VAULT}/log.md"
    git -C "${VAULT}" add log.md && git -C "${VAULT}" commit -qm "weekly: failed@${stage}" || true
    push_vault
  fi
  notify "週次ジョブ失敗: ${stage}"
  exit 1
}

vault_is_private() {
  local vis=""
  if command -v gh >/dev/null 2>&1; then
    vis="$(cd "${VAULT}" && gh repo view --json visibility -q .visibility 2>/dev/null || true)"
  fi
  # Hosts without gh: wiki-setup.sh records the visibility verified on a host that has gh.
  [[ -z "${vis}" && -f "${CONF_DIR}/push.conf" ]] && vis="$(sed -n 's/^vault_visibility=//p' "${CONF_DIR}/push.conf")"
  [[ "${vis}" == "PRIVATE" || "${vis}" == "INTERNAL" ]]
}

push_vault() {
  vault_is_private || { echo "vault push skipped: visibility not confirmed PRIVATE"; return 1; }
  git -C "${VAULT}" pull --rebase --autostash -q || { git -C "${VAULT}" rebase --abort 2>/dev/null; echo "vault pull failed"; return 1; }
  git -C "${VAULT}" push -q || { echo "vault push failed"; return 1; }
}

push_todo() {
  git -C "${TODO}" pull --rebase --autostash -q || { git -C "${TODO}" rebase --abort 2>/dev/null; echo "todo pull failed"; return 1; }
  git -C "${TODO}" push -q || { echo "todo push failed"; return 1; }
}

# 1. pull the plugin itself (this host may lag behind the dev Mac), then both repos
PLUGIN_REPO="$(cd "$(dirname "$0")/../.." && pwd)"
git -C "${PLUGIN_REPO}" pull --ff-only -q || echo "plugin pull failed (continuing with local copy)"
git -C "${VAULT}" pull --rebase --autostash -q || { git -C "${VAULT}" rebase --abort 2>/dev/null; fail "vault-pull"; }
git -C "${TODO}" pull --rebase --autostash -q || { git -C "${TODO}" rebase --abort 2>/dev/null; fail "todo-pull"; }

if (( DRY )); then
  echo "dry-run: would run ${CLAUDE} -p /claude-wiki:wiki-weekly in ${VAULT}"
  python3 "$(dirname "$0")/todo_parse.py" --todo-dir "${TODO}" --projects | head -c 400; echo
  exit 0
fi

# 2. run the skill (watchdog: kill if it stalls)
OUT="$(mktemp -t wiki-weekly)"
export WIKI_INGEST_WORKER=1   # keep the SessionEnd auto-ingest hook from re-firing
( cd "${VAULT}" && "${CLAUDE}" --dangerously-skip-permissions -p "/claude-wiki:wiki-weekly" ) >"${OUT}" 2>&1 &
pid=$!
( sleep "${TIMEOUT_SEC}"; kill -0 "${pid}" 2>/dev/null && { kill -TERM "${pid}"; sleep 10; kill -KILL "${pid}"; } ) 2>/dev/null &
wd=$!
rc=0; wait "${pid}" || rc=$?
kill "${wd}" 2>/dev/null || true
cat "${OUT}"
(( rc == 0 )) || fail "claude(rc=${rc})"

# 3. guard: the todo repo may only gain _proposals/ files
stray="$(git -C "${TODO}" status --porcelain | grep -v ' _proposals/' || true)"
[[ -z "${stray}" ]] || { echo "todo has non-proposal changes:"; echo "${stray}"; fail "todo-guard"; }

# 4. push both
push_vault || fail "vault-push"
push_todo || fail "todo-push"

summary="$(grep -m1 '^WEEKLY_SUMMARY:' "${OUT}" | sed 's/^WEEKLY_SUMMARY: *//')"
notify "${summary:-週次ジョブ完了}"
rm -f "${OUT}"
echo "=== $(ts) wiki-weekly done ==="
