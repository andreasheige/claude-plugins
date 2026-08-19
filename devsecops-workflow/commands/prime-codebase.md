---
description: Load only the files relevant to one ticket (inner loop, step 1).
argument-hint: "<ticket-path-or-description>"
---
TASK: Prime context for $ARGUMENTS.

1. PRIMING: Identify the minimum set of files this ticket touches or must
   respect (interfaces it calls, tests it must satisfy, style to mirror).
2. END STATE: Those files (and only those) are read into context.
3. VALIDATION PLAN:
   - Level 4 (Agent Execution — mandatory): List the files you read back to
     the user; confirm none is irrelevant bloat and nothing required is
     missing.
4. GO: Read the ticket, then read exactly the files it needs — resist
   reading the whole module "just in case".
