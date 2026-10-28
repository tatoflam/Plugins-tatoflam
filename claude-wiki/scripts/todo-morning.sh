#!/usr/bin/env bash
# Morning todo digest: pull todo → todo_today.py → notify-cli (Slack + macOS).
# Launched by launchd (com.tatoflam.todo-morning, daily 08:00) on the host Mac;
# safe to run by hand. Read-only on the todo repo (pull only).
#
#   todo-morning.sh             notify now
#   todo-morning.sh --dry-run   print the digest, no notification
#
# notify-cli profile: $TODO_NOTIFY_PROFILE (default "todo") in
# ~/.config/notify-cli/config.yaml.

set -u

TODO="${WIKI_TODO_DIR:-${HOME}/repo/gitlab/tatoflam/todo}"
STATE="${HOME}/.claude/wiki/state"
LOG="${STATE}/morning.log"
NOTIFY="${NOTIFY_BIN:-${HOME}/.local/bin/notify}"
PROFILE="${TODO_NOTIFY_PROFILE:-todo}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DRY=0; [[ "${1:-}" == "--dry-run" ]] && DRY=1

export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o BatchMode=yes}"
mkdir -p "${STATE}"
(( DRY )) || exec >>"${LOG}" 2>&1

ts() { date -u +%FT%TZ; }
echo "=== $(ts) todo-morning start (dry=${DRY}) ==="

# A failed pull still notifies, from the local copy, tagged so it isn't trusted blindly.
stale=""
git -C "${TODO}" pull --ff-only -q || { stale="（pull失敗・ローカルの内容）"; echo "todo pull failed"; }

if ! out="$(python3 "${HERE}/todo_today.py" --todo-dir "${TODO}")"; then
  echo "todo_today.py failed"
  (( DRY )) || "${NOTIFY}" send --profile "${PROFILE}" --status failure --title "ToDo 朝通知: 失敗" \
    --message "todo_today.py が失敗しました（~/.claude/wiki/state/morning.log）"
  exit 1
fi
title="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["title"])' <<<"${out}")${stale}"
message="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["message"])' <<<"${out}")"

if (( DRY )); then
  printf '%s\n\n%s\n' "${title}" "${message}"
  exit 0
fi
"${NOTIFY}" send --profile "${PROFILE}" --status info --title "${title}" --message "${message}"
echo "=== $(ts) todo-morning done: ${title} ==="
