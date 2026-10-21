#!/bin/bash
# PreToolUse hook — block credentials being written into shell rc files.
#
# Policy: real secret values live in ~/.zshrc.local (chmod 600, gitignored),
# which .zshrc sources at the end. Nothing secret belongs in .zshrc itself,
# .zprofile, .zshenv, .bashrc or .bash_profile.
#
# Wire-compatible with BOTH Claude Code and Codex CLI: the two agents use an
# identical PreToolUse payload (.tool_name / .tool_input) and an identical
# output envelope (hookSpecificOutput.permissionDecision = deny). One script,
# both agents. Copilot CLI runs it only as a postToolUse --audit (it can detect
# a misplaced secret after the write, not block it), plus the advisory
# instruction in ~/.agent-global/AGENTS.md.
#
# Matches on the CONTENT of tool_input rather than on tool_name, so it works
# regardless of whether the agent calls its editor Write/Edit or apply_patch,
# and it also catches the `echo ... >> ~/.zshrc` route through Bash.
#
# Fails OPEN (allow) on any internal error or missing dependency — same
# convention as guardrail.sh. This can add friction; it must never be able to
# softlock a session. It is a placement guard, not a containment boundary:
# string matching, so deliberate obfuscation defeats it.
#
# Second mode:  secret-placement.sh --audit   scans the rc files on disk and
# reports misplaced assignments (names and value LENGTHS only, never values).
set -uo pipefail

# Variable names that indicate a credential. Applied to the extracted NAME, so
# `PAT` is anchored — otherwise it would match PATH and block `export PATH=`.
SECRET_NAME_RE='(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|CONNECTIONSTRING|CONNECTION_STRING|BEARER|PRIVATE|_PW$|^PW_|_PAT$|^PAT$|_SAS$|^SAS$)'

# Names that contain a keyword above but are not secrets. KEYTIMEOUT/KEYMAP are
# real zsh variables; the PATH family must never be caught.
SAFE_NAME_RE='^(PATH|MANPATH|INFOPATH|CLASSPATH|PYTHONPATH|GOPATH|NODE_PATH|LD_LIBRARY_PATH|DYLD_LIBRARY_PATH|PKG_CONFIG_PATH|KEYTIMEOUT|KEYMAP|KEYBOARD|KEYBOARD_HACK|SECRETS_DIR|TOKENIZERS_PARALLELISM)$'

# Values that are obviously not real secrets.
PLACEHOLDER_RE='^([<$"'"'"']|your[-_]|my[-_]|xxx|x{4,}|\.\.\.|changeme|change[-_]me|example|placeholder|todo|tbd|fixme|replace[-_]|insert[-_]|sk-or-v1-\.\.\.|<[^>]*>|\{\{)'

# Shell rc files where a secret is a policy violation. NOTE: *.local variants
# are the sanctioned destination and are stripped before this is applied.
RC_FILE_RE='(^|/|~)\.(zshrc|zprofile|zshenv|zlogin|bashrc|bash_profile|profile)([^.[:alnum:]_-]|$)'

# ── shared detection ─────────────────────────────────────────────────────────
# Reads text on stdin, prints "VARNAME<TAB>valuelength" for each offending
# assignment. An assignment offends when the name looks like a credential AND
# the value is non-empty, not a placeholder, and at least 8 chars long.
find_secret_assignments() {
  # grep -n first so real line numbers survive, then a CHEAP pre-filter: only
  # lines that assign to a credential-looking name reach the per-line loop
  # below. Without this, a 400-line .zshrc costs ~2s of process spawning —
  # too close to the 5s hook timeout. With it, ~10ms.
  grep -n '.' 2>/dev/null \
  | grep -iE "[A-Za-z_][A-Za-z0-9_]*(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|CONNECTIONSTRING|CONNECTION_STRING|BEARER|PRIVATE|_PW|_PAT|PAT|_SAS|SAS)[A-Za-z0-9_]*=" 2>/dev/null \
  | while IFS= read -r line; do
      # line is "N:<text>" from grep -n
      local lineno text
      lineno="${line%%:*}"
      text="${line#*:}"

      # A commented-out line is not active config. Skip it entirely — this is
      # what keeps the disabled ANTHROPIC_* block in .zshrc from tripping.
      printf '%s' "$text" | grep -qE '^[[:space:]]*#' && continue

      # Pull out every NAME=value candidate ANYWHERE on the line, not just at
      # line start, so `echo 'export FOO_KEY=v' >> ~/.zshrc` is caught too.
      printf '%s' "$text" \
        | grep -oE "[A-Za-z_][A-Za-z0-9_]*=[^;&|>[:space:]]*" 2>/dev/null \
        | while IFS= read -r pair; do
            local name value
            name="${pair%%=*}"
            value="${pair#*=}"
            printf '%s' "$name" | grep -qiE "$SAFE_NAME_RE" && continue
            printf '%s' "$name" | grep -qiE "$SECRET_NAME_RE" || continue
            # Strip surrounding quote characters. Done unconditionally rather
            # than as a matched pair, because the candidate above can be cut
            # mid-value (e.g. a connection string containing ';'), leaving an
            # unbalanced quote that would otherwise read as a placeholder.
            value="$(printf '%s' "$value" | sed -E 's/^["'"'"'`]+//; s/["'"'"'`]+$//')"
            [ -z "$value" ] && continue
            [ "${#value}" -lt 8 ] && continue
            printf '%s' "$value" | grep -qiE "$PLACEHOLDER_RE" && continue
            printf '%s\t%s\t%s\n' "$lineno" "$name" "${#value}"
          done
    done
}

# ── scan mode ────────────────────────────────────────────────────────────────
# Reads text on stdin, prints "line<TAB>NAME<TAB>valuelength" per hit, exits 1
# if any were found. This is the single source of truth the global pre-commit
# hook reuses, so the patterns live in exactly one place.
if [ "${1:-}" = "--scan" ]; then
  hits="$(find_secret_assignments)"
  [ -z "$hits" ] && exit 0
  printf '%s\n' "$hits"
  exit 1
fi

# ── audit mode ───────────────────────────────────────────────────────────────
if [ "${1:-}" = "--audit" ]; then
  status=0
  for f in "$HOME/.zshrc" "$HOME/.zprofile" "$HOME/.zshenv" "$HOME/.zlogin" \
           "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
    [ -f "$f" ] || continue
    hits="$(find_secret_assignments < "$f")"
    [ -z "$hits" ] && continue
    status=1
    echo "MISPLACED  $f"
    printf '%s\n' "$hits" | while IFS=$'\t' read -r ln name len; do
      printf '    line %-5s %-34s [value redacted, %s chars]\n' "$ln" "$name" "$len"
    done
  done
  if [ "$status" -eq 0 ]; then
    echo "clean — no credential assignments found in any shell rc file"
  else
    echo
    echo "Move each of the above into ~/.zshrc.local (chmod 600), which .zshrc"
    echo "sources at the end. Values were not printed."
  fi
  exit "$status"
fi

# ── hook mode ────────────────────────────────────────────────────────────────
command -v jq >/dev/null 2>&1 || {
  echo '{"systemMessage":"secret-placement.sh: jq not found, secret-placement hook is disabled (failing open)."}'
  exit 0
}

input="$(cat)"
[ -z "$input" ] && exit 0

# Strip the sanctioned *.local destinations before testing for rc filenames, so
# a write to .zshrc.local is never mistaken for a write to .zshrc.
strip_local() { sed -E 's/\.(zshrc|zprofile|zshenv|zlogin|bashrc|bash_profile|profile)\.local//g'; }

# Two shapes of tool_input, distinguished by FIELD PRESENCE rather than by tool
# name, so this stays agnostic to what each agent calls its editor tool.
target="$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)"

if [ -n "$target" ]; then
  # File-targeted write (Write / Edit / MultiEdit / …). The PATH decides whether
  # the file is in scope and the CONTENT fields decide whether it holds a
  # secret — judged separately, so content that merely mentions another rc file
  # cannot drag an out-of-scope target into scope.
  printf '%s' "$target" | strip_local | grep -qE "$RC_FILE_RE" || exit 0
  payload="$(printf '%s' "$input" \
    | jq -r '[.tool_input | del(.file_path) | del(.path) | .. | strings] | join("\n")' 2>/dev/null)" || exit 0
else
  # Command-style input (Bash / shell / exec_command). Path and content live in
  # one opaque string, so both tests run against the whole command.
  #
  # KNOWN LIMITATION: a single compound command that touches BOTH an in-scope
  # rc file and a sanctioned .local file is denied, because the rc mention and
  # the secret assignment cannot be attributed to separate statements. Splitting
  # on newlines would fix that but would break the far more important
  # `cat > ~/.zshrc <<EOF ... EOF` heredoc case, where the path and the secret
  # are deliberately on different lines. Denying the rare compound command is
  # the safer trade; run the two writes as separate commands.
  payload="$(printf '%s' "$input" | jq -r '[.tool_input | .. | strings] | join("\n")' 2>/dev/null)" || exit 0
  [ -z "$payload" ] && exit 0
  printf '%s' "$payload" | strip_local | grep -qE "$RC_FILE_RE" || exit 0
fi

[ -z "$payload" ] && exit 0

hits="$(printf '%s' "$payload" | find_secret_assignments)"
[ -z "$hits" ] && exit 0

names="$(printf '%s' "$hits" | cut -f2 | sort -u | tr '\n' ' ')"
reason="Blocked: this writes a credential (${names% }) into a shell rc file. Secrets do not belong in .zshrc/.zprofile/.zshenv/.bashrc — those are readable config, often version-controlled.

Put the real value in ~/.zshrc.local instead (chmod 600, gitignored); .zshrc already sources it at the end via:
  [ -f ~/.zshrc.local ] && source ~/.zshrc.local

If this is a placeholder rather than a real secret, leave the value empty (FOO_KEY=\"\") and it will pass."

jq -n --arg reason "$reason" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason},systemMessage:$reason}'
exit 0
