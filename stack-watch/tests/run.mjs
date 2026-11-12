// node --test tests/run.mjs — fixture release data + fake osv-scanner output, fixed date, no network.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT = path.join(here, "..", "skills", "stack-watch", "scripts", "stack-watch.mjs");
const FIXTURES = path.join(here, "fixtures", "data");
const DAY = "2026-11-12"; // Node 26 active LTS, 24 maintenance, 20 EOL; .NET 8 EOL 2026-11-10; Python 3.9 EOL
const tmp = (p) => fs.mkdtempSync(path.join(os.tmpdir(), p));

function tree(files) {
  const root = tmp("sw-");
  for (const [f, body] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(root, f)), { recursive: true });
    fs.writeFileSync(path.join(root, f), body);
  }
  return root;
}

// Release data dir with osv.json paths pointing into `root`.
function dataFor(root) {
  const dir = tmp("sw-data-");
  for (const f of fs.readdirSync(FIXTURES))
    fs.writeFileSync(path.join(dir, f), fs.readFileSync(path.join(FIXTURES, f), "utf8").replaceAll("__ROOT__", root));
  return dir;
}

function run(args, { roots = [], home, day = DAY, data } = {}) {
  home ??= tmp("sw-home-");
  const r = spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: "utf8",
    env: { ...process.env, STACK_WATCH_HOME: home, STACK_WATCH_DATA_DIR: data ?? dataFor(roots[0] || "/nowhere"),
      STACK_WATCH_TODAY: day, STACK_WATCH_ROOTS: roots.join(path.delimiter), STACK_WATCH_NO_PROBE: "1" },
  });
  return { ...r, home };
}

const projects = {
  "eol/.nvmrc": "20\n",
  "eol/Dockerfile": "FROM --platform=linux/amd64 node:18-alpine AS build\nFROM mcr.microsoft.com/dotnet/aspnet:8.0\nFROM nginx\n",
  "eol/app.csproj": "<Project><PropertyGroup><TargetFrameworks>net8.0;net10.0</TargetFrameworks></PropertyGroup></Project>\n",
  "eol/.python-version": "3.9.18\n",
  "behind/package.json": JSON.stringify({ engines: { node: ">=22" }, volta: { node: "24.1.0" } }, null, 2),
  "behind/.github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - uses: actions/setup-node@v4\n        with:\n          node-version: [24, 26]\n      - uses: actions/setup-python@v5\n        with:\n          python-version: ${{ matrix.py }}\n",
  "ok/.node-version": "lts/*\n",
  "ok/.tool-versions": "nodejs 26.13.1\npython 3.14.1\n",
  "ok/azure-pipelines.yml": "steps:\n- task: NodeTool@0\n  inputs:\n    versionSpec: '26.x'\n- task: UseDotNet@2\n  inputs:\n    version: '10.0.x'\n",
  "ok/go.mod": "module x\n\ngo 1.27.1\n",
  "pinned/.nvmrc": "v26.13.0\n",
  "floor/pyproject.toml": "[project]\nrequires-python = \">=3.9\"\n",
  "codename/.nvmrc": "lts/iron\n",
  "ignored/node_modules/x/.nvmrc": "14\n",
  ".claude/worktrees/x/.nvmrc": "14\n",
};

test("declarations: runtimes across ecosystems are classified", () => {
  const root = tree(projects);
  const r = run(["scan", root], { roots: [root] });
  const out = r.stdout;
  assert.equal(r.status, 2, r.stderr);
  assert.match(out, /eol\/\.nvmrc:1` \.nvmrc `20` — Node\.js 20 is EOL since 2026-04-30/);
  assert.match(out, /eol\/Dockerfile:1` docker `18` — Node\.js 18 is EOL/);
  assert.match(out, /eol\/Dockerfile:2` docker `8\.0` — Microsoft \.NET 8 is EOL since 2026-11-10/);
  assert.match(out, /eol\/app\.csproj:1` TargetFramework `8\.0` — Microsoft \.NET 8 is EOL/);
  assert.doesNotMatch(out, /TargetFramework `10\.0`/);
  assert.match(out, /eol\/\.python-version:1` \.python-version `3\.9\.18` — Python 3\.9 is EOL/);
  assert.match(out, /codename\/\.nvmrc:1` \.nvmrc `lts\/iron` — Node\.js 20 is EOL/);
  assert.match(out, /behind\/package\.json:\d+` engines\.node `>=22` — Node\.js 22 is behind newest LTS 26/);
  assert.match(out, /behind\/package\.json:\d+` volta\.node `24\.1\.0` — Node\.js 24 is behind/);
  assert.match(out, /ci\.yml:6` github-actions `\[24, 26\]` — Node\.js 24 is behind/);
  assert.match(out, /pinned\/\.nvmrc:1` \.nvmrc `v26\.13\.0` — pinned 26\.13\.0 predates security release 26\.13\.1/);
  assert.match(out, /floor\/pyproject\.toml:2` requires-python `>=3\.9` — Python 3\.9 \(floor\) is EOL/);
  assert.doesNotMatch(out, /`ok\/|worktrees|node_modules|matrix\.py/);
});

test("dependencies: frameworks matched by purl, CVEs grouped per lockfile, worktrees skipped", () => {
  const root = tree(projects);
  const out = run(["scan", root], { roots: [root] }).stdout;
  assert.match(out, /app\/package-lock\.json:1` dependency eslint `9\.39\.5` — ESLint 9 is EOL/);
  assert.match(out, /dependency next `15\.5\.26` — Next\.js 15 /);
  assert.doesNotMatch(out, /dependency react/, "react 19 is current → OK, not listed");
  assert.match(out, /## Vulnerabilities \(2 in 1 lockfiles\)/);
  assert.match(out, /app\/package-lock\.json` — \*\*1 exploited in the wild\*\*, 2 high\/critical, 0 low\/medium/);
  assert.match(out, /next@15\.5\.26 — \[GHSA-2464-fhr4-w9xw\]\(https:\/\/osv\.dev\/vulnerability\/GHSA-2464-fhr4-w9xw\) critical 9\.5, fixed in 16\.4\.1/);
  assert.doesNotMatch(out, /GHSA-dup/);
});

test("intel: KEV escalates and sorts first, EPSS shown, OSV MAL- ids become malicious packages", () => {
  const root = tree(projects);
  const r = run(["scan", root], { roots: [root] });
  const out = r.stdout;
  assert.equal(r.status, 2);
  assert.match(out, /- fast-uri@3\.1\.8 — \[CVE-2026-110725 \/ GHSA-333x-w4r6-6crp\]\([^)]+\) \*\*KEV: exploited in the wild since 2026-11-01, used by ransomware\*\*, low 3\.7, EPSS 42%/);
  assert.ok(out.indexOf("fast-uri@3.1.8") < out.indexOf("next@15.5.26"), "KEV before higher CVSS");
  assert.match(out, /## Malicious packages — remove now \(1\)\n\n- `[^`]+app\/package-lock\.json` flatmap-streamx@0\.1\.1 — MALWARE \(\[OSV MAL-2026-1234\]/);
  assert.doesNotMatch(out, /evil-pkg/, "Aikido is opt-in");
});

test("intel: Aikido malware list when opted in; MALWARE is an error, TELEMETRY a warning", () => {
  const root = tree(projects);
  const home = tmp("sw-home-");
  fs.writeFileSync(path.join(home, "config.json"), JSON.stringify({ aikido: true }));
  run(["check", "--quiet"], { roots: [root], home });
  const report = fs.readFileSync(path.join(home, "report.md"), "utf8");
  assert.match(report, /## Malicious packages — remove now \(3\)/);
  assert.match(report, /evil-pkg@1\.0\.0 — MALWARE \(\[Aikido\]/);
  assert.match(report, /react@19\.3\.1 — TELEMETRY \(\[Aikido\]/);
  assert.match(fs.readFileSync(path.join(home, "alert.txt"), "utf8"), /^Stack watch: 1 vulnerability exploited in the wild \(CISA KEV\); 2 MALICIOUS packages installed;/);
});

test("recommendations: GitHub repos get a malware-alerts link, others don't; can be turned off", () => {
  const root = tree({
    "gh/.git/config": '[remote "origin"]\n\turl = git@github.com:acme/widget.git\n',
    "ado/.git/config": '[remote "origin"]\n\turl = https://dev.azure.com/acme/p/_git/r\n',
    "gh/.nvmrc": "lts/*\n",
  });
  const out = run(["scan", root], { roots: [root] }).stdout;
  assert.match(out, /## Recommendations\n\n- These repos are on GitHub\. Turn on \*\*Dependabot alerts and malware alerts\*\*/);
  assert.match(out, /  - \[acme\/widget\]\(https:\/\/github\.com\/acme\/widget\/settings\/security_analysis\)/);
  assert.doesNotMatch(out, /dev\.azure/);
  const home = tmp("sw-home-");
  fs.writeFileSync(path.join(home, "config.json"), JSON.stringify({ recommend: false }));
  assert.doesNotMatch(run(["scan", root], { roots: [root], home }).stdout, /## Recommendations/);
});

test("a failed osv-scanner run leaves no stamp, keeps the previous report and alert, and retries", () => {
  const root = tree({ "a/.nvmrc": "lts/*\n" });
  const home = tmp("sw-home-");
  const data = dataFor(root);
  fs.rmSync(path.join(data, "osv.json"));
  const bin = tmp("sw-bin-");
  fs.writeFileSync(path.join(bin, "osv-scanner"), "#!/bin/sh\necho boom >&2\nexit 127\n", { mode: 0o755 });
  fs.writeFileSync(path.join(home, "report.md"), "previous report\n");
  fs.writeFileSync(path.join(home, "alert.txt"), "previous alert\n");
  const r = spawnSync(process.execPath, [SCRIPT, "check", "--quiet"], { encoding: "utf8", env: { ...process.env,
    PATH: `${bin}${path.delimiter}${process.env.PATH}`, STACK_WATCH_HOME: home, STACK_WATCH_DATA_DIR: data,
    STACK_WATCH_TODAY: DAY, STACK_WATCH_ROOTS: root, STACK_WATCH_NO_PROBE: "1" } });
  assert.match(r.stderr, /osv-scanner failed: boom/);
  assert.ok(!fs.existsSync(path.join(home, "last-run")), "no stamp → next hourly run retries");
  assert.equal(fs.readFileSync(path.join(home, "report.md"), "utf8"), "previous report\n");
  assert.equal(fs.readFileSync(path.join(home, "alert.txt"), "utf8"), "previous alert\n");
});

test("git submodules are scanned; worktrees are not", () => {
  const root = tree({
    "app/.git/config": "",
    "app/libs/sub/.git": "gitdir: ../../.git/modules/libs/sub\n",
    "app/libs/sub/.nvmrc": "20\n",
    "app/libs/worktrees/w/.git": "gitdir: ../../../.git/modules/libs/worktrees/w\n",
    "app/libs/worktrees/w/.nvmrc": "21\n",
    "app-wt/.git": "gitdir: /x/app/.git/worktrees/app-wt\n",
    "app-wt/.nvmrc": "18\n",
  });
  const out = run(["scan", root], { roots: [root] }).stdout;
  assert.match(out, /app\/libs\/sub\/\.nvmrc:1` \.nvmrc `20` — Node\.js 20 is EOL/);
  assert.match(out, /libs\/worktrees\/w\/\.nvmrc:1` \.nvmrc `21`/, "submodule under a 'worktrees' path");
  assert.doesNotMatch(out, /app-wt/);
});

test("advisories: Node security post is reported, and alerted only once", () => {
  const root = tree({ "a/.nvmrc": "lts/*\n" });
  const home = tmp("sw-home-");
  const data = dataFor(root);
  run(["check", "--quiet"], { roots: [root], home, data });
  assert.match(fs.readFileSync(path.join(home, "report.md"), "utf8"), /## Advisories\n\n- 2026-11-11 \[.*Security Releases\]\(https:\/\/nodejs\.org\/en\/blog\/vulnerability\/november-2026-security-releases\)/);
  assert.match(fs.readFileSync(path.join(home, "alert.txt"), "utf8"), /november-2026-security-releases/);
  run(["check", "--quiet"], { roots: [root], home, data, day: "2026-11-13" });
  assert.doesNotMatch(fs.readFileSync(path.join(home, "alert.txt"), "utf8"), /november-2026-security-releases/);
});

test("check runs once per day and catches up the next day", () => {
  const root = tree(projects);
  const first = run(["check", "--quiet"], { roots: [root] });
  assert.equal(first.status, 0, first.stderr);
  const report = path.join(first.home, "report.md");
  assert.match(fs.readFileSync(path.join(first.home, "alert.txt"), "utf8"), /projects: \d+ EOL, \d+ behind; vulnerabilities: 2 high\/critical, 0 other/);
  fs.rmSync(report);
  run(["check", "--quiet"], { roots: [root], home: first.home });
  assert.ok(!fs.existsSync(report), "second run the same day is a no-op");
  run(["check", "--quiet"], { roots: [root], home: first.home, day: "2026-11-13" });
  assert.ok(fs.existsSync(report), "next day runs again");
});

test("new release line on a watched product is announced", () => {
  const root = tree({ "a/.nvmrc": "lts/*\n" });
  const home = tmp("sw-home-");
  fs.writeFileSync(path.join(home, "config.json"), JSON.stringify({ watch: ["kubernetes"] }));
  fs.writeFileSync(path.join(home, "state.json"), JSON.stringify({ lines: { nodejs: "24", kubernetes: "1.30" }, lastAdvisory: "2026-12-01" }));
  run(["check", "--quiet"], { roots: [root], home });
  const alert = fs.readFileSync(path.join(home, "alert.txt"), "utf8");
  assert.match(alert, /new release line Node\.js 26/);
  assert.match(alert, /new release line Kubernetes \d/);
  assert.match(fs.readFileSync(path.join(home, "report.md"), "utf8"), /## Watched\n\n- Kubernetes: /);
});

test("status --brief prints only a fresh alert", () => {
  const home = tmp("sw-home-");
  assert.equal(run(["status", "--brief"], { home }).stdout, "");
  fs.writeFileSync(path.join(home, "alert.txt"), "Stack watch: x\n");
  assert.equal(run(["status", "--brief"], { home }).stdout, "Stack watch: x\n");
  const old = new Date(Date.now() - 8 * 86400000);
  fs.utimesSync(path.join(home, "alert.txt"), old, old);
  assert.equal(run(["status", "--brief"], { home }).stdout, "");
});

test("unknown command exits 64", () => {
  assert.equal(run(["nope"]).status, 64);
});
