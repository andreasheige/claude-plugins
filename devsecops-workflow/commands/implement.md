---
description: Execute the implementation plan step by step (inner loop, step 3 — Implementer role).
argument-hint: "[plan-path]"
---
TASK: Implement $ARGUMENTS.

1. PRIMING: Load the implementation plan and the primed files.
2. END STATE: Code written matching the plan, one step at a time, test-first
   (Red → Green) for every step that has logic, verify check run before
   moving to the next.
3. VALIDATION PLAN:
   - Level 1 (Lint): Syntax/type-check the changed files after each step.
   - Level 4 (Agent Execution — mandatory): Run each step's stated verify
     check for real and show the output — do not claim a step is done
     without having executed its check.
4. GO, per step, in this order — do not write implementation code before
   step 4a for any step that has logic to test:
   a. **Red** — write the test matching this step's `verify:` clause. Run it
      and confirm it fails for the expected reason (not a typo or setup
      error).
   b. **Green** — write the minimal code to make it pass. Mirror existing
      style, touch only what this step specifies.
   c. Run the test again for real and show it passing before moving to the
      next step.

   **Exception — pure UX/presentational steps with no logic** (styling,
   markup, copy, layout with no conditional behavior): skip 4a–4b, implement
   directly, and note in your step summary that this step had no logic to
   test-first. If a step turns out to have logic once you're in it, don't
   silently skip the exception — go back to 4a.

**Role boundary:** You are acting as the Implementer. The tests you write in
step 4a are step-verification smoke tests, scoped to that step's stated
`verify:` clause — you must NOT write or extend the ticket's broader
adversarial test suite. That's the Tester's job, done independently in
`/devsecops-workflow:validate`, against the diff, without seeing your
reasoning — that separation stays even though you're now writing tests
too.
