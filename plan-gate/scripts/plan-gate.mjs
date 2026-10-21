// Stop hook: keeps Claude working through an active plan file instead of
// stopping between phases to ask "should I continue?".
//
// Inert unless the session turned it on with `/plan-gate <plan.md>` (or a user
// message line `PLAN-GATE: <plan.md>`); `/plan-gate off` turns it off. The
// activation is read from the transcript, so there is no state to go stale.
//
// While a plan is active, a stop is blocked when the plan still has open
// checkbox items (`- [ ]`, or `- [~]` from progress-board) and no line starting
// with `BLOCKED:`. Claude writes that line when it genuinely needs the user
// (ambiguity, an ask-first area, landing a PR); then the stop goes through.
//
// Loop guard: at most MAX_CONTINUATIONS blocked stops per user prompt. After
// that the stop goes through with a message saying why.
//
// Fails open: any error, missing transcript or missing plan allows the stop.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MAX_CONTINUATIONS = 10;
const STATE_DIR = join(dirname(fileURLToPath(import.meta.url)), ".state");

function allow(message) {
  if (message) process.stdout.write(JSON.stringify({ systemMessage: message }));
  process.exit(0);
}

function textOf(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  // A tool result is not something the user typed.
  if (content.some((b) => b?.type === "tool_result")) return "";
  return content.filter((b) => b?.type === "text").map((b) => b.text).join("\n");
}

// Walks the transcript once: the latest gate command and the latest real
// (non-meta) user prompt, which resets the continuation counter.
function scan(transcriptPath) {
  let plan = null;
  let lastPrompt = null;
  for (const line of readFileSync(transcriptPath, "utf8").split("\n")) {
    if (!line) continue;
    let entry;
    try {
      entry = JSON.parse(line);
    } catch {
      continue;
    }
    if (entry.type !== "user" || entry.isMeta) continue;
    const text = textOf(entry.message?.content);
    if (!text) continue;
    lastPrompt = entry.uuid ?? lastPrompt;

    let arg = null;
    const cmd = text.match(/<command-name>\/plan-gate<\/command-name>[\s\S]*?<command-args>([\s\S]*?)<\/command-args>/);
    if (cmd) arg = cmd[1].trim();
    const marker = text.match(/^PLAN-GATE:\s*(\S+)\s*$/m);
    if (marker) arg = marker[1];
    if (arg === null) continue;

    if (arg === "" || arg === "off") plan = null;
    else plan = isAbsolute(arg) ? arg : resolve(entry.cwd ?? process.cwd(), arg);
  }
  return { plan, lastPrompt };
}

function openItems(planText) {
  return planText
    .split("\n")
    .map((l) => l.match(/^\s*[-*]\s+\[( |~)\]\s+(.*)$/))
    .filter(Boolean)
    .map((m) => m[2].trim());
}

try {
  const payload = JSON.parse(readFileSync(0, "utf8"));
  const { session_id: sessionId, transcript_path: transcriptPath } = payload;
  if (!sessionId || !transcriptPath || !existsSync(transcriptPath)) allow();

  const { plan, lastPrompt } = scan(transcriptPath);
  if (!plan || !existsSync(plan)) allow();

  const planText = readFileSync(plan, "utf8");
  if (/^\s*BLOCKED:/m.test(planText)) allow();
  const items = openItems(planText);
  if (items.length === 0) allow();

  mkdirSync(STATE_DIR, { recursive: true });
  const stateFile = join(STATE_DIR, `${sessionId}.json`);
  let state = { lastPrompt: null, count: 0 };
  try {
    state = JSON.parse(readFileSync(stateFile, "utf8"));
  } catch {}
  if (state.lastPrompt !== lastPrompt) state = { lastPrompt, count: 0 };

  if (state.count >= MAX_CONTINUATIONS) {
    allow(`plan-gate: stopped after ${MAX_CONTINUATIONS} automatic continuations; ${items.length} item(s) still open in ${plan}.`);
  }
  state.count += 1;
  writeFileSync(stateFile, JSON.stringify(state));

  process.stdout.write(
    JSON.stringify({
      decision: "block",
      reason:
        `The plan ${plan} still has ${items.length} open item(s). Next: "${items[0]}". ` +
        `Keep going: do it, verify it, tick it (- [x]). ` +
        `Only if you need the user (real ambiguity, an ask-first area, landing a PR) add a line "BLOCKED: <reason>" to the plan, then stop. ` +
        `(Automatic continuation ${state.count} of ${MAX_CONTINUATIONS}; the user can turn this off with /plan-gate off.)`,
    }),
  );
  process.exit(0);
} catch {
  allow();
}
