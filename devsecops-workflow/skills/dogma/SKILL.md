---
name: dogma
description: Iterative critic-loop reasoning. Simulates "more loops = deeper thinking" via solve → critic → refine, halting when the critic finds nothing substantive. Use when the user says "dogma", "/dogma", or asks for deep/iterative reasoning on a hard problem.
---

# Dogma

Run a single-track critic loop on the user's task — spend more inference compute per problem by cycling solve → critic → refine until an adversarial critic finds nothing substantive.

## When to use

- Hard reasoning, design, or coding problems where a one-shot answer feels shallow.
- The user explicitly asks for `dogma`, `/dogma`, or "think deeper".
- NOT for trivial tasks — the loop adds 2–4x latency and token cost.

## Phase 1 — Solve (iteration 0)

Produce an initial answer to the user's task, with reasoning visible.

## Phase 2 — Critic pass

Dispatch a **fresh** `general-purpose` Agent (see `cost-aware-orchestration` for model tier — Sonnet is the right default critic, escalate to Opus for high-stakes work) with this prompt:

```
Independent critic. Do NOT defend or extend the answer below — find what's wrong, missing, or weak.

Return a numbered list of substantive issues, or the literal string NO_SUBSTANTIVE_ISSUES if the answer holds up.

Substantive = correctness errors, logic gaps, missing edge cases, security issues, performance problems.
NOT substantive = style preferences, minor wording, formatting.

## Task
<the original user task>

## Answer to Critique
<the current answer>
```

## Phase 3 — Halt check

- Critic returns `NO_SUBSTANTIVE_ISSUES` or only stylistic nits → **STOP**, present the current answer.
- Otherwise → continue to refine.

## Phase 4 — Refine

Address the critic's substantive issues. Do not rewrite from scratch — surgically revise only what was flagged.

## Phase 5 — Repeat

Repeat phases 2–4 up to **3 total critic passes**. If still contested after 3 iterations, present the final version plus an "unresolved tensions" note.

## Output format

1. The final answer — clean, complete, ready to use.
2. Meta line: `Iterations: N. Halt reason: <critic-clean | max-iters>.`
3. Unresolved tensions (only if halt reason is max-iters) — brief list.

Don't dump every intermediate draft. The user can ask to see critic transcripts if they want them.

## Constraints

- Maximum 3 critic passes — never loop forever.
- Each critic must be a fresh Agent dispatch — no context leakage from prior iterations, and never spawn a critic that has seen the solve reasoning.
- Not for trivial lookups or simple factual questions.
