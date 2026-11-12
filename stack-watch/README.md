# stack-watch

A daily check of everything your projects run on. It tells you when something needs updating:

- **End-of-life and outdated versions** of runtimes and frameworks. Release data comes from
  [endoflife.date](https://endoflife.date), which tracks 480+ products. Runtimes are read from their usual files:

  | Runtime | Read from |
  |---|---|
  | Node | `.nvmrc`, `.node-version`, `engines`, `volta`, `.tool-versions`, `mise.toml` |
  | .NET | `global.json`, `TargetFramework(s)` |
  | Python | `.python-version`, `requires-python`, `runtime.txt` |
  | Go | `go.mod` |
  | Rust | `rust-toolchain`, `rust-version` |
  | Java | `.java-version`, `.sdkmanrc`, Maven, Gradle |

  Docker `FROM` lines, GitHub Actions `setup-*` and Azure Pipelines tasks are checked too.
  Frameworks and packages are matched **dynamically**: any dependency in a lockfile whose purl endoflife.date lists gets
  checked (React, Next.js, Angular, Vue, ESLint, …). New products need no code change.
- **Known vulnerabilities** in lockfiles for npm, pnpm, yarn, NuGet, PyPI/uv, Go, Cargo, Maven and others, via
  [osv-scanner](https://github.com/google/osv-scanner) (GitHub advisories, PyPA, RustSec, Go vulndb, …), grouped per
  lockfile with the fixed version.
- **Exploited and malicious, first**: CVEs on CISA's [Known Exploited Vulnerabilities](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
  list are escalated and sorted to the top, then ordered by [EPSS](https://www.first.org/epss/) (probability of
  exploitation within 30 days), then CVSS. Malicious packages (OSV `MAL-` ids from the OpenSSF malicious-packages
  dataset, and optionally [Aikido's malware lists](https://intel.aikido.dev)) get their own "remove now" section.
- **Recommendations**: for repos hosted on GitHub (read from `.git/config`, no API calls), a link to switch on
  Dependabot alerts and malware alerts, which alert in real time between runs. If you use npm or pip and don't have
  [Aikido Safe Chain](https://github.com/AikidoSec/safe-chain), a suggestion to install it so known malware is blocked at install time.
- **Advisories**: Node.js security release posts from the nodejs.org vulnerability feed, plus whether your installed
  Node predates the latest security release.
- **Your machine**: installed node/dotnet/python3/go/rustc/java versions against the same data.

You get a desktop notification when the alert changes, and a one-line nudge when an agent session starts.

## Install

You need Node 18+. For dependency CVEs you also need `osv-scanner`: `brew install osv-scanner` · `winget install Google.OSVScanner` ·
`go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest`.

```sh
git clone https://github.com/andreasheige/claude-plugins.git
S="$PWD/claude-plugins/stack-watch/skills/stack-watch/scripts/stack-watch.mjs"

mkdir -p ~/.config/stack-watch
echo '{"roots": ["~/Dev"], "exclude": ["_archive"], "watch": ["kubernetes"]}' > ~/.config/stack-watch/config.json

node "$S" install          # launchd (macOS) · systemd --user timer (Linux) · Task Scheduler (Windows)
node "$S" check --force    # first report now
```

The schedule fires every hour and at login. A date stamp makes it do the real work once a day, so if the machine was off,
the check runs at the next start. A failed download leaves no stamp, so it retries an hour later.
On Windows, the config file goes in `$env:APPDATA\stack-watch\config.json`.

### The skill in each harness

| Harness | How | Session-start nudge |
|---|---|---|
| Claude Code | `/plugin marketplace add andreasheige/claude-plugins`, then `/plugin install stack-watch@personal-plugins` | built in (SessionStart hook) |
| Codex CLI | symlink `skills/stack-watch` into `~/.agents/skills/` | line in `~/.codex/AGENTS.md` |
| GitHub Copilot CLI | `~/.copilot/skills/` | line in `~/.copilot/copilot-instructions.md` |
| pi | `~/.pi/agent/skills/` | line in `~/.pi/agent/AGENTS.md` |
| opencode | `~/.config/opencode/skills/` | line in `~/.config/opencode/AGENTS.md` |

The line for harnesses without hooks:

> If `~/.cache/stack-watch/alert.txt` exists, mention its one line to me once at the start of the session.

## Use

```sh
node "$S" status               # last report
node "$S" scan ~/Dev/my-app    # one project now: exit 2 = EOL/high CVE, 1 = warnings, 0 = clean
```

Or ask the agent: "is my stack up to date?", "what in my-app has vulnerabilities?", "bump my-app to the newest Node
LTS". The skill tells the agent to recommend first, fix high/critical CVEs before EOL before "behind", change all
declarations together, then build and test.

## Policy

| Level | When |
|---|---|
| error | release line is end-of-life; vulnerability with CVSS ≥ 7 or on CISA KEV; malicious package |
| warn | behind the newest LTS; EOL within 90 days; unmaintained; Node odd line or floating on Current; Node pin older than the line's latest security release; open floor (`>=3.9`) still allowing EOL; vulnerability below 7; Aikido TELEMETRY/PROTESTWARE package |
| ok | newest LTS or supported line; `lts/*` |

Git worktrees, dot-directories, `node_modules`, build output and `exclude` entries are skipped. To silence a whole product,
add it to `"ignore"`. For example, Rust supports only the newest stable, so every older toolchain pin shows as EOL.

## Files

| Path | What |
|---|---|
| `~/.config/stack-watch/config.json` | `roots`, `exclude`, `maxDepth` (4), `notify`, `osv`, `kev`, `epss`, `recommend` (all true), `aikido` (false), `watch`, `ignore` |
| `~/.cache/stack-watch/report.md` | last report |
| `~/.cache/stack-watch/alert.txt` | one-line alert; absent when nothing needs doing |

## Data sources and privacy

The check only reads public data. Here is what each source receives:

| Source | What it receives | Turn off |
|---|---|---|
| endoflife.date, nodejs.org, CISA KEV | nothing: full lists are downloaded | `"kev": false` for KEV |
| osv-scanner → osv.dev (and deps.dev) | package names and versions | `"osv": false` |
| FIRST EPSS | CVE ids only | `"epss": false` |
| Aikido malware lists (opt-in) | nothing: full lists are downloaded and matched locally | off by default; `"aikido": true` to enable |

No source code is sent anywhere. The Aikido data is free and open per Aikido; check its current terms before using it
for commercial work.

## Tests

```sh
node --test stack-watch/tests/run.mjs
```

The tests use fixture release data, fake osv-scanner output and a fixed date, so they need no network. Tested on macOS. The Linux path
(systemd, notify-send) and the Windows path (schtasks, balloon notification) are written but have not been run on those systems.
