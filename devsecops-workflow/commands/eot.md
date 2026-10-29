---
description: End-of-ticket review by the review-loop CLI — scan, other-family finder and verifier, fix, recheck (inner loop, step 6).
argument-hint: "[ticket-path]"
---
TASK: Run the end-of-ticket review for $ARGUMENTS.

1. PRIMING: `/devsecops-workflow:validate` and `/devsecops-workflow:review-changes`
   have passed and the ticket's work is committed on its feature branch.
   Find the CLI: `$REVIEW_LOOP_BIN`, else `review-loop` on `PATH`, else
   `~/Dev/review-loop/bin/review-loop`. If none is executable, say so and
   dispatch the `security-reviewer` subagent (Task tool, agent type
   `devsecops-workflow:security-reviewer`) instead, with the output of
   `git diff <base>...HEAD` pasted into its prompt (it has no shell) —
   that is the only case it runs.
2. END STATE: The latest review-loop record for this branch exits 0, or the
   user has decided on every open finding.
3. VALIDATION PLAN:
   - Level 4 (Agent Execution — mandatory): show the real `--format text`
     output of each run. Never describe exit 0 as "secure"; it means no
     finding was reported.
4. GO, in order:
   - `review-loop eot --ticket <ticket-path> --format text`. It reviews
     `merge-base(origin/main, HEAD)..HEAD`; pass `--base <ref>` for any other
     base (e.g. an epic branch). The reviewers are from the other model
     family than the commit trailers name, so keep `Co-Authored-By` honest.
   - Act on the exit code:
     - `0` — done; continue to `/devsecops-workflow:open-pr`.
     - `1` (blocked) — fix each `blocking`/`hard` finding test-first, re-run
       `/devsecops-workflow:validate` from the failing level, commit, then
       `review-loop recheck --ticket <ticket-path> --format text`. Recheck
       reads only what changed since the last record, checks again whether
       the earlier findings still hold, and never repeats a settled one.
       `advisory` findings are yours to judge; don't loop on them.
     - `2` (needs_human) — stop and show the user the findings. This is also
       what recheck returns after its second round with findings still open.
       Don't run another `eot` to get a fresh round.
     - `3` (error) — stop and report the error. A failed review never counts
       as a pass.
   - Never edit, delete or hand-write anything under
     `$(git rev-parse --git-common-dir)/review-loop/`.
