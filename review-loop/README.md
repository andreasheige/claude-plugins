# review-loop

One CLI for code review and security checks on a diff, usable from any coding agent (Claude Code, Codex CLI,
Copilot CLI, ...) or a git hook. This is the public subset of a private tool: the scanner, the model workers and
the shared contract. The red-team runner and the golden evaluation set are not included.

| Path | What it is |
|---|---|
| `bin/review-loop` | the CLI: `scan` and `worker` |
| `review_loop/` | scan (D1 secrets, D2 hidden Unicode, D3 dependencies), worker launcher and adapters |
| `contract/` | JSON schemas for findings, records, worker output and accepts, with valid and invalid examples |
| `prompts/` | finder and verifier prompts |
| `golden/synthetic/build.sh` | builds small seeded repos (SQL injection, prompt injection, ...) used by the tests |
| `docs/cooldowns.md` | package-manager minimum-release-age settings |
| `skills/review-loop/` | how Claude should call the CLI |

## Setup

1. Install the scanners: `brew install gitleaks osv-scanner`.
2. Pin them. The CLI refuses a scanner that isn't in the lock or whose hash changed:

   ```sh
   mkdir -p ~/.config/review-loop
   for t in gitleaks osv-scanner; do
     p="$(python3 -c 'import os,shutil,sys; print(os.path.realpath(shutil.which(sys.argv[1])))' "$t")"
     printf '%s\t%s\t%s\t%s\n' "$t" "$("$t" --version 2>&1 | head -1 | grep -oE '[0-9]+(\.[0-9]+)+')" "$p" "$(shasum -a 256 "$p" | cut -d' ' -f1)"
   done > ~/.config/review-loop/tools.lock
   ```

   Re-run after every scanner upgrade, and read the diff before you do.
3. Optional: `export REVIEW_LOOP_OWN_ORIGIN='github\.com[:/]your-user/'`. Repos whose origin matches may send
   dependency names to osv.dev and the public registries. Every other repo with a remote stays offline
   (`osv-scanner --offline`), which is the safe default for client code.

## Use

```sh
bin/review-loop scan --staged
bin/review-loop scan --range origin/main..HEAD --sarif out.sarif
```

As a pre-commit hook: `review-loop scan --staged --format text || exit 1`.

Exit codes: `0` pass, `1` block, `2` needs a human, `3` tool error (treat as block). See `contract/README.md`.

## Tests

```sh
python3 -m unittest discover -s tests
```

No network and no model calls; the Claude adapter is checked against stored real output from the synthetic repos.

## Limits

- A local check stops mistakes, not a determined agent: `git commit --no-verify` skips a hook. Pair it with
  server-side checks where your plan allows them.
- Model review finds bugs; a pass is "no findings reported", never "secure".
