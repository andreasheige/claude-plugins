---
name: git-workflow
description: Use this skill whenever committing, naming a branch, integrating upstream changes, or opening/landing a pull request. Encodes Conventional Commits format, the branch naming convention, and the rebase-only policy — never merge, always rebase.
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
Agents stop at the open PR: merging, approving and auto-merge are the user's, and the guard denies them for agents. The user lands with `gh pr merge --rebase` — never the bare `gh pr merge` (which falls back to whatever the repo's default is, possibly a merge commit or squash) and never `--squash`. See the `/devsecops-workflow:open-pr` command for the rebase → validate → push → PR sequence. Note: the target GitHub repo must have "Allow rebase merging" enabled in its settings for this to succeed — that's a per-repo setting, not something this workflow controls.

## Quick reference — what's blocked vs. required
| Action | Status |
|---|---|
| `git merge` (any form) | Blocked |
| `git push --force` / `-f` | Blocked (any branch) |
| `git push --force-with-lease` on `main`/`master` | Blocked |
| `git push --force-with-lease` on a feature branch | Allowed — required after rebasing an already-pushed branch |
| Direct `git push` to `main`/`master` | Blocked — use a PR |
| Non-conventional commit message | Rejected by the `commit-msg` hook |
| `gh pr merge`, approving, auto-merge (agent) | Blocked — stop at the open PR; the user lands it with `gh pr merge --rebase` |
| Changing GitHub/Azure/ADO settings or resources (agent) | Asks the user first |
