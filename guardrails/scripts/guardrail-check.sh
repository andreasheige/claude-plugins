#!/bin/bash
# SessionStart anchor check.
#
# guardrail.sh deliberately fails OPEN so it can never softlock a session —
# that design stays. The cost of it is that a missing jq, a deleted file, or a
# broken pattern silently removes the guardrail with no signal at all. This
# check closes that gap from the outside: it exercises the guardrail against a
# canary payload at session start and reports loudly if it does not deny.
#
# It never blocks a session either. The worst it does is print a warning.
set -uo pipefail

GUARDRAIL="${GUARDRAIL_PATH:-$(dirname "$0")/guardrail.sh}"

fail() {
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg m "$1" '{systemMessage:$m}'
  else
    printf '{"systemMessage":"%s"}\n' "$1"
  fi
  exit 0
}

[ -r "$GUARDRAIL" ] || fail "GUARDRAIL DOWN: $GUARDRAIL is missing or unreadable. Bash/Read guardrails are NOT active this session."

command -v jq >/dev/null 2>&1 || fail "GUARDRAIL DOWN: jq is not installed, so guardrail.sh fails open and every Bash/Read guardrail is inactive. Run 'brew install jq' to restore it."

# Functional canary — a payload the guardrail must deny. This asserts the hook
# actually works, not merely that the file exists. No file is read: only the
# path string is passed to the hook.
canary="$(jq -n --arg p "$HOME/.ssh/id_rsa" '{tool_name:"Read",tool_input:{file_path:$p}}')"
verdict="$(printf '%s' "$canary" | bash "$GUARDRAIL" 2>/dev/null | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null)"

[ "$verdict" = "deny" ] || fail "GUARDRAIL DOWN: guardrail.sh did not deny a known-bad canary (got '${verdict:-no verdict}'). Guardrails may be broken — inspect hooks/guardrail.sh before trusting this session."

# Config drift — installers (Herdr, plugin setups) rewrite settings.json without
# asking. Warn about the changes that have actually happened before; never fix
# anything here. GUARDRAIL_CHECK_SETTINGS lets a test point at a scratch copy.
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SETTINGS="${GUARDRAIL_CHECK_SETTINGS:-$CFG/settings.json}"
LOCAL_SETTINGS="$(dirname "$SETTINGS")/settings.local.json"
drift=()

if [ -r "$SETTINGS" ]; then

  # First quoted script path in each hook command, e.g. bash "/x/y.sh" or node '/x/y.mjs'.
  while IFS= read -r script; do
    script="${script/#\$HOME/$HOME}"
    [ -n "$script" ] && [ ! -e "$script" ] && drift+=("hook script missing: $script")
  done < <(jq -r '.hooks[]?[]?.hooks[]?.command // empty' "$SETTINGS" 2>/dev/null \
    | grep -oE "[\"'][^\"']+\.(sh|mjs|js)[\"']" | tr -d "\"'" | sort -u)
fi

if [ -r "$LOCAL_SETTINGS" ] && \
   [ "$(jq '.permissions.deny // [] | length' "$LOCAL_SETTINGS" 2>/dev/null)" != "0" ]; then
  drift+=("settings.local.json has deny rules again — they belong in settings.json")
fi

if [ "${#drift[@]}" -gt 0 ]; then
  fail "CONFIG DRIFT: $(printf '%s; ' "${drift[@]}")"
fi

exit 0
