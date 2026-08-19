---
description: Fresh-context review of the ticket's diff against architectural constraints (inner loop, step 5).
argument-hint: "[ticket-path]"
---
TASK: Review the changes for $ARGUMENTS.

1. PRIMING: Load the diff and the architecture doc from the outer loop.
2. END STATE: A review verdict (approve / changes-requested) with findings
   ranked by severity, and, if changes are requested, those fixes applied
   before the ticket is considered committable.
3. VALIDATION PLAN:
   - Level 4 (Agent Execution — mandatory): Every "changes requested" item
     is either fixed and re-validated via `/devsecops-workflow:validate`, or
     explicitly accepted by the user with a stated reason — never silently
     dropped.
4. GO: Dispatch the `architecture-reviewer` subagent (Task tool, agent type
   `devsecops-workflow:architecture-reviewer`) with the diff and the
   architecture doc. A fresh subagent context is required here — reviewing
   in the same context that wrote the code defeats the purpose (confirmation
   bias). Apply fixes for anything the reviewer flags, then re-run
   `/devsecops-workflow:validate` before considering the ticket done.
