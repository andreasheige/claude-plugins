---
description: Rebase a ticket's feature branch onto latest main, re-validate, push, open the PR with its review effort, and land it only if it is risk:low. Otherwise the user merges.
argument-hint: "[ticket-path]"
---
TASK: Open the PR for $ARGUMENTS.

1. PRIMING: Confirm the current branch is a feature branch (not `main`/`master`)
   and that `/devsecops-workflow:validate` and `/devsecops-workflow:eot` have
   already passed for this ticket.
2. END STATE: The feature branch is rebased onto the latest `main`, re-validated,
   pushed, and a PR is open with its `review-loop risk` section. A risk:low PR
   is landed with `review-loop land`; anything else waits for the user (the
   guard denies `gh pr merge` and every other merge or approve path for agents).
3. VALIDATION PLAN:
   - Level 4 (Agent Execution — mandatory): `gh pr view --json url,state,mergeable`
     shows the PR open and mergeable; the branch has no merge commit
     (`git log --graph origin/main..HEAD`).
4. GO, in order — never substitute `git merge` or a squash/merge PR landing
   for any of these steps:
   - `git fetch && git rebase origin/main` — never `git merge origin/main`.
     Resolve conflicts as part of the rebase.
   - Re-run `/devsecops-workflow:validate` — a rebase can change behavior;
     don't skip re-validation because it "already passed" before the rebase.
   - `review-loop recheck --ticket <ticket-path> --format text` (skip only if
     `/devsecops-workflow:eot` used the `security-reviewer` fallback). If the
     rebase left the patch-id unchanged it reports the last outcome without
     running a model; otherwise it reviews what the rebase changed. Push only
     on exit 0; on 1–3 follow `/devsecops-workflow:eot`.
   - Push the branch: `git push` if this is its first push, otherwise
     `git push --force-with-lease` (required after a rebase rewrites commits
     already on the remote). Never push to `main`/`master` directly.
   - `gh pr create` with a title matching the Conventional Commits format
     (see the `git-workflow` skill) and a body summarizing the change, ending
     with the output of `review-loop risk --format md` (how much review it
     needs, decided in code). Never add a `risk:` label by hand.
   - `review-loop land <pr>`. Exit 0: landed (low risk, reviewed clean, green
     checks). Exit 1: refused with the reasons; stop and give the user the PR
     link and the tier, they merge. Exit 3: report the error. Never run
     `gh pr merge`, approve, or enable auto-merge yourself.
