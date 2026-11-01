---
name: git-workflow
description: Use this skill whenever committing, naming a branch, integrating upstream changes, opening/landing a pull request, or cleaning up after one is merged. Encodes Conventional Commits format, the branch naming convention, and the rebase-only policy — never merge, always rebase.
---

# Git Workflow

## Commit messages — Conventional Commits
```
<type>(<optional-scope>): <description>
```
Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Add `!` before `:` for a breaking change (`feat!: ...`). This is enforced by a global `commit-msg` git hook — a malformed message will be rejected with a clear error, not silently accepted.

## Branch naming
```
<type>/<short-kebab-description>
```
Mirrors the commit types above, e.g. `feat/add-login-flow`, `fix/null-pointer-in-parser`, `chore/bump-deps`.

## Integration — never merge, always rebase
This machine enforces "never merge" at multiple layers: a global `pre-merge-commit` git hook rejects merge commits, and `~/.claude/hooks/guardrail.sh` blocks the `git merge` command outright for Claude Code specifically (fast-forward or not).

To update a feature branch with upstream changes:
```
git fetch && git rebase origin/main
```
Resolve conflicts as part of the rebase (`git rebase --continue`), never by falling back to a merge commit. If the branch was already pushed before the rebase, update the remote with:
```
git push --force-with-lease
```
`--force-with-lease` is allowed on feature branches (guardrail.sh permits it) but hard-denied on `main`/`master` in any form — rebase workflows never need it there anyway, since `main` should only move forward via landed PRs.

## Landing a PR
Agents land only a risk:low PR, through `review-loop land <pr>` (it recomputes the tier from the PR head and merges with `--rebase --match-head-commit`). Everything else stops at the open PR: merging, approving and auto-merge are the user's, and the guard denies them for agents. The user lands with `gh pr merge --rebase` — never the bare `gh pr merge` (which falls back to whatever the repo's default is, possibly a merge commit or squash) and never `--squash`. See the `/devsecops-workflow:open-pr` command for the rebase → validate → push → PR sequence. Note: the target GitHub repo must have "Allow rebase merging" enabled in its settings for this to succeed — that's a per-repo setting, not something this workflow controls.

## After a PR is merged — clean up its worktree and branch
Once a branch's PR is merged, remove what it left locally; don't let merged worktrees and branches pile up.
1. Merged means the PR says so: `gh pr view <branch> --json state,headRefOid` shows `MERGED`. PRs land by rebase, so
   the branch is never an ancestor of `main` and `git branch -d` can't tell; the PR state is the source of truth.
2. Only if the local branch still points at the merged head (`git rev-parse <branch>` equals `headRefOid`) and its
   worktree has no uncommitted changes (`git -C <path> status --porcelain` is empty):
   `git worktree remove <path>`, then `git branch -D <branch>`.
3. `git fetch --prune` drops the remote-tracking ref; GitHub deletes the remote branch on merge where
   "Automatically delete head branches" is on. Deleting a remote branch yourself is a platform write: ask first.
4. Anything else stops and asks the user: an open or closed-unmerged PR, commits after the merged head, uncommitted
   changes, or a branch with no PR.
Do it right after `review-loop land` merges, and whenever a session finds worktrees left by an earlier one.

## Quick reference — what's blocked vs. required
| Action | Status |
|---|---|
| `git merge` (any form) | Blocked |
| `git push --force` / `-f` | Blocked (any branch) |
| `git push --force-with-lease` on `main`/`master` | Blocked |
| `git push --force-with-lease` on a feature branch | Allowed — required after rebasing an already-pushed branch |
| Direct `git push` to `main`/`master` | Blocked — use a PR |
| Non-conventional commit message | Rejected by the `commit-msg` hook |
| `review-loop land <pr>` (agent) | Allowed — merges only a risk:low, reviewed, green PR |
| `gh pr merge`, approving, auto-merge (agent) | Blocked — stop at the open PR; the user lands it with `gh pr merge --rebase` |
| Changing GitHub/Azure/ADO settings or resources (agent) | Asks the user first |
| Worktree + local branch of a merged PR | Required — remove once `MERGED` and nothing newer or uncommitted |
