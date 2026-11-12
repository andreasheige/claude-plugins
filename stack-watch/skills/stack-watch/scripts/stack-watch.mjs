#!/usr/bin/env node
// stack-watch: daily check of the runtimes, frameworks and dependencies your projects use.
//   - EOL / behind-LTS for any product endoflife.date tracks (runtimes: Node, .NET, Python, Go, Rust, Java;
//     frameworks/packages matched dynamically by purl: React, Next.js, Angular, Vue, ... whatever it lists)
//   - known vulnerabilities in lockfiles (npm, NuGet, PyPI, Go, crates, Maven, ...) via osv-scanner, if installed
//   - Node.js security advisories (nodejs.org vulnerability feed) and security releases
// Zero dependencies; macOS, Linux and Windows.
//
//   stack-watch.mjs check [--force] [--notify] [--quiet]   once per day (stamp file); writes report + alert
//   stack-watch.mjs scan [dir...]                          scan now with cached release data; exit 2 EOL/high CVE, 1 warn
//   stack-watch.mjs status [--brief]                       last report / one-line alert (no network)
//   stack-watch.mjs install | uninstall                    hourly schedule (launchd / systemd --user / schtasks)
//
// Config <config>/config.json:
//   {"roots": ["~/Dev"], "exclude": ["_archive"], "maxDepth": 4, "notify": true, "osv": true,
//    "watch": ["kubernetes", "postgresql"], "ignore": ["rust"]}
// Env: STACK_WATCH_ROOTS (path list), STACK_WATCH_HOME (state+config dir, tests), STACK_WATCH_DATA_DIR (read release
//      data and osv.json from disk, tests), STACK_WATCH_TODAY (YYYY-MM-DD), STACK_WATCH_NO_PROBE=1 (skip local probes)

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const URLS = {
  eol: "https://endoflife.date/api/v1/products/full",
  nodeIndex: "https://nodejs.org/dist/index.json",
  nodeVuln: "https://nodejs.org/en/feed/vulnerability.xml",
};
const SKIP_DIRS = new Set(["node_modules", ".git", "dist", "build", "out", ".next", ".nuxt", ".turbo", ".cache",
  "vendor", "coverage", "target", ".venv", "venv", "__pycache__", "graphify-out", "bower_components", "bin", "obj"]);
const SOON_DAYS = 90, ADVISORY_DAYS = 30;
const HOME = os.homedir();
const IS_WIN = process.platform === "win32";
const SCRIPT = fileURLToPath(import.meta.url);
const ENV = (k) => process.env[`STACK_WATCH_${k}`];

const STATE_DIR = ENV("HOME")
  || (IS_WIN ? path.join(process.env.LOCALAPPDATA || HOME, "stack-watch")
    : path.join(process.env.XDG_CACHE_HOME || path.join(HOME, ".cache"), "stack-watch"));
const CONFIG_FILE = ENV("HOME") ? path.join(STATE_DIR, "config.json")
  : IS_WIN ? path.join(process.env.APPDATA || HOME, "stack-watch", "config.json")
    : path.join(process.env.XDG_CONFIG_HOME || path.join(HOME, ".config"), "stack-watch", "config.json");
const st = (f) => path.join(STATE_DIR, f);
const P = { last: st("last-run"), state: st("state.json"), report: st("report.md"), alert: st("alert.txt"),
  eol: st("eol.json"), nodeIndex: st("node-index.json"), nodeVuln: st("node-vuln.xml"), osv: st("osv.json") };

const today = () => ENV("TODAY") || new Date().toISOString().slice(0, 10);
const expand = (p) => p.replace(/^~(?=$|[\\/])/, HOME);
const readJson = (f, dflt) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch { return dflt; } };
const readText = (f) => { try { return fs.readFileSync(f, "utf8"); } catch { return null; } };
const write = (f, s) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, s); };
const daysBetween = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000);
const has = (cmd) => spawnSync(IS_WIN ? "where" : "which", [cmd], { env: probeEnv() }).status === 0;

function config() {
  const c = readJson(CONFIG_FILE, {});
  const envRoots = ENV("ROOTS")?.split(path.delimiter).filter(Boolean);
  return {
    roots: (envRoots || c.roots || []).map(expand),
    exclude: new Set(c.exclude || []),
    maxDepth: c.maxDepth ?? 4,
    notify: c.notify ?? true,
    osv: c.osv ?? true,
    kev: c.kev ?? true,           // CISA Known Exploited Vulnerabilities: public domain, no key
    epss: c.epss ?? true,         // FIRST exploit probability: sends CVE ids only
    aikido: c.aikido ?? false,    // Aikido malware lists: opt-in, check its licence for company use
    recommend: c.recommend ?? true, // GitHub malware alerts / Safe Chain hints in the report
    watch: c.watch || [],
    ignore: new Set(c.ignore || []),
  };
}

// ---------- release data ----------

async function fetchText(url) {
  const res = await fetch(url, { signal: AbortSignal.timeout(30000), headers: { "user-agent": "stack-watch" } });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.text();
}

async function loadData({ offline }) {
  const dir = ENV("DATA_DIR");
  const files = dir ? { eol: path.join(dir, "eol.json"), nodeIndex: path.join(dir, "node-index.json"),
    nodeVuln: path.join(dir, "node-vuln.xml") } : { eol: P.eol, nodeIndex: P.nodeIndex, nodeVuln: P.nodeVuln };
  if (!dir && (!offline || !fs.existsSync(P.eol))) {
    const [eol, idx, vuln] = await Promise.all([fetchText(URLS.eol), fetchText(URLS.nodeIndex),
      fetchText(URLS.nodeVuln).catch(() => "")]);
    JSON.parse(eol); JSON.parse(idx); // refuse to cache garbage
    write(P.eol, eol); write(P.nodeIndex, idx); if (vuln) write(P.nodeVuln, vuln);
  }
  return {
    products: readJson(files.eol, {}).result || [],
    nodeIndex: readJson(files.nodeIndex, []),
    nodeVuln: readText(files.nodeVuln) || "",
  };
}

// Index products by name and by purl (without version/qualifiers) so any package or image maps dynamically.
const DOCKER_ALIAS = [ // images endoflife.date has no purl for
  [/^mcr\.microsoft\.com\/dotnet\//, "dotnet"], [/^(library\/)?(eclipse-temurin|openjdk)$/, "eclipse-temurin"],
  [/^(library\/)?amazoncorretto$/, "amazon-corretto"], [/^(library\/)?rust$/, "rust"], [/^(library\/)?python$/, "python"],
  [/^(library\/)?golang$/, "go"], [/^(library\/)?node$/, "nodejs"],
];
function indexProducts(products, day) {
  const byName = new Map(), byPurl = new Map();
  for (const p of products) {
    for (const r of p.releases || []) r.eol = r.eolFrom ? r.eolFrom <= day : !!r.isEol;
    byName.set(p.name, p);
    for (const i of p.identifiers || [])
      if (i.type === "purl") byPurl.set(i.id.toLowerCase().replace(/^pkg:docker\/library\//, "pkg:docker/"), p);
  }
  return { byName, byPurl };
}

function dockerProduct(image, idx) {
  const img = image.toLowerCase().replace(/^docker\.io\//, "");
  const p = idx.byPurl.get(`pkg:docker/${img.replace(/^library\//, "")}`);
  if (p) return p;
  const alias = DOCKER_ALIAS.find(([re]) => re.test(img));
  return alias ? idx.byName.get(alias[1]) : null;
}

const cmpVer = (a, b) => {
  const x = String(a).replace(/^v/, "").split(/[.+-]/).map((n) => parseInt(n, 10) || 0);
  const y = String(b).replace(/^v/, "").split(/[.+-]/).map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(x.length, y.length, 3); i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) - (y[i] || 0);
  return 0;
};

function cycleFor(product, ver) {
  let v = String(ver).replace(/^v/, "");
  if (/temurin|corretto|openjdk|jdk/.test(product.name)) v = v.replace(/^1\.(\d+)/, "$1"); // java 1.8 → 8
  let best = null;
  for (const r of product.releases || [])
    if ((v === r.name || v.startsWith(r.name + ".")) && (!best || r.name.length > best.name.length)) best = r;
  return best;
}

function newestLts(product, day) {
  return (product.releases || []).filter((r) => r.isLts && !r.eol && (!r.ltsFrom || r.ltsFrom <= day))
    .sort((a, b) => (b.releaseDate || "").localeCompare(a.releaseDate || ""))[0] || null;
}

// ---------- version specs ----------

// → { versions: [...], exact: "x.y.z"|null, floating: "lts"|"current"|null } or null if unusable
export function parseSpec(raw, product, ctx = {}) {
  let s = String(raw).trim().replace(/^["']|["']$/g, "").replace(/\s+#.*$/, "");
  if (!s || s.includes("${{") || s.includes("$(")) return null;
  if (/^(lts\/\*|lts|lts-\w+|stable)$/i.test(s)) return { versions: [], exact: null, floating: "lts" };
  if (/^(node|latest|current|current-\w+|nightly|beta)$/i.test(s)) return { versions: [], exact: null, floating: "current" };
  const code = s.match(/^lts\/([a-z]+)$/i);
  if (code && ctx.nodeCodenames) {
    const major = ctx.nodeCodenames.get(code[1].toLowerCase());
    return major ? { versions: [String(major)], exact: null, floating: null } : null;
  }
  const exact = s.match(/^v?(\d+\.\d+\.\d+)$/);
  s = s.replace(/<\s*=?\s*v?[\d.x*]+/g, " "); // upper bounds don't constrain the floor
  const versions = [...s.matchAll(/(?<![\w.])v?(\d{1,4}(?:\.\d+){0,2})(?![\w])/g)].map((m) => m[1])
    .filter((v) => product && cycleFor(product, v));
  if (!versions.length) return null;
  return { versions: [...new Set(versions)], exact: exact ? exact[1] : null, floating: null };
}

const RANK = { ok: 0, info: 0, warn: 1, error: 2 };

export function judge(spec, product, day, ctx = {}) {
  const label = product.label || product.name;
  const lts = newestLts(product, day);
  if (spec.floating === "lts") return { level: "ok", msg: "floating LTS" };
  if (spec.floating === "current") return { level: lts ? "warn" : "ok", msg: lts ? "floats on Current (non-LTS)" : "floating" };
  let worst = { level: "ok", msg: "" };
  const bump = (level, msg) => { if (RANK[level] > RANK[worst.level]) worst = { level, msg }; };
  for (const v of spec.versions) {
    const c = cycleFor(product, v);
    if (!c) continue;
    if (c.eol) bump("error", `${label} ${c.name} is EOL since ${c.eolFrom}`);
    else if (c.eolFrom && daysBetween(day, c.eolFrom) <= SOON_DAYS) bump("warn", `${label} ${c.name} reaches EOL ${c.eolFrom}`);
    else if (product.name === "nodejs" && !c.isLts && lts && c.releaseDate > lts.releaseDate)
      bump("warn", `${label} ${c.name} is not an LTS line`);
    else if (lts && (c.releaseDate || "") < (lts.releaseDate || "")) bump("warn", `${label} ${c.name} is behind newest LTS ${lts.name}`);
    else if (c.isMaintained === false) bump("warn", `${label} ${c.name} is no longer maintained`);
  }
  if (spec.exact && worst.level === "ok" && product.name === "nodejs" && ctx.nodeSecurity) {
    const sec = ctx.nodeSecurity.get(Number(spec.exact.split(".")[0]));
    if (sec && cmpVer(spec.exact, sec) < 0) bump("warn", `pinned ${spec.exact} predates security release ${sec}`);
  }
  return worst;
}

// ---------- project scan: version declarations ----------

// A linked git worktree duplicates its main checkout; skip it. Submodules also have a `.git` file
// ("gitdir: ../.git/modules/x") but are real code. A linked worktree's gitdir is always <repo>/.git/worktrees/<name>.
const isWorktree = (dir) =>
  /^gitdir:\s*(?:.*[\\/])?\.git[\\/]worktrees[\\/][^\\/\s]+[\\/]?\s*$/m.test(readText(path.join(dir, ".git")) || "");

function* walk(dir, depth, cfg) {
  let ents;
  try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
  if (depth > 0 && ents.some((e) => e.name === ".git" && e.isFile()) && isWorktree(dir)) return;
  yield [dir, ents];
  if (depth >= cfg.maxDepth) return;
  for (const e of ents)
    if (e.isDirectory() && !e.isSymbolicLink() && !SKIP_DIRS.has(e.name) && !cfg.exclude.has(e.name)
      && !(e.name.startsWith(".") && e.name !== ".github"))
      yield* walk(path.join(dir, e.name), depth + 1, cfg);
}

function lineHits(file, re, max = Infinity) {
  const text = readText(file);
  if (text == null) return [];
  const out = [];
  text.split(/\r?\n/).forEach((ln, i) => { const m = ln.match(re); if (m && out.length < max) out.push({ line: i + 1, value: m[1] }); });
  return out;
}

const TOOL = { nodejs: "nodejs", node: "nodejs", python: "python", golang: "go", go: "go", rust: "rust",
  java: "eclipse-temurin", dotnet: "dotnet", "dotnet-core": "dotnet" };
const GHA = { "node-version": "nodejs", "python-version": "python", "go-version": "go", "dotnet-version": "dotnet",
  "java-version": "eclipse-temurin" };
const AZURE = [[/NodeTool@|UseNode@/, "nodejs"], [/UsePythonVersion@/, "python"], [/UseDotNet@/, "dotnet"],
  [/GoTool@/, "go"], [/JavaToolInstaller@/, "eclipse-temurin"]];

// Every runtime declaration in one directory: [{file, line, source, product, value, floor?}]
export function declarationsIn(dir, ents, idx) {
  const names = new Set(ents.map((e) => e.name));
  const out = [];
  const add = (f, source, product, hits, extra = {}) =>
    hits.forEach((h) => out.push({ file: path.join(dir, f), source, product: h.product || product, line: h.line, value: h.value, ...extra }));
  const at = (f) => path.join(dir, f);
  const one = (f) => lineHits(at(f), /^\s*(\S+)\s*$/, 1);

  for (const f of [".nvmrc", ".node-version"]) if (names.has(f)) add(f, f, "nodejs", one(f));
  if (names.has(".python-version")) add(".python-version", ".python-version", "python", one(".python-version"));
  if (names.has(".java-version")) add(".java-version", ".java-version", "eclipse-temurin", one(".java-version"));
  if (names.has("runtime.txt")) add("runtime.txt", "runtime.txt", "python", lineHits(at("runtime.txt"), /^\s*python-(\S+)/));
  if (names.has(".sdkmanrc")) add(".sdkmanrc", "sdkman", "eclipse-temurin", lineHits(at(".sdkmanrc"), /^\s*java\s*=\s*([\d.]+)/));
  if (names.has(".tool-versions"))
    add(".tool-versions", "asdf", null, lineHits(at(".tool-versions"), /^\s*(\S+\s+\S+)/)
      .map((h) => { const [t, v] = h.value.split(/\s+/); return { ...h, product: TOOL[t], value: v.replace(/^[a-z]+-/, "") }; })
      .filter((h) => h.product));
  for (const f of ["mise.toml", ".mise.toml"])
    if (names.has(f))
      add(f, "mise", null, lineHits(at(f), /^\s*(\w[\w-]*\s*=\s*["']?[^"'\s]+)/)
        .map((h) => { const [t, v] = h.value.split(/\s*=\s*["']?/); return { ...h, product: TOOL[t], value: v }; })
        .filter((h) => h.product));
  if (names.has("package.json")) {
    const pj = readJson(at("package.json"), {});
    const src = (readText(at("package.json")) || "").split(/\r?\n/);
    const lineOf = (re) => src.findIndex((l) => re.test(l)) + 1 || 1;
    if (typeof pj.engines?.node === "string")
      out.push({ file: at("package.json"), source: "engines.node", product: "nodejs", line: lineOf(/"node"\s*:/), value: pj.engines.node, floor: true });
    if (typeof pj.volta?.node === "string")
      out.push({ file: at("package.json"), source: "volta.node", product: "nodejs", line: lineOf(/"volta"/), value: pj.volta.node });
  }
  if (names.has("pyproject.toml"))
    add("pyproject.toml", "requires-python", "python",
      lineHits(at("pyproject.toml"), /^\s*(?:requires-python|python)\s*=\s*["']([^"']+)/), { floor: true });
  if (names.has("global.json")) {
    const v = readJson(at("global.json"), {}).sdk?.version;
    if (typeof v === "string") add("global.json", "global.json sdk", "dotnet", lineHits(at("global.json"), /"version"\s*:\s*"([^"]+)"/, 1));
  }
  if (names.has("go.mod")) {
    add("go.mod", "go.mod", "go", lineHits(at("go.mod"), /^go\s+(\d[\d.]*)/));
    add("go.mod", "go.mod toolchain", "go", lineHits(at("go.mod"), /^toolchain\s+go(\d[\d.]*)/));
  }
  if (names.has("rust-toolchain")) add("rust-toolchain", "rust-toolchain", "rust", one("rust-toolchain"));
  if (names.has("rust-toolchain.toml"))
    add("rust-toolchain.toml", "rust-toolchain", "rust", lineHits(at("rust-toolchain.toml"), /^\s*channel\s*=\s*["']([^"']+)/));
  if (names.has("Cargo.toml"))
    add("Cargo.toml", "rust-version", "rust", lineHits(at("Cargo.toml"), /^\s*rust-version\s*=\s*["']([^"']+)/), { floor: true });
  if (names.has("pom.xml"))
    add("pom.xml", "maven", "eclipse-temurin",
      lineHits(at("pom.xml"), /<(?:maven\.compiler\.release|maven\.compiler\.source|java\.version|release)>\s*([\d.]+)\s*</));
  for (const f of ["build.gradle", "build.gradle.kts"])
    if (names.has(f))
      add(f, "gradle", "eclipse-temurin",
        lineHits(at(f), /(?:JavaLanguageVersion\.of\(|JavaVersion\.VERSION_|sourceCompatibility\s*=\s*['"]?)(\d[\d._]*)/)
          .map((h) => ({ ...h, value: h.value.replace(/_/g, ".") })));

  for (const e of ents) {
    if (!e.isFile()) continue;
    if (/\.(cs|fs|vb)proj$|^Directory\.Build\.props$/i.test(e.name))
      add(e.name, "TargetFramework", "dotnet", lineHits(at(e.name), /<TargetFrameworks?>([^<]+)</)
        .flatMap((h) => h.value.split(";").map((t) => t.trim().match(/^net(?:coreapp)?(\d+\.\d+)/)).filter(Boolean)
          .map((m) => ({ ...h, value: m[1] }))));
    if (/^(Dockerfile|Containerfile)(\..+)?$|\.Dockerfile$/i.test(e.name))
      add(e.name, "docker", null, lineHits(at(e.name), /^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)/i)
        .map((h) => {
          const [, image, tag = "latest"] = h.value.match(/^([^:@\s]+)(?::([^@\s]+))?/) || [];
          const p = image && dockerProduct(image, idx);
          if (!p) return null;
          const v = tag.match(/^v?(\d+(?:\.\d+){0,2})/)?.[1]
            ?? (/^(lts|.*-lts)/i.test(tag) ? "lts" : /^(current|latest|alpine|slim|bookworm|bullseye|bookworm-slim)/i.test(tag) ? "current" : null);
          return v ? { ...h, product: p.name, value: v } : null;
        }).filter(Boolean));
    if (/^azure-pipelines.*\.ya?ml$/i.test(e.name)) {
      let current = null;
      const hits = [];
      (readText(at(e.name)) || "").split(/\r?\n/).forEach((ln, i) => {
        const task = AZURE.find(([re]) => re.test(ln));
        if (task) current = task[1];
        const m = ln.match(/^\s*(?:versionSpec|version)\s*:\s*["']?([^"'#\s]+)/);
        if (m && current) hits.push({ line: i + 1, value: m[1], product: current });
      });
      add(e.name, "azure-pipelines", null, hits);
    }
  }
  if (path.basename(dir) === "workflows" && path.basename(path.dirname(dir)) === ".github")
    for (const e of ents)
      if (e.isFile() && /\.ya?ml$/.test(e.name))
        add(e.name, "github-actions", null, lineHits(at(e.name),
          /^\s*((?:node|python|go|dotnet|java)-version\s*:\s*\[?[^\[{#]*\d[^#]*?)\s*$/)
          .map((h) => { const [k, v] = h.value.split(/\s*:\s*/); return { ...h, product: GHA[k], value: v }; })
          .filter((h) => !/\$\{\{/.test(h.value)));
  return out.filter((d) => d.product);
}

function scanDeclarations(roots, cfg, data) {
  const findings = [];
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    for (const [dir, ents] of walk(root, 0, cfg)) {
      if (data.github && ents.some((e) => e.name === ".git" && e.isDirectory())) {
        const repo = githubRepo(dir);
        if (repo) data.github.set(repo.toLowerCase(), repo);
      }
      for (const d of declarationsIn(dir, ents, data.idx)) {
        if (cfg.ignore.has(d.product)) continue;
        const product = data.idx.byName.get(d.product);
        if (!product) continue;
        const spec = parseSpec(d.value, product, data);
        if (!spec) continue;
        let j = judge(spec, product, data.day, data);
        // An open-ended floor (engines ">=20", requires-python ">=3.9") doesn't run that version; it only allows it.
        if (j.level === "error" && d.floor && !/</.test(d.value) && /^\s*(>=?|\^|~)/.test(d.value))
          j = { level: "warn", msg: j.msg.replace(/ is EOL/, " (floor) is EOL") };
        findings.push({ ...d, root, ...j });
      }
    }
  }
  return findings;
}

// ---------- dependencies: osv-scanner ----------

function osvRun(roots, cfg) {
  const fake = ENV("DATA_DIR") && path.join(ENV("DATA_DIR"), "osv.json");
  if (fake && fs.existsSync(fake)) return { json: readJson(fake, null) };
  if (!cfg.osv) return { json: null };
  if (!has("osv-scanner")) return { json: null, missing: true };
  const existing = roots.filter((r) => fs.existsSync(r));
  if (!existing.length) return { json: null };
  fs.rmSync(P.osv, { force: true });
  const excl = [...cfg.exclude].flatMap((x) => ["--x-exclude", x]);
  const r = spawnSync("osv-scanner", ["scan", "source", "-r", "--all-packages", "--allow-no-lockfiles", "--format", "json",
    "--verbosity", "error", "--output-file", P.osv, ...excl, ...existing],
  { env: probeEnv(), encoding: "utf8", timeout: 20 * 60000 });
  const json = readJson(P.osv, null);
  return json ? { json } : { json: null, error: (r.stderr || r.error?.message || `exit ${r.status}`).trim().slice(0, 300) };
}

const sevName = (s) => s >= 9 ? "critical" : s >= 7 ? "high" : s >= 4 ? "medium" : s > 0 ? "low" : "unrated";

function fixedFor(vulns, id, name) {
  const v = vulns.find((x) => x.id === id);
  const fixes = (v?.affected || []).filter((a) => !a.package || a.package.name === name)
    .flatMap((a) => (a.ranges || []).flatMap((r) => r.events || [])).map((e) => e.fixed).filter(Boolean);
  return fixes.sort(cmpVer).pop() || null;
}

export function analyseOsv(json, data, cfg, day, roots = []) {
  const vulns = [], deps = [], packages = [];
  const seen = new Set();
  for (const res of json?.results || []) {
    const file = res.source?.path || "";
    const root = roots.find((r) => file.startsWith(r + path.sep));
    const segs = path.relative(root || path.dirname(file), file).split(/[\\/]/).slice(0, -1);
    if (segs.some((seg) => (SKIP_DIRS.has(seg) && seg !== "vendor") || cfg.exclude.has(seg) || seg.startsWith(".")))
      continue;
    if (root && segs.some((_, i) => isWorktree(path.join(root, ...segs.slice(0, i + 1))))) continue;
    for (const p of res.packages || []) {
      const pkg = p.package || {};
      if (pkg.name && pkg.version) packages.push({ file, name: pkg.name, version: pkg.version, ecosystem: pkg.ecosystem });
      for (const g of p.groups || []) {
        const sev = Number(g.max_severity) || 0;
        const id = g.ids?.[0];
        vulns.push({ file, pkg: pkg.name, version: pkg.version, ecosystem: pkg.ecosystem, id,
          cve: (g.aliases || []).find((a) => /^CVE-/.test(a)) || null, sev, level: sev >= 7 ? "error" : "warn",
          fixed: fixedFor(p.vulnerabilities || [], id, pkg.name),
          summary: (p.vulnerabilities || []).find((v) => v.id === id)?.summary || "" });
      }
      const base = (pkg.purl || "").split("?")[0].replace(/@[^@/]*$/, "").toLowerCase();
      const product = base && data.idx.byPurl.get(base);
      if (!product || cfg.ignore.has(product.name) || !pkg.version) continue;
      const key = `${file}|${product.name}|${cycleFor(product, pkg.version)?.name}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const j = judge({ versions: [pkg.version], exact: null, floating: null }, product, day, data);
      deps.push({ file, root: root || path.dirname(file), source: `dependency ${pkg.name}`, product: product.name, line: 1,
        value: pkg.version, ...j });
    }
  }
  vulns.sort((a, b) => b.sev - a.sev);
  return { vulns, deps, packages };
}

// ---------- local runtimes ----------

function probeEnv() {
  const extra = IS_WIN ? [] : ["/opt/homebrew/bin", "/opt/homebrew/opt/rustup/bin", "/usr/local/bin", "/usr/local/go/bin", path.join(HOME, ".dotnet"),
    path.join(HOME, ".cargo", "bin"), path.join(HOME, "go", "bin")];
  return { ...process.env, PATH: [process.env.PATH, ...extra].filter(Boolean).join(path.delimiter) };
}

const PROBES = [
  ["dotnet", ["dotnet", "--version"], /(\d+\.\d+\.\d+)/],
  ["python", ["python3", "--version"], /Python (\d+\.\d+\.\d+)/],
  ["go", ["go", "version"], /go(\d+\.\d+(?:\.\d+)?)/],
  ["rust", ["rustc", "--version"], /rustc (\d+\.\d+\.\d+)/],
  ["eclipse-temurin", ["java", "-version"], /version "([\d.]+)/],
];

function localRuntimes(data) {
  const found = [["nodejs", process.version.slice(1)]];
  if (!ENV("NO_PROBE"))
    for (const [product, [cmd, ...args], re] of PROBES) {
      const r = spawnSync(cmd, args, { encoding: "utf8", timeout: 5000, env: probeEnv() });
      const m = `${r.stdout || ""}${r.stderr || ""}`.match(re);
      if (r.status === 0 && m) found.push([product, m[1]]);
    }
  const out = [];
  for (const [name, version] of found) {
    const product = data.idx.byName.get(name);
    if (!product || data.cfg.ignore.has(name)) continue;
    const c = cycleFor(product, version);
    const j = judge({ versions: [version], exact: null, floating: null }, product, data.day, data);
    const notes = j.level !== "ok" ? [j] : [];
    if (name === "nodejs") {
      const sec = data.nodeSecurity.get(Number(version.split(".")[0]));
      if (sec && cmpVer(version, sec) < 0) notes.push({ level: "warn", msg: `security release v${sec.replace(/^v/, "")} available`,
        link: data.advisories[0]?.link });
    }
    if (c?.latest?.name && cmpVer(version, c.latest.name) < 0 && !notes.some((n) => /security/.test(n.msg)))
      notes.push({ level: "info", msg: `patch ${c.latest.name} available`, link: c.latest.link });
    out.push({ product, version, notes });
  }
  return out;
}

function bumpHint(product, line) {
  if (product !== "nodejs") return null;
  if (process.env.NVM_DIR || fs.existsSync(path.join(HOME, ".nvm"))) return `nvm install ${line} && nvm alias default ${line}`;
  if (fs.existsSync(path.join(HOME, ".volta"))) return `volta install node@${line}`;
  if (has("fnm")) return `fnm install ${line} && fnm default ${line}`;
  if (has("mise")) return `mise use -g node@${line}`;
  return null;
}

// ---------- Node specifics: security releases and advisories ----------

function nodeContext(nodeIndex, nodeVuln, day) {
  const nodeSecurity = new Map(), nodeCodenames = new Map();
  for (const r of nodeIndex) {
    if (/-/.test(r.version)) continue;
    const m = Number(r.version.slice(1).split(".")[0]);
    if (r.security && !nodeSecurity.has(m)) nodeSecurity.set(m, r.version.slice(1));
    if (r.lts && !nodeCodenames.has(String(r.lts).toLowerCase())) nodeCodenames.set(String(r.lts).toLowerCase(), m);
  }
  const advisories = [...nodeVuln.matchAll(/<item>([\s\S]*?)<\/item>/g)].map(([, it]) => ({
    title: (it.match(/<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/title>/) || [])[1]?.trim(),
    link: (it.match(/<link>([^<]+)<\/link>/) || [])[1]?.trim(),
    date: (() => { const d = Date.parse((it.match(/<pubDate>([^<]+)<\/pubDate>/) || [])[1]); return isNaN(d) ? null : new Date(d).toISOString().slice(0, 10); })(),
  })).filter((a) => a.title && /^https:\/\/nodejs\.org\//.test(a.link || "") && a.date && daysBetween(a.date, day) <= ADVISORY_DAYS
    && daysBetween(a.date, day) >= 0);
  return { nodeSecurity, nodeCodenames, advisories };
}

// ---------- threat intel: CISA KEV, FIRST EPSS, Aikido malware lists ----------

const INTEL = {
  kev: "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
  epss: "https://api.first.org/data/v1/epss",
  aikido: "https://malware-list.aikido.dev/",
};
const AIKIDO_LIST = { npm: "malware_predictions.json", PyPI: "malware_pypi.json", NuGet: "malware_nuget.json",
  Maven: "malware_maven.json", "crates.io": "malware_cargo.json", Go: "malware_golang.json", Packagist: "malware_packagist.json" };

// Online: download (falling back to the cache on failure). Offline: cache, downloading only if there is none.
async function cachedJson(name, url, online) {
  const dir = ENV("DATA_DIR");
  if (dir) return readJson(path.join(dir, name), null);
  const file = st(name);
  if (!online && fs.existsSync(file)) return readJson(file, null);
  try { const t = await fetchText(url); JSON.parse(t); write(file, t); } catch { /* keep the cached copy */ }
  return readJson(file, null);
}

async function epssScores(cves, online) {
  if (ENV("DATA_DIR")) return readJson(path.join(ENV("DATA_DIR"), "epss.json"), {});
  const file = st("epss.json");
  const cache = readJson(file, {});
  const day = today();
  const todo = online ? cves.filter((c) => cache[c]?.day !== day) : cves.filter((c) => !cache[c]);
  for (let i = 0; i < todo.length; i += 100) {
    try {
      const j = JSON.parse(await fetchText(`${INTEL.epss}?cve=${todo.slice(i, i + 100).join(",")}`));
      for (const d of j.data || []) cache[d.cve] = { epss: Number(d.epss), day };
    } catch { break; }
  }
  write(file, JSON.stringify(cache));
  return Object.fromEntries(Object.entries(cache).map(([k, v]) => [k, typeof v === "number" ? v : v.epss]));
}

// Adds kev/epss to vulns, moves malicious-package findings into `malware`, and escalates both to error.
export async function enrich({ vulns, packages }, cfg, online) {
  const malware = [];
  for (const v of vulns.filter((x) => /^MAL-/.test(x.id)))
    malware.push({ file: v.file, pkg: v.pkg, version: v.version, reason: "MALWARE", source: `OSV ${v.id}`,
      link: `https://osv.dev/vulnerability/${v.id}`, level: "error" });
  vulns = vulns.filter((x) => !/^MAL-/.test(x.id));
  if (cfg.kev) {
    const kev = new Map(((await cachedJson("kev.json", INTEL.kev, online))?.vulnerabilities || []).map((k) => [k.cveID, k]));
    for (const v of vulns) {
      const k = v.cve && kev.get(v.cve);
      if (k) Object.assign(v, { kev: k.dateAdded, ransomware: k.knownRansomwareCampaignUse === "Known", level: "error" });
    }
  }
  if (cfg.epss) {
    const scores = await epssScores([...new Set(vulns.map((v) => v.cve).filter(Boolean))], online);
    for (const v of vulns) if (v.cve && scores[v.cve] != null) v.epss = scores[v.cve];
  }
  if (cfg.aikido) {
    for (const eco of new Set(packages.map((p) => p.ecosystem))) {
      const list = AIKIDO_LIST[eco] && await cachedJson(`aikido-${AIKIDO_LIST[eco]}`, INTEL.aikido + AIKIDO_LIST[eco], online);
      if (!Array.isArray(list)) continue;
      const bad = new Map(list.map((m) => [`${m.package_name}@${m.version}`, m.reason]));
      for (const p of packages.filter((x) => x.ecosystem === eco)) {
        const reason = bad.get(`${p.name}@${p.version}`);
        if (reason && !malware.some((m) => m.file === p.file && m.pkg === p.name && m.version === p.version))
          malware.push({ file: p.file, pkg: p.name, version: p.version, reason, source: "Aikido",
            link: `https://intel.aikido.dev/?search=${encodeURIComponent(p.name)}`, level: reason === "MALWARE" ? "error" : "warn" });
      }
    }
  }
  // Exploited in the wild first, then EPSS (in whole percent, so noise below 1% doesn't reorder), then CVSS.
  const pct = (v) => Math.floor((v.epss || 0) * 100);
  vulns.sort((a, b) => !!b.kev - !!a.kev || pct(b) - pct(a) || b.sev - a.sev);
  return { vulns, malware };
}

// GitHub remotes of the repos under the roots (read from .git/config, no API calls).
function githubRepo(dir) {
  const cfgText = readText(path.join(dir, ".git", "config"));
  const m = cfgText?.match(/url\s*=\s*(?:https:\/\/|git@|ssh:\/\/git@)github\.com[:/]([\w.-]+\/[\w.-]+?)(?:\.git)?\s*$/m);
  return m ? m[1] : null;
}

// ---------- report ----------

const rel = (f) => (f.root ? path.join(path.basename(f.root), path.relative(f.root, f.file)) : f.file);

function render(r) {
  const out = [`# Stack watch — ${r.day}`, ""];
  if (r.advisories.length) {
    out.push("## Advisories", "");
    for (const a of r.advisories) out.push(`- ${a.date} [${a.title}](${a.link})`);
    out.push("");
  }
  if (r.newLines.length) out.push(...r.newLines.map((n) => `**New release line: ${n}.**`), "");
  out.push("## This machine", "");
  for (const l of r.local) {
    out.push(`- ${l.product.label} ${l.version}${l.notes.length ? "" : " — OK"}`);
    for (const n of l.notes) out.push(`  - ${n.level.toUpperCase()}: ${n.msg}${n.link ? ` — ${n.link}` : ""}`);
    const lts = newestLts(l.product, r.day);
    const hint = l.notes.some((n) => n.level !== "info") && lts && bumpHint(l.product.name, lts.name);
    if (hint) out.push(`  - Suggested: \`${hint}\``);
  }
  if (r.watch.length) {
    out.push("", "## Watched", "");
    for (const w of r.watch) out.push(`- ${w}`);
  }
  const section = (title, list, fmt) => { if (list.length) out.push("", `## ${title} (${list.length})`, "", ...list.map(fmt)); };
  const decl = (f) => `- \`${rel(f)}:${f.line}\` ${f.source} \`${f.value}\` — ${f.msg}`;
  section("Malicious packages — remove now", r.malware, (m) =>
    `- \`${m.file.replace(HOME, "~")}\` ${m.pkg}@${m.version} — ${m.reason} ([${m.source}](${m.link}))`);
  section("Projects — EOL, update now", r.findings.filter((f) => f.level === "error"), decl);
  if (r.vulns.length) {
    const byFile = new Map();
    for (const v of r.vulns) byFile.set(v.file, [...(byFile.get(v.file) || []), v]);
    const files = [...byFile].sort((a, b) => !!b[1][0].kev - !!a[1][0].kev || (b[1][0].epss || 0) - (a[1][0].epss || 0)
      || b[1][0].sev - a[1][0].sev || b[1].length - a[1].length);
    out.push("", `## Vulnerabilities (${r.vulns.length} in ${files.length} lockfiles)`, "");
    for (const [file, vs] of files) {
      const hi = vs.filter((v) => v.level === "error");
      const kev = vs.filter((v) => v.kev).length;
      out.push(`- \`${file.replace(HOME, "~")}\` — ${kev ? `**${kev} exploited in the wild**, ` : ""}${hi.length} high/critical, ${vs.length - hi.length} low/medium`);
      for (const v of hi.slice(0, 10)) out.push("  " + vuln(v));
      if (hi.length > 10) out.push(`  - … ${hi.length - 10} more high/critical`);
    }
    out.push("", "Details for one project: `osv-scanner scan source -r <dir>`; many fixes: `osv-scanner fix` or the package manager's audit fix.");
  }
  section("Projects — behind / at risk", r.findings.filter((f) => f.level === "warn"), decl);
  if (r.recommendations.length) out.push("", "## Recommendations", "", ...r.recommendations.map((x) => /^\s+-/.test(x) ? x : `- ${x}`));
  if (r.osvNote) out.push("", r.osvNote);
  out.push("", "Ordering: exploited in the wild (CISA KEV) first, then EPSS (probability of exploitation in 30 days), then CVSS.");
  out.push("", `${r.findings.length} versions checked, ${r.findings.filter((f) => f.level === "ok").length} OK; ${r.vulns.length} known vulnerabilities.`, "");
  return out.join("\n");
}

function vuln(v) {
  const id = v.cve ? `${v.cve} / ${v.id}` : v.id;
  return `- ${v.pkg}@${v.version} — [${id}](https://osv.dev/vulnerability/${v.id}) ` +
    `${v.kev ? `**KEV: exploited in the wild since ${v.kev}${v.ransomware ? ", used by ransomware" : ""}**, ` : ""}` +
    `${sevName(v.sev)}${v.sev ? ` ${v.sev}` : ""}${v.epss != null ? `, EPSS ${(v.epss * 100).toFixed(v.epss < 0.01 ? 2 : 0)}%` : ""}${v.fixed ? `, fixed in ${v.fixed}` : ""}${v.summary ? ` — ${v.summary.slice(0, 120)}` : ""}`;
}

function brief(r, prev) {
  const parts = [];
  const fresh = r.advisories.filter((a) => !prev.lastAdvisory || a.date > prev.lastAdvisory);
  if (fresh.length) parts.push(`${fresh[0].title} (${fresh[0].link})`);
  parts.push(...r.newLines.map((n) => `new release line ${n}`));
  for (const l of r.local) for (const n of l.notes) if (n.level !== "info") parts.push(`${l.product.label}: ${n.msg}`);
  const e = r.findings.filter((f) => f.level === "error").length, w = r.findings.filter((f) => f.level === "warn").length;
  const vh = r.vulns.filter((v) => v.level === "error").length, vl = r.vulns.length - vh;
  const mal = r.malware.filter((m) => m.level === "error").length, kev = r.vulns.filter((v) => v.kev).length;
  if (mal) parts.unshift(`${mal} MALICIOUS package${mal > 1 ? "s" : ""} installed`);
  if (kev) parts.unshift(`${kev} vulnerabilit${kev > 1 ? "ies" : "y"} exploited in the wild (CISA KEV)`);
  if (e || w) parts.push(`projects: ${e} EOL, ${w} behind`);
  if (r.vulns.length) parts.push(`vulnerabilities: ${vh} high/critical, ${vl} other`);
  return parts.length ? `Stack watch: ${parts.join("; ")}. Report: ${P.report}` : "";
}

function notify(msg) {
  const title = "Stack watch";
  if (process.platform === "darwin")
    spawnSync("osascript", ["-e", "on run argv", "-e", "display notification (item 1 of argv) with title (item 2 of argv)",
      "-e", "end run", msg, title]);
  else if (IS_WIN)
    spawnSync("powershell", ["-NoProfile", "-Command",
      "[void][Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');" +
      "$n=New-Object System.Windows.Forms.NotifyIcon;$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;" +
      "$n.ShowBalloonTip(10000,$env:SW_TITLE,$env:SW_MSG,'Info');Start-Sleep 11;$n.Dispose()"],
    { env: { ...process.env, SW_TITLE: title, SW_MSG: msg } });
  else spawnSync("notify-send", [title, msg]);
}

// ---------- the run ----------

async function runAll(roots, { offline, prev = {} }) {
  const day = today();
  const cfg = config();
  const raw = await loadData({ offline });
  const idx = indexProducts(raw.products, day);
  const data = { day, cfg, idx, github: new Map(), ...nodeContext(raw.nodeIndex, raw.nodeVuln, day) };
  const findings = scanDeclarations(roots, cfg, data);
  const osv = osvRun(roots, cfg);
  const scanned = analyseOsv(osv.json, data, cfg, day, roots);
  findings.push(...scanned.deps);
  const { vulns, malware } = await enrich(scanned, cfg, !offline);
  const recommendations = [];
  if (cfg.recommend && data.github.size)
    recommendations.push("These repos are on GitHub. Turn on **Dependabot alerts and malware alerts** (free; Settings → " +
      "Advanced Security) so GitHub warns you as soon as an advisory or malware report is published, between stack-watch runs:",
    ...[...data.github.values()].sort().map((r) => `  - [${r}](https://github.com/${r}/settings/security_analysis)`));
  if (cfg.recommend && scanned.packages.some((p) => p.ecosystem === "npm" || p.ecosystem === "PyPI") && !has("safe-chain"))
    recommendations.push("Block known malware at `npm`/`pip install` time with Aikido Safe Chain (open source; " +
      "a daily report can't stop an install). Install: https://github.com/AikidoSec/safe-chain#installation");
  const osvNote = osv.missing ? "Dependency vulnerabilities not checked: install osv-scanner " +
    "(brew install osv-scanner · winget install Google.OSVScanner · go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest)."
    : osv.error ? `osv-scanner failed: ${osv.error}` : "";
  // New LTS / release lines for Node and watched products since the last run.
  const lines = {}, newLines = [], watch = [];
  for (const name of new Set(["nodejs", ...cfg.watch])) {
    const p = idx.byName.get(name);
    if (!p) { if (name !== "nodejs") watch.push(`${name}: not on endoflife.date`); continue; }
    const top = newestLts(p, day) || (p.releases || []).find((r) => !r.eol);
    if (!top) continue;
    lines[name] = top.name;
    if (prev.lines?.[name] && prev.lines[name] !== top.name) newLines.push(`${p.label} ${top.name}`);
    if (name !== "nodejs" || cfg.watch.includes(name))
      watch.push(`${p.label}: ${top.isLts ? "LTS " : ""}${top.name}, latest ${top.latest?.name || "?"}${top.latest?.date ? ` (${top.latest.date})` : ""}`);
  }
  const local = localRuntimes(data);
  const nodeLts = newestLts(idx.byName.get("nodejs") || {}, day);
  return { day, cfg, findings, vulns, malware, recommendations, osvNote, osvError: osv.error, local, advisories: data.advisories, newLines, lines,
    watch, nodeLts };
}

async function cmdCheck(args) {
  const day = today();
  if (!args.includes("--force") && readText(P.last)?.trim() === day) return;
  const prev = readJson(P.state, {});
  let r;
  try { r = await runAll(config().roots, { offline: false, prev }); }
  catch (e) { console.error(`stack-watch: ${e.message}; retrying next run`); return; } // no stamp → retry
  // A failed vulnerability scan must not clear yesterday's alert or count as today's check.
  if (r.osvError) { console.error(`stack-watch: osv-scanner failed: ${r.osvError}; retrying next run`); return; }
  const report = render(r), alert = brief(r, prev);
  write(P.report, report);
  if (alert) write(P.alert, alert + "\n"); else fs.rmSync(P.alert, { force: true });
  if (args.includes("--notify") && r.cfg.notify && alert && alert !== prev.lastAlert) notify(alert.replace(/ Report: .*/, ""));
  write(P.state, JSON.stringify({ day, lines: { ...prev.lines, ...r.lines }, lastAlert: alert,
    lastAdvisory: r.advisories.map((a) => a.date).sort().pop() || prev.lastAdvisory }, null, 2));
  write(P.last, day + "\n");
  if (!args.includes("--quiet")) console.log(report);
}

async function cmdScan(dirs) {
  const cfg = config();
  const roots = dirs.length ? dirs.map((d) => path.resolve(expand(d))) : cfg.roots;
  if (!roots.length) { console.error(`No roots: pass directories or set "roots" in ${CONFIG_FILE}`); process.exit(64); }
  const r = await runAll(roots, { offline: true });
  console.log(render(r));
  const bad = (l) => [r.findings, r.vulns, r.malware].some((xs) => xs.some((x) => x.level === l));
  process.exitCode = bad("error") ? 2 : bad("warn") ? 1 : 0;
}

function cmdStatus(args) {
  if (args.includes("--brief")) {
    // For SessionStart hooks: one line, only if actionable and fresh (≤ 7 days).
    // One file descriptor for both the age check and the read, so the file can't change in between.
    let fd;
    try {
      fd = fs.openSync(P.alert, "r");
      if (Date.now() - fs.fstatSync(fd).mtimeMs < 7 * 86400000) process.stdout.write(fs.readFileSync(fd, "utf8"));
    } catch { /* no alert */ } finally { if (fd !== undefined) fs.closeSync(fd); }
    return;
  }
  console.log(readText(P.report) ?? "No report yet: run `check --force`.");
}

// ---------- schedule ----------

const LABEL = "dev.stack-watch";

// argv that runs `check` with the user's current default Node. With nvm the versioned path changes on every bump,
// so resolve nvm's default at run time and fall back to the Node that ran `install`.
function runner() {
  const args = ["check", "--notify", "--quiet"];
  const nvmSh = path.join(process.env.NVM_DIR || path.join(HOME, ".nvm"), "nvm.sh");
  if (IS_WIN || !fs.existsSync(nvmSh)) return [process.execPath, SCRIPT, ...args];
  const sh = `. "$1" >/dev/null 2>&1 && nvm use --silent default >/dev/null 2>&1; ` +
    `command -v node >/dev/null 2>&1 || PATH="$2:$PATH"; shift 2; exec node "$@"`;
  return ["/bin/sh", "-c", sh, "stack-watch", nvmSh, path.dirname(process.execPath), SCRIPT, ...args];
}

function cmdInstall() {
  const argv = runner();
  if (process.platform === "darwin") {
    const plist = path.join(HOME, "Library", "LaunchAgents", `${LABEL}.plist`);
    fs.mkdirSync(STATE_DIR, { recursive: true }); // launchd won't create the StandardErrorPath directory
    const xml = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
    // Hourly + at login; the daily stamp makes it run once a day and catch up after the machine was off.
    write(plist, `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>${argv.map((a) => `<string>${xml(a)}</string>`).join("")}</array>
  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardErrorPath</key><string>${xml(path.join(STATE_DIR, "launchd.log"))}</string>
  <key>ProcessType</key><string>Background</string>
  <key>LowPriorityIO</key><true/>
</dict>
</plist>
`);
    spawnSync("launchctl", ["bootout", `gui/${process.getuid()}`, plist]);
    const r = spawnSync("launchctl", ["bootstrap", `gui/${process.getuid()}`, plist], { stdio: "inherit" });
    console.log(r.status === 0 ? `Installed ${plist}` : `Wrote ${plist}, but launchctl bootstrap failed`);
  } else if (IS_WIN) {
    const r = spawnSync("schtasks", ["/Create", "/F", "/SC", "HOURLY", "/TN", "stack-watch",
      "/TR", `"${process.execPath}" "${SCRIPT}" check --notify --quiet`], { stdio: "inherit" });
    console.log(r.status === 0 ? "Installed scheduled task stack-watch (hourly; runs once a day)" : "schtasks failed");
  } else {
    const dir = path.join(process.env.XDG_CONFIG_HOME || path.join(HOME, ".config"), "systemd", "user");
    const q = (a) => `"${a.replace(/[\\"]/g, "\\$&").replace(/\$/g, "$$$$").replace(/%/g, "%%")}"`;
    write(path.join(dir, "stack-watch.service"),
      `[Unit]\nDescription=Stack watch\n\n[Service]\nType=oneshot\nExecStart=${argv.map(q).join(" ")}\n`);
    write(path.join(dir, "stack-watch.timer"),
      `[Unit]\nDescription=Stack watch (hourly; runs once a day)\n\n[Timer]\nOnBootSec=5min\nOnUnitActiveSec=1h\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n`);
    const r = spawnSync("systemctl", ["--user", "enable", "--now", "stack-watch.timer"], { stdio: "inherit" });
    if (r.status === 0) console.log("Installed systemd user timer stack-watch.timer");
    else console.log(`systemd --user unavailable. Add to crontab instead:\n17 * * * * "${process.execPath}" "${SCRIPT}" check --notify --quiet`);
  }
  console.log(argv[0] === "/bin/sh" ? "Schedule runs nvm's default Node." : `Schedule runs ${process.execPath}; re-run install after removing that Node.`);
  if (!config().roots.length) console.log(`Set project roots in ${CONFIG_FILE}, e.g. {"roots": ["~/Dev"]}`);
}

function cmdUninstall() {
  if (process.platform === "darwin") {
    const plist = path.join(HOME, "Library", "LaunchAgents", `${LABEL}.plist`);
    spawnSync("launchctl", ["bootout", `gui/${process.getuid()}`, plist]);
    fs.rmSync(plist, { force: true });
  } else if (IS_WIN) spawnSync("schtasks", ["/Delete", "/F", "/TN", "stack-watch"], { stdio: "inherit" });
  else {
    spawnSync("systemctl", ["--user", "disable", "--now", "stack-watch.timer"], { stdio: "inherit" });
    const dir = path.join(process.env.XDG_CONFIG_HOME || path.join(HOME, ".config"), "systemd", "user");
    for (const f of ["stack-watch.service", "stack-watch.timer"]) fs.rmSync(path.join(dir, f), { force: true });
  }
  console.log("Schedule removed. State left in " + STATE_DIR);
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fs.realpathSync(SCRIPT)) {
  const [cmd = "status", ...args] = process.argv.slice(2);
  const run = { check: cmdCheck, scan: cmdScan, status: cmdStatus, install: cmdInstall, uninstall: cmdUninstall }[cmd];
  if (!run) { console.error("usage: stack-watch.mjs check|scan|status|install|uninstall"); process.exit(64); }
  await run(args);
}
