# Shared agent memory

Durable facts that every coding agent (Claude Code, Codex CLI, Copilot CLI) reads and writes.
One fact per file; this index gets one line per fact and is the only file read at session
start. Open a fact file only when its line matches the task — keep this index small
(a few KB), because it is read every session.

Point each agent at this folder: a section in `~/.claude/CLAUDE.md`, an `AGENTS.md` for
Codex, `COPILOT_CUSTOM_INSTRUCTIONS_DIRS` for Copilot CLI.

## Facts

- [Terminal is Warp](terminal-is-warp.md) — never hard-code Terminal.app; read `__CFBundleIdentifier` and pass it to `open -b`.
