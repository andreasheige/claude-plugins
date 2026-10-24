# Shared agent memory

Durable facts that every coding agent (Claude Code, Codex CLI, Copilot CLI) reads and writes.
One fact per file; this index gets one line per fact and is the only file read at session
start. Open a fact file only when its line matches the task — keep this index small
(a few KB), because it is read every session.

Point each agent at this folder: a section in `~/.claude/CLAUDE.md`, an `AGENTS.md` for
Codex, `COPILOT_CUSTOM_INSTRUCTIONS_DIRS` for Copilot CLI.

When a fact changes, edit its file in place; never write a second file that disagrees,
because the other agents can't tell which one is current. Rewrite the fact, set
`metadata.date` to today, update its line below, and keep the old version as one line at
the end: `**Previously:** <old fact> (until YYYY-MM-DD)`. If it's unclear which version is
right, add `status: disputed` under `metadata` and ask the person; their own explicit
correction beats anything an agent inferred.

If this folder is pushed anywhere, keep client and employer names out unless they're on a
local allow-list the person approved (ask before adding a new one), and never write other
people's names or emails, credentials or account IDs.

## Facts

- [Terminal is Warp](terminal-is-warp.md) — never hard-code Terminal.app; read `__CFBundleIdentifier` and pass it to `open -b`.
