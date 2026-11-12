---
name: stack-watch
description: Check whether the runtimes, frameworks and dependencies in the user's projects are end-of-life, behind the newest LTS, or have known vulnerabilities, and recommend updates. Covers Node, .NET, Python, Go, Rust, Java and any framework or package endoflife.date tracks (React, Next.js, Angular, Vue, ESLint, ...), CVEs in lockfiles via osv-scanner, and Node.js security advisories. Use when asked "is my stack up to date", which projects need an update or have vulnerabilities, to bump a runtime/framework, or when a "Stack watch" alert shows up.
---

# stack-watch

The CLI is `scripts/stack-watch.mjs` next to this file. It needs Node 18+ and has no dependencies. It runs on macOS, Linux and Windows.
Dependency vulnerabilities also need `osv-scanner` on PATH. Without it, that part is skipped and the report says so.

```
node scripts/stack-watch.mjs status            # last daily report (no network)
node scripts/stack-watch.mjs check --force     # refresh release data, rescan everything, rewrite report
node scripts/stack-watch.mjs scan <dir>...     # scan given dirs now; exit 2 = EOL or high/critical CVE, 1 = warnings
node scripts/stack-watch.mjs install           # schedule: hourly, real work once a day (catches up after downtime)
```

Report: `~/.cache/stack-watch/report.md` (`%LOCALAPPDATA%\stack-watch` on Windows). Config:
`~/.config/stack-watch/config.json` (`%APPDATA%\stack-watch\config.json` on Windows), for example:
`{"roots": ["~/Dev"], "exclude": ["_archive"], "watch": ["kubernetes"], "ignore": ["rust"]}`.
`watch` takes any product slug from https://endoflife.date (to announce new release lines). `ignore` silences a product.

## What the levels mean

- **error**: the release line is end-of-life; a dependency has a high/critical (CVSS ≥ 7) vulnerability or one on
  CISA KEV (exploited in the wild); or a malicious package is installed.
- **warn**: the version is behind the newest LTS, reaches EOL within 90 days, is no longer maintained, is a Node odd line, or floats on Current. Also: a Node pin older than its line's latest security release, an open floor (`>=3.9`) that still allows EOL, or a low/medium vulnerability.
- Products are matched dynamically. Every package or Docker image whose purl endoflife.date lists gets checked, so new
  products need no code change.

## When the user asks what to do

Recommend first. Don't rewrite files silently. Prioritise in this order: malicious packages (remove them, and treat the machine's credentials as exposed),
KEV-listed vulnerabilities, then high EPSS or high/critical CVEs with a fix, then EOL, then behind. Pass the report's
**Recommendations** on: GitHub malware alerts and Safe Chain for repos that don't have them.

- **Vulnerability**: name the package, the fixed version and the link. Prefer upgrading the direct dependency that pulls
  it in (`npm ls <pkg>`, `pnpm why`, `uv tree`, `dotnet list package --include-transitive`, `go mod why`, `cargo tree -i`).
  For many fixes, try `osv-scanner fix` or the package manager's audit fix.
- **Runtime bump**: change every declaration listed for the project together (`.nvmrc`, `engines`, Dockerfile, CI,
  `global.json`/`TargetFramework`, `.python-version`/`requires-python`, `go.mod`, toolchain files). Bump the matching
  types package (`@types/node`).
- **Framework major** (Next, React, Angular, .NET): link the official upgrade guide or codemod. Don't hand-edit.
- After any change, reinstall, build, run the tests and report what broke. Then run `scan <project>` again and confirm the
  findings are gone.
