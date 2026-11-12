// Inventory of a prototype: one screenshot per screen x viewport x theme, plus inventory.json with
// each screen's headings and controls (accessible names) for drafting stories.
//
//   node shoot.mjs <config.json> <outdir>
//
// Run it from a folder where Playwright is installed (`npm i -D playwright` in a scratch folder, then
// `npx playwright install chromium`); it resolves Playwright from the current directory.
// Serve a local prototype first: `python -m http.server 4400 --bind 127.0.0.1 -d <prototype folder>`.
// Config: see references/inventory.md. Screens are reached by URL path, or by clicking accessible
// names in order from the start page (for prototypes with an in-memory router and no URL routes).
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

const [cfgPath, outDir] = process.argv.slice(2);
if (!cfgPath || !outDir) { console.error("usage: node shoot.mjs <config.json> <outdir>"); process.exit(2); }
const req = createRequire(join(process.cwd(), "noop.js"));
let pw;
try { pw = req("playwright"); } catch { try { pw = req("@playwright/test"); } catch {
  console.error("Playwright not found from this folder. Run: npm i -D playwright && npx playwright install chromium");
  process.exit(3);
} }

const cfg = JSON.parse(readFileSync(cfgPath, "utf8"));
const viewports = cfg.viewports ?? [{ name: "desktop", width: 1440, height: 900 }];
const themes = cfg.themes ?? ["light"];
const waitMs = cfg.waitMs ?? 1500;
const exact = (s) => new RegExp(`^\\s*${s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`, "i");
mkdirSync(resolve(outDir), { recursive: true });

function urlFor(path, theme) {
  const u = new URL(path ?? "", cfg.baseUrl);
  if (cfg.themeParam) u.searchParams.set(cfg.themeParam, theme);
  return u.toString();
}

async function clickByName(page, name) {
  const loc = page.getByRole("link", { name: exact(name) })
    .or(page.getByRole("button", { name: exact(name) }))
    .or(page.getByRole("tab", { name: exact(name) }))
    .or(page.getByRole("menuitem", { name: exact(name) })).first();
  await loc.click({ timeout: 4000 });
  await page.waitForTimeout(waitMs);
}

async function outline(page) {
  return page.evaluate(() => {
    const name = (e) => (e.getAttribute("aria-label") || e.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80);
    const pick = (sel) => [...new Set([...document.querySelectorAll(sel)].map(name).filter(Boolean))].slice(0, 60);
    return {
      title: document.title,
      headings: pick("h1, h2, h3"),
      buttons: pick("button, [role=button]"),
      links: pick("a[href], [role=link]"),
      fields: pick("input, select, textarea"),
    };
  });
}

const browser = await pw.chromium.launch();
const shots = [], failures = [];
try {
  for (const vp of viewports) for (const theme of themes) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, colorScheme: theme === "dark" ? "dark" : "light" });
    for (const s of cfg.screens) {
      const page = await ctx.newPage();
      const file = `${s.name}-${vp.name}-${theme}.png`;
      try {
        await page.goto(urlFor(s.path, theme)); await page.waitForTimeout(cfg.startWaitMs ?? waitMs);
        if (cfg.themeAttribute) await page.evaluate(([a, t]) => document.documentElement.setAttribute(a, t), [cfg.themeAttribute, theme]);
        for (const n of s.click ?? []) await clickByName(page, n);
        // Move the pointer away so hover flyouts don't cover the page.
        await page.mouse.move(vp.width / 2, vp.height - 10); await page.waitForTimeout(400);
        await page.screenshot({ path: join(outDir, file), fullPage: !!s.fullPage });
        shots.push({ screen: s.name, viewport: vp.name, theme, file, note: s.note ?? "", ...(await outline(page)) });
      } catch (e) {
        failures.push({ screen: s.name, viewport: vp.name, theme, error: String(e.message ?? e).split("\n")[0] });
      } finally { await page.close(); }
    }
    await ctx.close();
  }
} finally { await browser.close(); }

writeFileSync(join(outDir, "inventory.json"), JSON.stringify({ baseUrl: cfg.baseUrl, shots, failures }, null, 2) + "\n", "utf8");
console.log(`${shots.length} screenshot(s), ${failures.length} failure(s) -> ${join(outDir, "inventory.json")}`);
for (const f of failures) console.log(`  failed: ${f.screen} ${f.viewport} ${f.theme}: ${f.error}`);
process.exit(failures.length ? 1 : 0);
