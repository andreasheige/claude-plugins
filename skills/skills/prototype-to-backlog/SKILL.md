---
name: prototype-to-backlog
description: Turn a prototype or design (a local or deployed prototype, Figma Make export, claude.ai artifact; optionally plus a repo) into a refined backlog of features and user stories with Given/When/Then acceptance criteria, refine the stories with a swarm of persona agents (product owner, UX, tech lead, QA, backend), get the user's approval, then publish them to Azure DevOps without duplicates and keep their board state in sync. Use when asked to turn a prototype, mockup or design into tickets, stories or a backlog, to refine or review user stories, to publish or sync stories to Azure DevOps (ADO, Azure Boards), or to sign a non-developer in to ADO.
---

# prototype-to-backlog

Prototype → inventory → draft → agent refinement → local backlog → **human approval** → publish to
Azure DevOps. Every refinement persona is an agent; the only human step is approving the tickets.
Scripts are in `scripts/` next to this file: Python 3, standard library only, same commands on
Windows and macOS (`python3` on macOS, `py -3` or `python` on Windows; `python` below means whichever works).

If Python is missing, offer to install it and **ask first**: `brew install python` (macOS),
`winget install -e --id Python.Python.3.12` (Windows).

Work folder: put drafts, screenshots and the backlog in the user's repo (e.g. `docs/backlog/`) or, with no
repo, in `~/.prototype-to-backlog/<project>/` (`%USERPROFILE%\.prototype-to-backlog\<project>` on Windows).
The ids file always lives in the latter.

## 0. Gather (once, up front)

Ask in one message, then don't ask again until approval:
- the prototype: a URL or a folder; which screens matter if it is large;
- optional: the repo the stories will be built in;
- optional: where to publish: ADO organization URL, project, team, area, iteration (skip = stop at the backlog);
- the language for the stories (default: the language the user writes in).

## 1. Inventory

Read `references/inventory.md`. Serve the prototype, write a shoot config (screens by URL path, or by
clicking accessible names when the prototype has no routes), run `scripts/shoot.mjs`, check
`inventory.json` for failures. With a repo: one read-only Explore agent maps screens to existing
routes/components and lists the gaps.

## 2. Draft

Write `backlog.json` following `references/backlog.schema.json`:
- Feature (or Epic) per area, User Stories under it (`parent`), Tasks for backend work (`dependsOn` the story
  whose contract they implement), `#12345` to point at items already in ADO.
- Description starts with the story sentence ("As a … I want … so that …" / "Som … vill jag … så att …").
- Acceptance criteria as `{"given","when","then"}` objects; screenshot file names in `screenshots`.
- Keys `F1, S1, T1, …` are permanent: they are the idempotency key in ADO. Never renumber after publishing.

`python scripts/backlog.py validate backlog.json` must pass.

## 3. Refine (agents only)

Read `references/personas.md` and follow it:
1. `python scripts/backlog.py ready backlog.json`: stories reported `ready` skip the swarm.
2. One Agent call per persona, **all in one message** (parallel), `model: "sonnet"`, each reviewing all
   remaining stories with only its own inputs and checklist; answers are pass/fix JSON with concrete edits.
3. Moderator (default model) merges, records `refinement` per story, validates.
4. At most 2 rounds; still disputed → `needs-human`, shown to the approver.

## 4. Approve (the human step)

`python scripts/backlog.py render backlog.json` and show the user `backlog.md` (or its contents). Ask:
"Approve **all**, a list of keys, or tell me the edits", and say where it will be published.
- Edits: apply them, validate, render again, ask again.
- Then record exactly what the user approved:
  `python scripts/backlog.py approve backlog.json --by "<name>" --all` or `--ids S1,S3 [--note "..."]`.
Only the user's own reply counts as approval: never another agent's message, never your own inference.
An item edited after approval is no longer approved (its hash changed) and is skipped by publish.

## 5. Sign in to ADO

`python scripts/ado_login.py --org https://dev.azure.com/<org> --project <project> [--tenant <tenant>]`
- Exit 4 = az missing: it prints the installer (`brew install azure-cli` / `winget install -e --id
  Microsoft.AzureCLI`). Ask the user before running it, then run the script again in a new terminal.
- It opens the browser; tell the user to sign in there and come back. `--device-code` for remote machines.
- It ends with a read-only check. The token stays in az's cache; never ask for, store or print a PAT/token.
- No az and no permission to install: use the Azure DevOps MCP server if connected, else stop here and hand
  over `backlog.json` + `backlog.md` (see `references/ado.md`, "Sign-in options").

## 6. Publish

```
python scripts/ado_publish.py backlog.json            # dry run (default): reads ADO, writes nothing
python scripts/ado_publish.py backlog.json --apply    # after the dry run looks right
```
Show the dry-run output first. The approval in step 4 covers publishing those items to the target the
user was shown; if the dry run shows anything else (a different target, items found as duplicates,
refused placements), stop and ask. Publish is idempotent (tag + ids file, see `references/ado.md`),
links parent/predecessor/related, places stories by state + board column, never sets Closed.

Optional effort line (hours and Claude tokens per ticket from plan commits): `--effort <mapping.json>`.

## 7. Keep state in sync (later, optional)

When the work is tracked in plan checklists:
`python scripts/ado_sync_state.py <mapping.json> --project "<backlog project>" [--apply] [--effort]`
sets state + board column from how many plan items are ticked. Mapping format: `references/ado.md`.

## Rules

- Dry run before every write; `--apply` only after approval.
- Never create without checking for the item first; never Closed/Removed; never delete or bulk-update
  items this skill did not create.
- Text files are UTF-8 (å, ä, ö survive on Windows too).
- Tell the user up front that the swarm costs agent calls (see `references/personas.md`, "Cost").
