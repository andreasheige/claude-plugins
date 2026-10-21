#!/bin/bash
# PreToolUse guardrail hook — defense-in-depth behind permissions.deny.
# Reads a PreToolUse JSON payload on stdin and denies dangerous Bash commands
# or reads of credential/config files. Fails OPEN (allow) on any internal
# error or missing dependency — this hook must never be able to softlock a
# session; it can only add friction, not become a single point of failure.
set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo '{"systemMessage":"guardrail.sh: jq not found, guardrail hook is disabled (failing open). Install jq to restore it."}'
  exit 0
fi

input="$(cat)"
tool_name="$(echo "$input" | jq -r '.tool_name // empty' 2>/dev/null)"

deny() {
  jq -n --arg reason "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason},systemMessage:$reason}'
  exit 0
}

case "$tool_name" in
  Bash)
    cmd="$(echo "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)"
    [ -z "$cmd" ] && exit 0

    # --- destructive filesystem ---
    if echo "$cmd" | grep -qE '(^|[;&|]\s*)(sudo)\b'; then
      deny "sudo is blocked on this machine. Ask the user to run the privileged command manually."
    fi
    if echo "$cmd" | grep -qE '\brm\s+(-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*|-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*)\b'; then
      deny "rm -rf is blocked. Use 'trash <path>' (recoverable) instead, or ask the user to confirm and run it themselves."
    fi
    if echo "$cmd" | grep -qE '\bmkfs(\.|\s)'; then
      deny "mkfs is blocked (irreversible disk formatting)."
    fi
    if echo "$cmd" | grep -qE '\bdd\s+.*\b(if|of)='; then
      deny "dd is blocked (irreversible raw disk/file overwrite)."
    fi

    # --- git guardrails ---
    # Policy: never merge, always rebase (see the devsecops-workflow plugin's
    # git-workflow skill). git merge is blocked outright, ff-or-not — but
    # --abort/--continue/--quit are cleanup/recovery flags, not new merges,
    # and must stay allowed (e.g. to abort a merge started some other way).
    if echo "$cmd" | grep -qE '\bgit\s+merge\b' && \
       ! echo "$cmd" | grep -qE '\bgit\s+merge\s+--(abort|continue|quit)\b'; then
      deny "git merge is blocked (rebase-only policy). Use 'git fetch && git rebase origin/main' instead."
    fi
    # Plain --force/-f is always blocked. --force-with-lease is the expected
    # way to update a remote feature branch after a rebase, so it's allowed —
    # except when the target is main/master, which stays hard-denied in any
    # form. (Only fires when the branch is explicitly named, same convention
    # as the direct-push-to-main rule below.)
    if echo "$cmd" | grep -qE '\bgit\s+push\b' && \
       echo "$cmd" | grep -qE '(--force\b|-f\b)' && \
       ! echo "$cmd" | grep -qE '\-\-force-with-lease\b'; then
      deny "Plain force-push (--force/-f) is blocked. Use --force-with-lease on a feature branch instead."
    fi
    if echo "$cmd" | grep -qE '\bgit\s+push\b' && \
       echo "$cmd" | grep -qE '\-\-force-with-lease\b' && \
       echo "$cmd" | grep -qE '\b(origin\s+)?(main|master)\b'; then
      deny "Force-pushing main/master is blocked, even with --force-with-lease."
    fi
    if echo "$cmd" | grep -qE '\bgit\s+reset\s+.*--hard\b'; then
      deny "git reset --hard is blocked (destroys uncommitted work). Use 'git stash' or a soft reset."
    fi
    if echo "$cmd" | grep -qE '\bgit\s+push\b' && \
       echo "$cmd" | grep -qE '\b(origin\s+)?(main|master)\b' && \
       ! echo "$cmd" | grep -qE '\-\-force|\-f\b'; then
      # Only fires when the branch is explicitly named main/master — a bare
      # `git push` of the current tracking branch is intentionally NOT caught.
      deny "Direct push to main/master is blocked. Create a feature branch and open a PR."
    fi

    # --- infrastructure ---
    if echo "$cmd" | grep -qE '\bterraform\s+(apply|destroy)\b'; then
      deny "terraform apply/destroy execution is blocked. Run 'terraform plan' and hand the exact apply/destroy command to the user to run manually."
    fi
    if echo "$cmd" | grep -qE '\btofu\s+(apply|destroy)\b'; then
      deny "tofu apply/destroy execution is blocked. Run 'tofu plan' and hand the exact apply/destroy command to the user to run manually."
    fi
    # az CLI destructive commands. Enumerated by literal resource-type path
    # (not a generic '.* delete' catch-all) to avoid false-positive blocks on
    # commands like 'az group show --name delete-test-rg' — same narrow,
    # explicit-verb philosophy as the terraform/tofu rule above.
    if echo "$cmd" | grep -qE '\baz\s+(group|resource|vm|disk|webapp|functionapp|aks|acr|storage\s+account|sql\s+(server|db)|network\s+(vnet|nsg|public-ip)|deployment\s+(group|sub))\s+delete\b'; then
      deny "az delete on this resource type is blocked. Run the read-only equivalent (e.g. 'az ... show') and hand the exact delete command to the user to run manually."
    fi
    if echo "$cmd" | grep -qE '\baz\s+keyvault\s+(delete|purge)\b'; then
      deny "az keyvault delete/purge is blocked (purge is irreversible even past soft-delete). Hand the exact command to the user to run manually."
    fi

    # --- credential access ---
    # permissions.deny and the Read branch below are both scoped to the Read
    # tool, so a Bash command reaches the same files completely unchecked.
    # These patterns close that path. They are string matches on the command,
    # so deliberate obfuscation defeats them — this is friction and an
    # injection-resistance layer, not a containment boundary.
    if echo "$cmd" | grep -qE '\.(ssh|aws)/|(~|\$HOME)/\.(ssh|aws)\b'; then
      deny "Bash access to ~/.ssh or ~/.aws is blocked (credential stores). If you genuinely need a value from them, ask the user to retrieve it."
    fi
    if echo "$cmd" | grep -qE '\.git-credentials|\.netrc|\.docker/config\.json|Library/Keychains'; then
      deny "Bash access to a credential file (.git-credentials / .netrc / docker config / Keychains) is blocked."
    fi
    if echo "$cmd" | grep -qE '\bsecurity\s+(find-(generic|internet)-password|dump-keychain)\b'; then
      deny "Reading the macOS keychain via the 'security' CLI is blocked."
    fi
    # .env is matched only behind a reader verb, since '.env' appears legitimately
    # in commands all the time (gitignore edits, --env-file flags). Example and
    # template variants are not secrets and stay allowed.
    if echo "$cmd" | grep -qE '\b(cat|less|more|head|tail|strings|xxd|od|base64|nl|grep|rg|awk|sed)\b[^|;]*(^|[^[:alnum:]_-])\.env(\.|\b)' && \
       ! echo "$cmd" | grep -qE '\.env\.(example|sample|template|dist)\b'; then
      deny "Reading .env files from Bash is blocked. Ask the user for the specific value you need."
    fi
    ;;

  Read)
    fp="$(echo "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
    [ -z "$fp" ] && exit 0
    case "$fp" in
      "$HOME"/.ssh/*|"$HOME"/.aws/*|"$HOME"/.git-credentials| \
      "$HOME"/.docker/config.json|"$HOME"/.netrc| \
      "$HOME"/.bashrc|"$HOME"/.zshrc|"$HOME"/.zprofile| \
      "$HOME"/Library/Keychains/*)
        deny "Credential/config file reads are blocked: $fp"
        ;;
      *.env|*.env.*)
        deny "Reading .env files is blocked: $fp"
        ;;
    esac
    ;;
esac

exit 0
