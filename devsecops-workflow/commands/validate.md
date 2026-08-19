---
description: Run all 5 classes of checks, including mandatory adversarial testing (inner loop, step 4).
argument-hint: "[ticket-path]"
---
TASK: Execute a full validation sweep for $ARGUMENTS.

1. PRIMING: Identify every file changed for this ticket.
2. END STATE: A validation report confirming Levels 1-5 all ran, with the
   adversarial test suite (from the Tester) surviving.
3. VALIDATION PLAN:
   - Level 4 (Agent Execution — mandatory, non-skippable): Every level below
     must show real executed output, not an assertion that it "should pass".
4. GO — execute in order, do not skip or reorder:
   - **Level 1 (Compile & Lint):** run the project's linter/type-checker.
   - **Level 2 (Unit Integrity):** dispatch the `tester` subagent (via the
     Task tool, agent type `devsecops-workflow:tester`) to write an
     adversarial unit test suite against the *diff*, not against the
     Implementer's own description of what it does. The Implementer's
     session must not write these tests itself.
   - **Level 3 (Integration):** run integration tests covering the ticket's
     touched interfaces.
   - **Level 4 (Agent Execution — MANDATORY, NEVER SKIPPABLE):** actually
     execute the changed code end-to-end (run the app/script/endpoint) and
     inspect real runtime output. A green test suite alone does not satisfy
     this level — you must observe the feature working, or the bug
     reproduced-then-fixed, with your own eyes on real output.
   - **Level 5 (Stack-Specific incl. Security):** dispatch the
     `security-reviewer` subagent (Task tool, agent type
     `devsecops-workflow:security-reviewer`) for a dedicated security pass
     (secrets, injection, authz, dependency risk) plus any relevant
     E2E/perf checks for this stack.
   - Report pass/fail per level. Any failure at any level blocks moving to
     `/devsecops-workflow:review-changes` — fix and re-run from the failing
     level.
