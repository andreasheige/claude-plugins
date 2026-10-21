#!/bin/bash
# Exercises the plan-gate Stop hook against throwaway transcripts and plans.
# Needs node and jq. Usage: bash plan-gate/tests/run.sh
set -uo pipefail
HOOK="$(cd "$(dirname "$0")/../scripts" && pwd)/plan-gate.mjs"
T="$(mktemp -d)"
pass=0; fail=0

check() {
  if [ "$2" = "$3" ]; then pass=$((pass + 1)); printf '  ok    %s\n' "$1"
  else fail=$((fail + 1)); printf '  FAIL  %s (expected %s, got %s)\n' "$1" "$2" "$3"; fi
}

# transcript <file> <user text>... : one user entry per argument
transcript() {
  local f="$1"; shift; : > "$f"; local i=0
  for text in "$@"; do
    i=$((i + 1))
    jq -nc --arg t "$text" --arg u "u$i" --arg c "$T" \
      '{type:"user",uuid:$u,cwd:$c,message:{role:"user",content:$t}}' >> "$f"
  done
}

# verdict <session> <transcript> : "block" or "allow"
verdict() {
  jq -nc --arg s "$1" --arg p "$2" '{session_id:$s,transcript_path:$p}' \
    | node "$HOOK" | decide
}

# Reads hook stdout: "block" on decision:block, otherwise (incl. no output) "allow".
decide() {
  local out; out="$(cat)"
  if [ -n "$out" ] && [ "$(printf '%s' "$out" | jq -r '.decision // empty' 2>/dev/null)" = "block" ]; then
    echo block
  else
    echo allow
  fi
}

gate() { printf '<command-name>/plan-gate</command-name>\n<command-args>%s</command-args>' "$1"; }
sid() { echo "test-$$-$1"; }

printf -- '- [x] done\n- [ ] next\n' > "$T/open.md"
printf -- '- [x] done\n- [x] also done\n' > "$T/done.md"
printf -- '- [ ] next\nBLOCKED: needs a decision\n' > "$T/blocked.md"
printf -- '- [~] @agent in progress\n' > "$T/progress.md"

transcript "$T/a.jsonl" "$(gate open.md)"
check "open item blocks the stop" block "$(verdict "$(sid a)" "$T/a.jsonl")"

transcript "$T/b.jsonl" "$(gate done.md)"
check "all ticked allows the stop" allow "$(verdict "$(sid b)" "$T/b.jsonl")"

transcript "$T/c.jsonl" "$(gate blocked.md)"
check "BLOCKED: line allows the stop" allow "$(verdict "$(sid c)" "$T/c.jsonl")"

transcript "$T/d.jsonl" "$(gate progress.md)"
check "[~] in-progress item still blocks" block "$(verdict "$(sid d)" "$T/d.jsonl")"

transcript "$T/e.jsonl" "$(gate open.md)" "$(gate off)"
check "/plan-gate off disarms it" allow "$(verdict "$(sid e)" "$T/e.jsonl")"

transcript "$T/f.jsonl" "just chatting"
check "no gate command: inert" allow "$(verdict "$(sid f)" "$T/f.jsonl")"

transcript "$T/g.jsonl" "$(gate open.md)"
for _ in 1 2 3 4 5 6 7 8 9 10; do verdict "$(sid g)" "$T/g.jsonl" >/dev/null; done
check "11th continuation in one prompt lets it stop" allow "$(verdict "$(sid g)" "$T/g.jsonl")"

check "garbage stdin fails open" allow "$(echo 'not json' | node "$HOOK" | decide)"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
