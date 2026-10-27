# claude-plugins

My Claude Code plugins and starter files: guardrails, a plan gate, a dual-loop DevSecOps workflow, .NET knowledge, and templates for the parts a plugin can't carry (CLAUDE.md, `permissions.deny`, git hooks, plans, rules, memory).

The tour of how it all fits together is in [the gist](https://gist.github.com/andreasheige/700405cb6d3489ffb8867bf6a4c51f6c). This repo is the part you can install.

## What's here

| Path | Kind | What it does |
|---|---|---|
| [`guardrails/`](guardrails) | plugin | PreToolUse guardrail (destructive commands, `git merge`/force-push/`reset --hard`, infra destroy, credential reads), secrets-in-rc-files guard, a SessionStart canary that warns when the guardrail is silently broken, and a frontmatter check for skills/commands/agents |
| [`plan-gate/`](plan-gate) | plugin | `/plan-gate <plan.md>` arms a Stop hook that keeps Claude working through a checklist until every item is ticked or a `BLOCKED:` line is written |
| [`devsecops-workflow/`](devsecops-workflow) | plugin | PRD → architecture → tickets; per ticket: prime → plan → implement → validate (5 levels, real execution mandatory) → fresh-context review → land. Adversarial tester, security and architecture reviewers. Also `dogma`, `cost-aware-orchestration`, `verify-before-done`, `git-workflow` |
| [`review-loop/`](review-loop) | plugin | Harness-neutral review CLI: `scan` a diff for secrets, hidden Unicode and new dependencies (pinned scanners, fails closed); `worker` runs a read-only model finder/verifier in a stripped scratch worktree |
| [`dotnet-kit/`](dotnet-kit) | plugin | Path-scoped .NET / C# skills; every code sample is compile-verified (`dotnet-kit/verify/verify.sh`) |
| [`starter/CLAUDE.md`](starter/CLAUDE.md) | template | Operating principles, security posture, session hygiene |
| [`starter/settings/`](starter/settings) | template | `permissions.deny` — core rules, and an optional Azure set |
| [`starter/git-hooks/`](starter/git-hooks) | template | Global git hooks: Conventional Commits, no merge commits, no credentials in dotfiles — for every commit, human or agent |
| [`starter/plans/`](starter/plans) | template | What a plan for `/plan-gate` looks like |
| [`starter/rules/`](starter/rules) | template | A path-scoped rule (loads only when matching files are touched) |
| [`starter/memory/`](starter/memory) | template | One-fact-per-file memory shared by Claude Code, Codex and Copilot |

## Prerequisites

- **macOS or Linux.** Tested on macOS; the Read deny rules for Keychains are macOS-only and harmless elsewhere.
- **`jq`** — required. Without it the guardrail fails *open*; the canary tells you at session start.
- **Node** (plan-gate), **Python 3 with PyYAML** (frontmatter check), **`trash`** (the guardrail suggests it instead of `rm -rf`).
- A recent Claude Code with plugin support.

## Start here

Each step is useful on its own; stop wherever it stops paying off.

1. **CLAUDE.md.** Copy what you agree with from [`starter/CLAUDE.md`](starter/CLAUDE.md) into `~/.claude/CLAUDE.md`. Everything in it is re-sent every turn — keep it short.
2. **Deny list.** Merge [`deny-core.json`](starter/settings/deny-core.json) (and [`deny-azure.json`](starter/settings/deny-azure.json) if you use `az`) into `permissions.deny` in `~/.claude/settings.json`. This is the first layer; the hooks are defence in depth behind it.
3. **Guardrails + plan gate.** Inside Claude Code:

   ```
   /plugin marketplace add andreasheige/claude-plugins
   /plugin install guardrails@personal-plugins
   /plugin install plan-gate@personal-plugins
   ```

   Restart the session. Verify: ask Claude to `cat ~/.ssh/id_rsa` — it must be denied. No warning at session start means the canary passed.
4. **Write a plan, gate it.** Copy [`starter/plans/example-plan.md`](starter/plans/example-plan.md), write your own steps (each with a `→ verify:`), then `/plan-gate plans/<name>.md`.
5. **Global git hooks** (optional): `git config --global core.hooksPath /path/to/starter/git-hooks`. Set `SECRET_SCANNER` to `guardrails/scripts/secret-placement.sh` for the dotfile credential check. Each hook also runs the repo's own hook of the same name.
6. **Workflow** (optional, for larger features): `/plugin install devsecops-workflow@personal-plugins`.
7. **Path-scoped rules and shared memory** (optional): see [`starter/rules/`](starter/rules) and [`starter/memory/`](starter/memory).

## What the guardrail is — and isn't

The hooks are string matches on the command or path. They stop the common accidents and make the agent pick a safer route, and every deny says what to do instead. They are **not a containment boundary**: an obfuscated command gets through, and some harmless commands are blocked (anything whose text contains `git merge`, even in a quoted string). For isolation, run the agent in a sandbox or container.

## Tests

```
bash guardrails/tests/run.sh    # deny/allow cases + canary, both ways
bash plan-gate/tests/run.sh     # block / allow / BLOCKED / off / loop guard / fail-open
```

## License

[MIT](LICENSE)
