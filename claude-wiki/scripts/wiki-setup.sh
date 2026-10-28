#!/usr/bin/env bash
# Idempotent per-host setup for claude-wiki.
#
#   wiki-setup.sh [--hook] [--weekly] [--morning] [--vault-visibility PRIVATE]
#
#   (always)   ~/.claude/wiki/{state,config,hooks}, merge.regen driver in the vault
#   --hook     symlink ~/.claude/wiki/hooks/auto-ingest-push.sh → this plugin's copy,
#              register it as a SessionEnd hook and enable the plugin in
#              ~/.claude/settings.json (backup written next to it)
#   --weekly   install launchd job com.tatoflam.wiki-weekly (Sunday 08:00 local time)
#   --morning  install launchd job com.tatoflam.todo-morning (daily 08:00): today's
#              todo digest via notify-cli (profile "todo" in ~/.config/notify-cli/config.yaml)
#   --vault-visibility V
#              record the vault's GitHub visibility for hosts without gh
#              (verify it with `gh repo view` on a host that has gh first)
#
# Host-specific, never committed: ~/.claude/wiki/config/{capture.conf,push.conf,weekly.conf}

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "${HERE}")"
MARKET_ROOT="$(dirname "${PLUGIN_ROOT}")"
WIKI="${HOME}/.claude/wiki"
VAULT="${WIKI_VAULT:-${HOME}/repo/github/tatoflam/v}"
SETTINGS="${HOME}/.claude/settings.json"
PLIST="${HOME}/Library/LaunchAgents/com.tatoflam.wiki-weekly.plist"
MORNING_PLIST="${HOME}/Library/LaunchAgents/com.tatoflam.todo-morning.plist"

HOOK=0; WEEKLY=0; MORNING=0; VIS=""
while (( $# )); do
  case "$1" in
    --hook) HOOK=1 ;;
    --weekly) WEEKLY=1 ;;
    --morning) MORNING=1 ;;
    --vault-visibility) VIS="$2"; shift ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done

mkdir -p "${WIKI}/state" "${WIKI}/config" "${WIKI}/hooks"
echo "ok   ${WIKI}/{state,config,hooks}"

if [[ -d "${VAULT}/.git" ]]; then
  git -C "${VAULT}" config merge.regen.driver true
  git -C "${VAULT}" config merge.regen.name "regenerated file: keep current"
  echo "ok   merge.regen driver in ${VAULT}"
else
  echo "WARN vault not cloned at ${VAULT}"
fi

[[ -f "${WIKI}/config/capture.conf" ]] && echo "ok   capture.conf present" \
  || echo "WARN ${WIKI}/config/capture.conf missing — every session will be skipped (fail closed). Copy it from another host."

if [[ -n "${VIS}" ]]; then
  printf 'vault_visibility=%s\n' "${VIS}" > "${WIKI}/config/push.conf"
  echo "ok   push.conf vault_visibility=${VIS}"
fi

if (( HOOK )); then
  target="${WIKI}/hooks/auto-ingest-push.sh"
  if [[ -e "${target}" && ! -L "${target}" ]]; then
    mv "${target}" "${target}.bak.$(date +%Y%m%d%H%M%S)"
  fi
  ln -sfn "${HERE}/auto-ingest-push.sh" "${target}"
  echo "ok   ${target} -> ${HERE}/auto-ingest-push.sh"

  [[ -f "${SETTINGS}" ]] && cp "${SETTINGS}" "${SETTINGS}.bak.wiki-setup.$(date +%Y%m%d%H%M%S)"
  python3 - "${SETTINGS}" "${target}" "${MARKET_ROOT}" <<'PY'
import json, os, sys
path, hook, market = sys.argv[1:4]
s = json.load(open(path)) if os.path.exists(path) else {}
hooks = s.setdefault("hooks", {}).setdefault("SessionEnd", [])
cmds = [h.get("command") for g in hooks for h in g.get("hooks", [])]
if hook not in cmds:
    hooks.append({"matcher": "", "hooks": [{"type": "command", "command": hook}]})
s.setdefault("extraKnownMarketplaces", {})["plugins-tatoflam"] = {"source": {"source": "directory", "path": market}}
s.setdefault("enabledPlugins", {})["claude-wiki@plugins-tatoflam"] = True
json.dump(s, open(path, "w"), ensure_ascii=False, indent=2)
open(path, "a").write("\n")
PY
  echo "ok   settings.json: SessionEnd hook + plugins-tatoflam marketplace + claude-wiki enabled"
fi

if (( WEEKLY )); then
  mkdir -p "$(dirname "${PLIST}")"
  cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.tatoflam.wiki-weekly</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>${HERE}/wiki-weekly.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
  <key>EnvironmentVariables</key>
  <dict><key>HOME</key><string>${HOME}</string><key>LANG</key><string>ja_JP.UTF-8</string></dict>
  <key>StandardOutPath</key><string>${WIKI}/state/weekly.launchd.log</string>
  <key>StandardErrorPath</key><string>${WIKI}/state/weekly.launchd.log</string>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/com.tatoflam.wiki-weekly" 2>/dev/null || true
  for i in 1 2 3 4 5; do
    launchctl bootstrap "gui/$(id -u)" "${PLIST}" 2>/dev/null && break
    sleep 3   # "Bootstrap failed: 5" while the old job is still being torn down
  done
  launchctl print "gui/$(id -u)/com.tatoflam.wiki-weekly" >/dev/null && echo "ok   launchd com.tatoflam.wiki-weekly (Sun 08:00 $(date +%Z))"
fi

if (( MORNING )); then
  mkdir -p "$(dirname "${MORNING_PLIST}")"
  cat > "${MORNING_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.tatoflam.todo-morning</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>${HERE}/todo-morning.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
  <key>EnvironmentVariables</key>
  <dict><key>HOME</key><string>${HOME}</string><key>LANG</key><string>ja_JP.UTF-8</string></dict>
  <key>StandardOutPath</key><string>${WIKI}/state/morning.launchd.log</string>
  <key>StandardErrorPath</key><string>${WIKI}/state/morning.launchd.log</string>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/com.tatoflam.todo-morning" 2>/dev/null || true
  for i in 1 2 3 4 5; do
    launchctl bootstrap "gui/$(id -u)" "${MORNING_PLIST}" 2>/dev/null && break
    sleep 3
  done
  launchctl print "gui/$(id -u)/com.tatoflam.todo-morning" >/dev/null && echo "ok   launchd com.tatoflam.todo-morning (daily 08:00 $(date +%Z))"
  grep -q '^  todo:' "${HOME}/.config/notify-cli/config.yaml" 2>/dev/null \
    || echo "WARN notify-cli profile 'todo' missing in ~/.config/notify-cli/config.yaml"
fi
