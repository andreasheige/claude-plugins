---
name: cost-aware-orchestration
description: Use this skill whenever acting as the leader/orchestrator dispatching subagents, a swarm, or parallel Task-tool/Workflow work — pick each subagent's model based on the complexity of what it's being asked to do, not by default inheritance. Encodes real Anthropic pricing tiers so cost-consciousness is grounded in actual numbers, not vibes.
---

# Cost-Aware Orchestration

When you're the leader — planning work and dispatching subagents (Task tool, Agent tool, or a Workflow's `agent()` calls) — don't let every subagent default to whatever model you're running as. Each dispatch is an explicit choice; make it a cost-aware one.

## The real numbers (Anthropic API, per MTok, current-gen — platform.claude.com/docs/en/about-claude/pricing)

| Tier | Model | Input | Output | Relative cost |
|---|---|---|---|---|
| Cheap | Haiku 4.5 | $1 | $5 | 1x (baseline) |
| Balanced | Sonnet 5 | $2 | $10 | 2x |
| Premium | Opus 5 | $5 | $25 | 5x |

Opus costs 2.5x Sonnet and 5x Haiku, consistently across input and output. Per Artificial Analysis's Intelligence Index (artificialanalysis.ai/providers/anthropic), that cost gap tracks a real capability gap on hard multi-step reasoning — but Haiku is also markedly faster (~90 tok/s output vs. Opus's ~55) and lower-latency. This isn't "always use the cheapest" — it's "match the spend to what the task actually needs."

## Complexity tiers — pick a model per dispatch, not by default

**Haiku — mechanical, well-specified, low-ambiguity work:**
- Fetching a URL and extracting/summarizing specific facts
- Listing/searching files, running a linter and reporting output verbatim
- Simple classification/triage, boilerplate generation, format conversion
- Any task where a smaller model's answer is easy to verify and cheap to redo if wrong

**Sonnet — the default for real reasoning work:**
- Implementing a well-scoped ticket, writing tests against a concrete diff
- Standard code review, research-and-synthesize tasks, most subagent dispatches
- If you're unsure which tier fits, this is the right default — not Haiku

**Opus — high-stakes, ambiguous, or synthesis-heavy work:**
- Security review, architecture review — a missed finding is disproportionately costly
- Final synthesis/judgment across many conflicting findings or sources
- Genuinely open-ended or ambiguous planning where getting it wrong cascades

This is exactly the reasoning already applied to this plugin's own subagents: `security-reviewer` and `architecture-reviewer` run on Opus (high-stakes review), `tester` runs on Sonnet (frequent, well-scoped work). Apply the same judgment to any ad hoc subagent you dispatch, not just these three.

## In practice

- **Task tool / Agent tool dispatch:** pass the tier's model explicitly rather than letting it silently inherit the parent session's model.
- **Workflow `agent()` calls:** pass `{model: 'haiku'|'sonnet'|'opus', ...}` per call — omit only when you deliberately want to inherit, as a conscious choice, not a default.
- **A swarm/fan-out of many similar subagents:** default the whole fan-out to the cheapest tier that can do the job, and reserve Opus for a smaller number of judge/verify/synthesis passes at the end — usually far cheaper than running every parallel agent at the top tier "just in case."
- **When genuinely unsure:** Sonnet. It's the balanced default for a reason — don't reach for Opus out of caution alone, and don't reach for Haiku just because it's cheap if the task actually requires real reasoning.
- **Escalate reactively, not just by upfront category.** Start a dispatch at the tier the task category suggests. If it fails, comes back wrong, or the subagent reports it can't complete the task at its current tier, retry once at the next tier up — don't loop retries at the same tier, and don't pre-emptively start everything at Opus "to be safe."
- **Reconcile only final results.** Once a subagent's dispatch completes, read its returned output, not its full working trajectory (tool calls, intermediate drafts, retries). Reviewing the whole transcript defeats the point of delegating — the parent session should stay as lean as the subagent's summary allows.
- **Report the choice, briefly.** When dispatching a fan-out, a one-line note on why a tier was picked (e.g. "haiku — plain fact extraction, 8 parallel fetches") keeps the cost decision auditable rather than silent.
