---
description: Execute the implementation plan step by step (inner loop, step 3 — Implementer role).
argument-hint: "[plan-path]"
---
TASK: Implement $ARGUMENTS.

1. PRIMING: Load the implementation plan and the primed files.
2. END STATE: Code written matching the plan, one step at a time, each
   step's verify check run before moving to the next.
3. VALIDATION PLAN:
   - Level 1 (Lint): Syntax/type-check the changed files after each step.
   - Level 4 (Agent Execution — mandatory): Run each step's stated verify
     check for real and show the output — do not claim a step is done
     without having executed its check.
4. GO: Implement sequentially, mirroring existing style, touching only what
   the plan specifies (surgical changes).

**Role boundary:** You are acting as the Implementer. You may write
production code and, if truly needed, minimal smoke checks to drive your own
step-by-step execution — but you must NOT write or extend the adversarial
test suite for this ticket. That is the Tester's job, done in
`/devsecops-workflow:validate`.
