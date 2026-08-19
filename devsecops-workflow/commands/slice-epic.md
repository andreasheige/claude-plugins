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
   - Level 1 (Lint): Run `scripts/check-doc-structure.sh ticket <file>`
     (from this plugin) against every generated ticket — deterministic
     check that Scope, Files (likely touched), and Definition of Done are
     all present and non-empty. Then run
     `scripts/check-doc-structure.sh ticket-conflicts <tickets-dir>` — it
     flags any file listed by more than one ticket (a warning, not an
     automatic fail; overlap on a shared file isn't always a real
     conflict).
   - Level 4 (Agent Execution — mandatory): For anything the conflicts
     check flagged, judge by hand whether it's a real conflicting change;
     also check for dependency gaps (ticket B needs something ticket A
     defines, but A isn't ordered first) — the script can't see that.
4. GO: Slice by concern, not by file — a ticket should read as one coherent
   change a reviewer could approve on its own.
