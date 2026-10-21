#!/bin/bash
# Feeds every case in cases.jsonl to its hook and checks the decision.
# Also checks the SessionStart canary both ways (guardrail present / missing).
# Needs jq. Usage: bash guardrails/tests/run.sh
set -uo pipefail
cd "$(dirname "$0")"
S=../scripts
pass=0; fail=0

decision() {
  # A hook "denies" via hookSpecificOutput.permissionDecision, a top-level
  # decision:"block", or exit code 2 (stderr = reason). Anything else allows.
  local out rc
  out="$(bash "$S/$1" 2>/dev/null)"; rc=$?
  if [ "$rc" -eq 2 ]; then echo deny; return; fi
  if [ -z "$out" ]; then echo allow; return; fi
  printf '%s' "$out" | jq -r '
    (.hookSpecificOutput.permissionDecision // (if .decision == "block" then "deny" else empty end)) // "allow"
  ' 2>/dev/null || echo allow
}

check() {
  if [ "$2" = "$3" ]; then pass=$((pass + 1)); printf '  ok    %s\n' "$1"
  else fail=$((fail + 1)); printf '  FAIL  %s (expected %s, got %s)\n' "$1" "$2" "$3"; fi
}

while IFS= read -r line; do
  [ -z "$line" ] && continue
  name="$(jq -r .name <<<"$line")"; expect="$(jq -r .expect <<<"$line")"; hook="$(jq -r .hook <<<"$line")"
  payload="$(jq -c --arg h "$HOME" '.payload | walk(if type == "string" then sub("^~"; $h) else . end)' <<<"$line")"
  got="$(printf '%s' "$payload" | decision "$hook")"
  check "$hook: $name" "$expect" "$got"
done < cases.jsonl

msg="$(GUARDRAIL_CHECK_SETTINGS=/nonexistent bash "$S/guardrail-check.sh")"
check "canary: working guardrail is silent" "" "$msg"
msg="$(GUARDRAIL_PATH=/nonexistent GUARDRAIL_CHECK_SETTINGS=/nonexistent bash "$S/guardrail-check.sh" | jq -r '.systemMessage' | cut -c1-14)"
check "canary: missing guardrail warns" "GUARDRAIL DOWN" "$msg"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
