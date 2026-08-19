---
description: Turn a primed ticket into an atomic step list with embedded verification (inner loop, step 2).
argument-hint: "[ticket-path]"
---
TASK: Create an implementation plan for $ARGUMENTS.

1. PRIMING: Use the already-primed context for this ticket; do not re-scan
   the codebase.
2. END STATE: A step list where every step is `[step] -> verify: [check]` —
   no step without a stated, checkable success criterion.
3. VALIDATION PLAN:
   - Level 1 (Lint): Plan structure — every numbered step has a paired
     verify line.
   - Level 4 (Agent Execution — mandatory): Every verify line names a
     concrete, runnable check (a command, a test name, an observable
     output) — not a vague "make sure it works".
4. GO: Break the ticket into the smallest ordered set of surgical steps.
   Do not write implementation code in this step — plan only.
