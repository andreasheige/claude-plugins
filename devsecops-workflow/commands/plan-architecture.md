---
description: Design the technical architecture for a PRD (outer loop, step 2).
argument-hint: "<path-to-prd>"
---
TASK: Design the architectural spec for $ARGUMENTS.

1. PRIMING: Read the PRD at $ARGUMENTS and the relevant parts of the existing
   codebase (structure, conventions, existing interfaces it must fit).
2. END STATE: An architecture doc defining components, interfaces, data
   flows, and explicit non-goals, saved next to the PRD.
3. VALIDATION PLAN:
   - Level 1 (Lint): Run `scripts/check-doc-structure.sh architecture <file>`
     (from this plugin) — deterministic check that Components, Interfaces,
     Data Flows, and Non-Goals are all present and non-empty.
   - Level 4 (Agent Execution — mandatory): The script can't judge whether
     interfaces actually map to listed components — that's a semantic
     check, do it by hand: every proposed interface maps to an existing or
     clearly-new code unit; no interface references a component that
     doesn't appear in the "Components" section.
4. GO: Identify component boundaries, define APIs/contracts, outline
   dependencies and sequencing. Prefer the smallest architecture that
   satisfies the PRD — no speculative extensibility.
