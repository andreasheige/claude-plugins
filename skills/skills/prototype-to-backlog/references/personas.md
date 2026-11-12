# Refinement personas

Every persona is an agent. No human is asked anything during refinement; the only human step is the
approval before publishing.

## How a round runs

1. Run `python scripts/backlog.py ready <backlog.json>`. Stories it reports as `ready` skip the swarm.
   Epics, Features and Tasks are not reviewed by the swarm; the product owner sees the epic as context.
2. Start **one Agent call per persona, all in the same message** so they run in parallel. Each call
   reviews **every** swarm story in one go (one call per persona, not per story × persona: cheaper, and
   the persona sees overlaps between stories). Use `model: "sonnet"` for personas.
3. Each persona answers with the JSON below and nothing else.
4. The moderator merges (see "Moderator"). Use the default model for the moderator, never sonnet:
   merging conflicting edits is the hard part.
5. Round 2 only for stories where a merged edit changed the acceptance criteria or the scope, and only
   with the personas that answered `fix` for that story. **At most 2 rounds.** Whatever is still
   disputed after round 2: set `refinement.status` to `needs-human` and leave a note in `verdicts`; the
   approver sees it in the rendered markdown.

If a Workflow tool is available and the user has opted into workflows, the same fan-out can run there.
Without one, the plain parallel Agent calls above are the default and are enough.

## The prompt each persona gets

Fill in the persona block and inputs; keep the rest verbatim.

```
You are the <PERSONA> in a backlog refinement. You review user stories drafted from a prototype.
You cannot ask anyone anything; judge from the inputs below and your checklist.

Checklist:
<the persona's checklist from personas.md>

Inputs:
<only the inputs listed for this persona: story JSON, epic, screenshot paths to Read, repo paths, ...>

Answer with JSON only, no prose around it:
{"persona": "<PERSONA>", "stories": [
  {"key": "S1", "verdict": "pass" | "fix",
   "edits": [{"field": "title|description|acceptanceCriteria|dependsOn|storyPoints|tags",
              "op": "replace|add|remove", "value": <new value or the item to add/remove>,
              "why": "<one line, tied to a checklist point>"}],
   "split": [<optional: new story objects when the story does more than one thing>],
   "notes": "<optional, one line>"}]}
Rules: "fix" needs at least one concrete edit (exact new text, not "clarify X"). No edits outside your
checklist. Acceptance criteria you add are {"given","when","then"} objects in the story's language.
```

## Personas

### Product owner
- **Checks:** clear user value (the "so that" is a real benefit, not a restatement); one thing per story
  (INVEST: independent, negotiable, valuable, estimable, small, testable); in scope for the epic; no
  hidden second story ("and" in the title is a smell, propose a `split`); priority order makes sense.
- **Gets:** the swarm stories, the parent Feature/Epic, the list of all story titles.

### UX / design
- **Checks:** matches the prototype screens; every state is covered (empty, loading, error, long
  content, no permission); accessibility (keyboard, focus order, contrast, labels, reduced motion);
  phone width; dark theme if the prototype has one; copy and naming match the prototype.
- **Gets:** the swarm stories and the screenshot files each story references (Read the PNGs), plus
  `inventory.json` (headings and controls per screen). Missing states it can't see in any screenshot
  become acceptance criteria, not guesses about the visual design.

### Tech lead
- **Checks:** feasible as written; dependencies between stories (`dependsOn`) and on the backend are
  explicit; frontend/backend contract named (endpoint, payload) when data is involved; reuse of
  existing components; size (split anything bigger than a few days); risks.
- **Gets:** the swarm stories, the repo path (read-only: routes, components, API clients), API
  contracts if any. Without a repo: judge from the prototype and say so in `notes`.

### QA
- **Checks:** every criterion is testable and observable (no "works well", "fast", "intuitive"); edge
  cases (empty input, very long text, special characters such as å ä ö, many items, network failure);
  how it will be verified (unit, e2e, manual) is clear; no criterion contradicts another.
- **Gets:** the swarm stories, the names of existing test folders/specs in the repo if there is one.

### Backend (optional)
Use when the prototype implies data the app does not have yet.
- **Checks:** the API need is concrete enough to build against: endpoint, method, request/response
  shape, errors, who may call it, persistence; a backend Task exists with the story as its predecessor.
- **Gets:** the stories that touch data, existing contracts (OpenAPI, docs/contracts) if any.

## Moderator

The moderator gets the backlog JSON and every persona answer, and writes the merged backlog:

1. Apply non-conflicting edits as given.
2. Conflicts on the same field: prefer the persona whose checklist owns it (value/scope: PO;
   states/a11y: UX; contract/size: tech lead; testability: QA; API: backend). Otherwise keep the
   smaller story.
3. `split`: create the new stories with new keys (never reuse or renumber existing keys: the key is
   the idempotency key in ADO), give them the same parent, and run `backlog.py ready` on them.
4. Record per story: `refinement.status` (`refined` or `needs-human`), `rounds`, and one
   `verdicts` entry per persona (`persona`, `round`, `verdict`, short `notes`).
5. Run `python scripts/backlog.py validate`. Fix what it reports before the next round.

## Cost

Per round: one call per persona (4-5) plus one moderator call, each reading all swarm stories and,
for UX, the screenshots. Screenshots are the biggest input: reference only the screens a story needs.
The `ready` pre-check and the 2-round cap keep a 20-story backlog to roughly 5-12 agent calls.
