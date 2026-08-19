---
description: Land a ticket's feature branch — rebase onto latest main, re-validate, push, open the PR, and land it via rebase-merge.
argument-hint: "[ticket-path]"
---
TASK: Land $ARGUMENTS.

1. PRIMING: Confirm the current branch is a feature branch (not `main`/`master`)
   and that `/devsecops-workflow:validate` has already passed for this ticket.
2. END STATE: The feature branch is rebased onto the latest `main`, re-validated,
   pushed, a PR is open, and it is landed via rebase-merge — no merge commit
   anywhere in the history.
3. VALIDATION PLAN:
   - Level 4 (Agent Execution — mandatory): after landing, confirm `main`'s
     history is linear for this change (`git log --graph` shows no merge
     commit for it).
4. GO, in order — never substitute `git merge` or a squash/merge PR landing
   for any of these steps:
   - `git fetch && git rebase origin/main` — never `git merge origin/main`.
     Resolve conflicts as part of the rebase.
   - Re-run `/devsecops-workflow:validate` — a rebase can change behavior;
     don't skip re-validation because it "already passed" before the rebase.
   - Push the branch: `git push` if this is its first push, otherwise
     `git push --force-with-lease` (required after a rebase rewrites commits
     already on the remote). Never push to `main`/`master` directly.
   - `gh pr create` with a title matching the Conventional Commits format
     (see the `git-workflow` skill) and a body summarizing the change.
   - Land with `gh pr merge --rebase` — never bare `gh pr merge`, never
     `--squash`. If the repo doesn't allow rebase-merging, stop and tell the
     user rather than falling back to a different merge strategy.
