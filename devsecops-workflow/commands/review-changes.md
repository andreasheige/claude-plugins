---
description: Fresh-context review of the ticket's diff against architectural constraints (inner loop, step 5).
argument-hint: "[ticket-path]"
---
TASK: Review the changes for $ARGUMENTS.

1. PRIMING: Load the diff, the architecture doc from the outer loop, and the
   ticket file itself (Scope, Files, Definition of Done).
2. END STATE: A review verdict (approve / changes-requested) with findings
   ranked by severity, and, if changes are requested, those fixes applied
   before the ticket is considered committable.
3. VALIDATION PLAN:
   - Level 4 (Agent Execution — mandatory): Every "changes requested" item
     is either fixed and re-validated via `/devsecops-workflow:validate`, or
     explicitly accepted by the user with a stated reason — never silently
     dropped.
4. GO: Dispatch the `architecture-reviewer` subagent (Task tool, agent type
   `devsecops-workflow:architecture-reviewer`) with the diff, the
   architecture doc, and the full ticket text pasted verbatim, including its
   Definition of Done — the reviewer judges the diff against what the ticket
   promised, not only against the architecture. A fresh subagent context is required here — reviewing
   in the same context that wrote the code defeats the purpose (confirmation
   bias). Apply fixes for anything the reviewer flags, then re-run
   `/devsecops-workflow:validate` before considering the ticket done.
