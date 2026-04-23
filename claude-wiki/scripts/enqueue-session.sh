#!/usr/bin/env bash
# SessionEnd hook: append a pointer for the ending session to the ingest queue.
#
# Input : JSON on stdin from the Claude Code hook runtime.
#         Fields of interest: session_id, cwd, transcript_path (if provided).
# Effect: appends one line to $HOME/.claude/wiki/state/queue.jsonl.
# Never fails the hook runner — any error is logged and exit 0 so the
# session can close cleanly.

set -u

WIKI_STATE_DIR="${HOME}/.claude/wiki/state"
QUEUE="${WIKI_STATE_DIR}/queue.jsonl"
ERR_LOG="${WIKI_STATE_DIR}/hook-errors.log"

mkdir -p "${WIKI_STATE_DIR}"

INPUT="$(cat)"

# Extract fields without requiring jq: try jq first, fall back to python.
extract() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r --arg k "$1" '.[$k] // empty'
  else
    printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    v = d.get('$1', '')
    print(v if v is not None else '')
except Exception:
    pass
"
  fi
}

SESSION_ID="$(extract session_id)"
CWD="$(extract cwd)"
TRANSCRIPT_PATH="$(extract transcript_path)"

if [[ -z "${SESSION_ID}" ]]; then
  printf '%s  missing session_id in hook input\n' "$(date -u +%FT%TZ)" >> "${ERR_LOG}"
  exit 0
fi

# Derive the canonical transcript path if the runtime did not pass one:
# $HOME/.claude/projects/<encoded-cwd>/<session>.jsonl
if [[ -z "${TRANSCRIPT_PATH}" && -n "${CWD}" ]]; then
  ENCODED="$(printf '%s' "${CWD}" | sed 's|/|-|g')"
  TRANSCRIPT_PATH="${HOME}/.claude/projects/${ENCODED}/${SESSION_ID}.jsonl"
fi

TS="$(date -u +%FT%TZ)"

# Emit a single JSON line. Use python to ensure proper escaping.
python3 - <<PY >> "${QUEUE}"
import json
print(json.dumps({
    "session_id": "${SESSION_ID}",
    "cwd": "${CWD}",
    "transcript_path": "${TRANSCRIPT_PATH}",
    "enqueued_at": "${TS}",
    "processed": False,
}, ensure_ascii=False))
PY

exit 0
