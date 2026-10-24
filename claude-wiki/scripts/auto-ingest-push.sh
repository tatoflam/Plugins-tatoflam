#!/usr/bin/env bash
# SessionEnd hook (user-scope): after the plugin's enqueue-session.sh has
# appended the ending session to the ingest queue, fire a headless Claude
# session to drain the queue via /claude-wiki:wiki-ingest, then push the
# vault to origin.
#
# Registered in ~/.claude/settings.json under hooks.SessionEnd.
# Plugin-side hook (hooks/hooks.json in claude-wiki) still runs the enqueue;
# this script is additive.
#
# 2026-08 hardening, after the vault (then public) was found to contain client
# work and the pipeline had been livelocked since 2026-07-29:
#   * single-flight lock — concurrent runs used to mutually stand down forever
#   * watchdog — headless runs stall booting MCP and never drain the queue
#   * visibility guard — never push the vault to a public remote
#   * pull --rebase — origin gains CI commits daily, so bare push always failed
# 2026-10 (vault-todo-loop): two hosts (M1 + M5) ingest into the same vault.
#   * pull BEFORE ingest too, so the regenerated diary/index see the other
#     host's digests; regenerated files use merge=regen (.gitattributes)
#   * hosts without gh read the verified visibility from config/push.conf
#   * canonical copy lives in the plugin (scripts/); ~/.claude/wiki/hooks/
#     holds a symlink installed by wiki-setup.sh

set -u

VAULT="${HOME}/repo/github/tatoflam/v"
STATE="${HOME}/.claude/wiki/state"
ERR_LOG="${STATE}/hook-errors.log"
WORKER_LOG="${STATE}/ingest-worker.log"
LOCK_DIR="${STATE}/auto-ingest.lock"

# Kill a headless ingest that has not finished in this many seconds. Observed
# stalls sit at ~1-2s CPU for many minutes while booting MCP servers.
INGEST_TIMEOUT_SEC=900
# A lock whose owner PID is gone, or that is older than this, is stale.
LOCK_STALE_SEC=1800

# Recursion guard: the headless worker itself ends a Claude session, which
# re-fires SessionEnd. The worker sets this env var so nested invocations
# are no-ops.
if [[ "${WIKI_INGEST_WORKER:-}" == "1" ]]; then
  exit 0
fi

# Drain stdin so the hook runtime doesn't block (the plugin's enqueue hook
# has already consumed its own copy of the payload).
cat >/dev/null 2>&1 || true

log_err() { printf '%s  %s\n' "$(date -u +%FT%TZ)" "$*" >> "${ERR_LOG}"; }

# --- single-flight lock -----------------------------------------------------
# mkdir is atomic on macOS (no flock in the base system). The previous design
# had every run detect its peers and stand down, so with two or more runs in
# flight nothing ever drained. Now exactly one run proceeds and the rest exit
# immediately and silently.
acquire_lock() {
  if mkdir "${LOCK_DIR}" 2>/dev/null; then
    printf '%s' "$$" > "${LOCK_DIR}/pid"
    return 0
  fi

  local owner age
  owner="$(cat "${LOCK_DIR}/pid" 2>/dev/null || true)"

  if [[ -n "${owner}" ]] && kill -0 "${owner}" 2>/dev/null; then
    age=$(( $(date +%s) - $(stat -f %m "${LOCK_DIR}" 2>/dev/null || echo 0) ))
    if (( age < LOCK_STALE_SEC )); then
      return 1   # a healthy run owns the lock; this one is simply not needed
    fi
    log_err "lock: breaking stale lock held by live pid=${owner} age=${age}s (exceeds ${LOCK_STALE_SEC}s)"
    kill -TERM "${owner}" 2>/dev/null || true
  else
    log_err "lock: clearing orphaned lock (owner pid=${owner:-unknown} not running)"
  fi

  rm -rf "${LOCK_DIR}"
  if mkdir "${LOCK_DIR}" 2>/dev/null; then
    printf '%s' "$$" > "${LOCK_DIR}/pid"
    return 0
  fi
  return 1
}

# --- push safety ------------------------------------------------------------
# Refuse to push the vault anywhere public. Fails closed: if visibility cannot
# be determined, the commit stays local rather than risking exposure.
remote_is_private() {
  local vis=""
  if command -v gh >/dev/null 2>&1; then
    vis="$(gh repo view --json visibility -q .visibility 2>/dev/null || true)"
  fi
  if [[ -z "${vis}" && -f "${HOME}/.claude/wiki/config/push.conf" ]]; then
    vis="$(sed -n 's/^vault_visibility=//p' "${HOME}/.claude/wiki/config/push.conf")"
  fi
  case "${vis}" in
    PRIVATE|INTERNAL) return 0 ;;
    PUBLIC) log_err "push: REFUSED — remote is PUBLIC. Vault holds client work; make it private before enabling push."; return 1 ;;
    *)      log_err "push: could not determine remote visibility (got '${vis:-empty}'); skipping push"; return 1 ;;
  esac
}

# Fire-and-forget background worker so the session closes immediately.
(
  # Small delay to let the plugin's enqueue-session.sh finish flushing
  # queue.jsonl (hook ordering across plugins vs. user settings is not
  # contractually guaranteed).
  sleep 2

  export WIKI_INGEST_WORKER=1
  exec </dev/null >>"${WORKER_LOG}" 2>&1

  acquire_lock || exit 0
  trap 'rm -rf "${LOCK_DIR}"' EXIT

  echo ""
  echo "=== $(date -u +%FT%TZ) auto-ingest start (pid $$) ==="

  export PATH="${HOME}/.local/bin:/opt/homebrew/bin:${PATH}"
  if ! command -v claude >/dev/null 2>&1; then
    log_err "claude CLI not on PATH"
    exit 1
  fi

  # Pull first so the diary/index this run regenerates include digests the
  # other host pushed.
  if [[ -d "${VAULT}/.git" ]]; then
    git -C "${VAULT}" pull --rebase --autostash -q 2>/dev/null || {
      git -C "${VAULT}" rebase --abort 2>/dev/null || true
      log_err "pre-ingest pull failed in ${VAULT}; ingesting on local state"
    }
  fi

  # Watchdog: run the ingest in the background and kill it if it stalls, so a
  # hung run releases the lock instead of blocking every later run.
  claude --dangerously-skip-permissions -p "/claude-wiki:wiki-ingest" &
  ingest_pid=$!

  ( sleep "${INGEST_TIMEOUT_SEC}"
    if kill -0 "${ingest_pid}" 2>/dev/null; then
      kill -TERM "${ingest_pid}" 2>/dev/null || true
      sleep 10
      kill -KILL "${ingest_pid}" 2>/dev/null || true
    fi ) &
  watchdog_pid=$!

  ingest_rc=0
  wait "${ingest_pid}" || ingest_rc=$?
  kill "${watchdog_pid}" 2>/dev/null || true

  if (( ingest_rc != 0 )); then
    log_err "claude -p /claude-wiki:wiki-ingest failed or timed out rc=${ingest_rc}"
  fi

  if [[ -d "${VAULT}/.git" ]]; then
    cd "${VAULT}" || exit 1

    if remote_is_private; then
      # origin gains a CI "lint: daily health check" commit most days, so a
      # bare push is nearly always rejected as non-fast-forward.
      if ! git pull --rebase --autostash; then
        log_err "git pull --rebase failed in ${VAULT}; aborting rebase and leaving commits local"
        git rebase --abort 2>/dev/null || true
      elif ! git push; then
        log_err "git push failed in ${VAULT}"
      fi
    fi
  fi

  echo "=== $(date -u +%FT%TZ) auto-ingest done (rc=${ingest_rc}) ==="
) &
disown 2>/dev/null || true

exit 0
