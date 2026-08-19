---
name: dogma-deep
description: Deep Dogma variant. Fans out to 3 parallel agents with different framings, synthesizes, then runs a critic loop. Use when the user says "dogma-deep", "/dogma-deep", or "deep dogma".
---

# Dogma Deep

Heavier sibling of `dogma`. Run a fan-out → synthesize → critic-loop workflow to approximate both breadth (multiple expert framings) and depth (looped refinement) on a genuinely ambiguous problem.

## When to use

- Genuinely ambiguous or open-ended problems where multiple framings exist — architectural decisions, research synthesis, hard design tradeoffs.
- The user explicitly asks for `dogma-deep` or "deep dogma".
- NOT for tasks with a single obvious framing — `dogma` is enough there.
- Cost: ~5–8x a one-shot answer. Don't reach for this casually.

## Phase 1 — Fan-out (parallel)

Dispatch **3 Agents in a single message** (so they run concurrently), each given the SAME task but a deliberately DIFFERENT framing. Pick framings that genuinely differ, not three variants of the same lens.

**Default framings** (use unless a more domain-specific split is obvious):

1. **First-principles** — derive the answer from fundamentals, ignore convention.
2. **Pattern-matching** — what do existing solutions / prior art look like? Adapt the closest match.
3. **Adversarial / risk-first** — what would make this fail? Answer by avoiding the worst failure modes.

Agent type: `general-purpose` for each (or a domain specialist if obviously a better fit). Prompt template:

```
You are solving the following task with a specific framing. Give a complete, well-reasoned answer.

## Framing
<framing description — e.g. "First-principles: derive from fundamentals, ignore convention">

## Task
<the original user task>

Provide your complete answer with reasoning. Be thorough.
```

After all 3 complete, read their results.

## Phase 2 — Synthesize

You (not a subagent) integrate the three answers — synthesis needs full context and must not be delegated:

- Extract the strongest specific claims from each framing.
- Name disagreements explicitly rather than averaging them away.
- Pick a side on each disagreement and explain why.
- Weave in complementary insights that don't conflict.

## Phase 3 — Critic loop

Same mechanics as `dogma`'s critic loop, run against the synthesis:

1. Dispatch a fresh `general-purpose` Agent (model tier per `cost-aware-orchestration`):

```
Independent critic. Find what's wrong, missing, or weak in the synthesized answer below.

Return a numbered list of substantive issues, or the literal string NO_SUBSTANTIVE_ISSUES if the answer holds up.

Substantive = correctness errors, logic gaps, missing edge cases, security issues, performance problems, integration oversights.
NOT substantive = style preferences, minor wording, formatting.

## Original Task
<the original user task>

## Framings Used
<brief note of the 3 framings>

## Synthesized Answer to Critique
<the synthesis>
```

2. `NO_SUBSTANTIVE_ISSUES` → **STOP**.
3. Otherwise → refine surgically (don't rewrite from scratch).
4. Repeat up to **3 total critic passes**; halt on clean critic or max iterations.

## Output format

1. The final synthesized + refined answer — clean, complete, ready to use.
2. Framings used — which 3 lenses, and which disagreements survived synthesis.
3. Meta line: `Fan-out: 3 agents. Critic iterations: N. Halt reason: <critic-clean | max-iters>.`

Don't dump all three raw fan-out answers — the user can ask for them if they want.

## Constraints

- Always launch all 3 fan-out agents in a single response (parallel), never sequentially.
- Maximum 3 critic passes after synthesis.
- Each critic must be a fresh Agent dispatch — no context from prior iterations.
- Synthesis must be done by you, never delegated.
- Not for trivial tasks — suggest `dogma` instead if the problem has a single obvious framing.
- Pick framings that are genuinely orthogonal — if you can't name 3 different lenses, the problem likely doesn't need this skill.
