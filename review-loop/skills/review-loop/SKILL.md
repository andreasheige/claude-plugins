---
name: review-loop
description: Run the review-loop CLI on a diff — `scan` for secrets, hidden Unicode and new dependencies, or `worker` for a read-only model finder/verifier pass. Use when asked to scan staged changes or a commit range before committing or pushing, or to run an isolated model review of a diff.
---

# review-loop

The CLI lives next to this skill: `${CLAUDE_PLUGIN_ROOT}/bin/review-loop`. Python 3.9+, no dependencies.

## Scan a diff (deterministic, no model)

```
review-loop scan --staged                # what is about to be committed
review-loop scan --range origin/main..HEAD
review-loop scan --staged --format text  # one line per finding, for git hooks
```

Checks: D1 secrets (gitleaks), D2 hidden Unicode (bidi controls, Cf characters, variation selectors), D3 new or
changed versions in `package-lock.json` / `uv.lock` (malicious, nonexistent, very young).

Exit codes: `0` pass, `1` block, `2` needs a human, `3` tool error. Treat 3 as a block: a missing or tampered
scanner never counts as a pass. Report the findings as given; never describe a 0 as "secure".

## Model review of a diff

```
review-loop worker --harness claude|codex --role find|verify --input prompt.md --repo . --rev HEAD
```

The worker runs in a scratch `git worktree` of `--repo` at `--rev`, with agent config (`.claude/`, `.codex/`,
`.mcp.json`, `CLAUDE.md`, `AGENTS.md`, Copilot instructions) and `.env*` removed and a minimal environment.
Claude runs `--restricted --safe-mode` with Read/Grep/Glob only; Codex runs a read-only permission profile (no
home directory, no network) under a scratch `CODEX_HOME`. Output is validated against `contract/`; malformed
output is retried once, then exit 3.

## Setup the scan needs

Scanners are pinned by absolute path and sha256 in `~/.config/review-loop/tools.lock` (TSV:
`tool<TAB>version<TAB>realpath<TAB>sha256`), never taken from `PATH`. If the lock is missing, say so and show the
user the README's setup section; do not create or edit the lock yourself.
