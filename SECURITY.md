# Security policy

## Reporting a vulnerability

Please **don't open a public issue** for a security problem. Report it privately through
GitHub: **Security → Report a vulnerability** on this repository
([direct link](https://github.com/andreasheige/claude-plugins/security/advisories/new)).

Include what you found, how to reproduce it, and what an attacker could do with it.
I'll acknowledge the report within a week and keep you updated until it's resolved.

## Scope

In scope: anything in this repository — the plugins' hooks, scripts, commands, skills and
agents, and the files under `starter/`. Examples:

- a way to make `guardrails` allow a command or file read it is meant to deny, other than
  the known limitation below;
- a hook that executes or leaks content it shouldn't;
- a starter file that would weaken a user's setup when copied as documented.

Out of scope: Claude Code itself (report to Anthropic), third-party plugins, and the known
limitation below.

## Known limitation

The guardrail hooks match strings in the command or path. They stop common accidents; they
are **not a containment boundary**, and an obfuscated command can get past them. Reports
that only restate this are out of scope — but a *simple, realistic* command that slips
through is worth reporting.

## Supported versions

Only the latest commit on `main` is supported.
