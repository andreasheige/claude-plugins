---
description: Create a Product Requirements Document for a new feature or epic.
argument-hint: "<feature-or-epic-name>"
---
TASK: Create a comprehensive PRD for $ARGUMENTS.

1. PRIMING: Ask the user for context if not already in the conversation
   (problem, users, constraints). Read any existing docs the user points to.
2. END STATE: A markdown PRD saved at `docs/prd/$ARGUMENTS.md` covering
   scope, non-goals, objectives, and success metrics.
3. VALIDATION PLAN:
   - Level 1 (Lint): Markdown is well-formed, headings present.
   - Level 4 (Agent Execution — mandatory): Re-read the written file back and
     confirm every required section (Scope, Non-Goals, Success Metrics) is
     present and non-empty.
4. GO:
   - Surface open questions and ambiguities before writing (think before
     coding) — ask rather than assume.
   - Draft the PRD; keep it to what's needed to hand off to
     `/devsecops-workflow:plan-architecture`, not a speculative wishlist.
