---
description: Decompose an architecture doc into single-concern, ticket-sized tasks (outer loop, step 3).
argument-hint: "<path-to-architecture-doc>"
---
TASK: Decompose the architecture at $ARGUMENTS into individual tickets.

1. PRIMING: Read the architecture doc and identify component boundaries.
2. END STATE: A list of tickets (one file per ticket under
   `docs/tickets/`), each single-concern, each completable in one inner-loop
   pass, each stating its own success criteria.
3. VALIDATION PLAN:
   - Level 1 (Lint): Each ticket file has scope, files-likely-touched, and a
     "Definition of Done" section.
   - Level 4 (Agent Execution — mandatory): No two tickets claim the same
     file for conflicting changes; no dependency gap (ticket B needs
     something ticket A defines, but A isn't ordered first).
4. GO: Slice by concern, not by file — a ticket should read as one coherent
   change a reviewer could approve on its own.
