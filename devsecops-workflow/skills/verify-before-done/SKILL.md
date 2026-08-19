---
name: verify-before-done
description: Use this skill before saying a task/ticket/fix is done, working, complete, or ready — or before suggesting the user test it themselves. Encodes the mandatory 5-class validation sweep; Level 4 (actually executing the code and inspecting real output) is never skippable, no exceptions for "simple" or "obviously correct" changes.
---

# Verify Before Done

Never write implementation code until you know what "done" is checkable
against. Before claiming any task is complete, confirm all 5 classes of
checks ran — not just the ones that are convenient:

1. **Compile & Lint** — syntax/types/static analysis pass.
2. **Unit Integrity** — components do what they claim, verified by tests
   *not written by the same pass that implemented them* (see the
   `devsecops-workflow` plugin's `tester` agent if that workflow is
   enabled).
3. **Integration** — components interact cleanly across their contracts.
4. **Agent Execution — MANDATORY, NEVER SKIPPABLE.** You must actually run
   the code end-to-end yourself and look at real runtime output. Passing
   unit tests is not a substitute. "The logic is clearly correct" is not a
   substitute. If you cannot execute it (no runtime available, requires the
   user's credentials, etc.), say so explicitly and flag the task as
   unverified rather than calling it done.
5. **Stack-Specific** — whatever else this stack demands: E2E, performance,
   and always security (secrets, injection, authz, dependency risk) for
   anything touching input handling, auth, or external data.

If you're about to write "this should work", "this looks correct", or
similar — stop and go run it instead.
