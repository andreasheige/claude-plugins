# skills

Standalone agent skills, one folder each under [`skills/`](skills). Install the plugin once and every
skill in it is available.

| Skill | What it does |
|---|---|
| [`prototype-to-backlog`](skills/prototype-to-backlog/SKILL.md) | Prototype → refined user stories → your approval → Azure DevOps, without duplicates |

## Install

Inside Claude Code (CLI or desktop app):

```
/plugin marketplace add andreasheige/claude-plugins
/plugin install skills@personal-plugins
```

Restart the session. The skill triggers on its own when you ask for it ("turn this prototype into user
stories", "refine these stories", "publish the backlog to Azure DevOps"), or run `/skills:prototype-to-backlog`.

## prototype-to-backlog

You give it a prototype (a URL, or a folder such as a Figma Make export or a saved claude.ai artifact),
optionally the repo it will be built in, and optionally an Azure DevOps project. It:

1. **Inventories** the prototype: one screenshot per screen, phone and desktop, light and dark, plus a list
   of each screen's headings and controls. Prototypes without URL routes are navigated by clicking
   buttons and links by name.
2. **Drafts** Features and User Stories ("As a … I want … so that …"), acceptance criteria as
   Given/When/Then, dependencies, a screenshot per story, and backend Tasks where the prototype needs data.
3. **Refines** them with a swarm of persona agents: product owner, UX/design, tech lead, QA and an optional
   backend persona, each with its own checklist and inputs, answering pass or fix with concrete edits.
   A moderator merges; at most two rounds. Stories that already pass a cheap Definition-of-Ready check skip it.
   No person is asked anything during this step.
4. Shows you the backlog as a readable page and **asks you to approve**: all, some (by key), or with edits.
   This is the only human step. What you approved is recorded in `backlog.json`; an item edited after
   approval needs approving again.
5. **Publishes** the approved items to Azure DevOps as you, after a dry run: parent and predecessor
   links, placed in the right column of your team's board. Running it again never creates duplicates
   (each item carries a stable tag, and an ids file is kept under `~/.prototype-to-backlog/<project>/`).
6. Optionally keeps each story's state and board column in sync with a plan checklist, and adds an
   effort line (hours and Claude tokens spent per ticket).

### Prerequisites

| | macOS | Windows |
|---|---|---|
| Python 3 (standard library only) | preinstalled `python3`, or `brew install python` | `winget install -e --id Python.Python.3.12` |
| Azure CLI (only to publish) | `brew install azure-cli` | `winget install -e --id Microsoft.AzureCLI` |
| Node 18+ and Playwright (only for the screenshots) | `brew install node` | `winget install -e --id OpenJS.NodeJS.LTS` |

The skill offers these commands when something is missing and asks before running them. Without Node it
can work from screenshots you provide; without the Azure CLI it stops at the approved backlog
(`backlog.json` + `backlog.md`) for someone else to publish.

### Signing in to Azure DevOps (no az knowledge needed)

For product owners, designers and testers: you don't need to know the Azure CLI. When it is time to publish,
the skill runs `scripts/ado_login.py`, which:

1. checks that the Azure CLI is installed, and if not shows the one install command for your computer;
2. adds the Azure DevOps extension;
3. **opens the sign-in page in your browser**: sign in with your normal work account and come back
   (the skill says when);
4. sets your organization and project as the default;
5. checks, read-only, that you can see the project.

Tickets are created as you, with your own rights, so they show your name in the history. Your sign-in stays
in the Azure CLI's own store: the skill never sees, asks for or saves a password, token or PAT. If your
account belongs to several organizations, the skill asks for your organization's tenant once.

### Cost

The refinement swarm is the expensive part. Each round is one call per persona (4–5, on Sonnet) plus one
moderator call, and every call reads all stories under review; the UX persona also reads the screenshots.
The ready-check and the two-round cap keep a 20-story backlog to roughly 5–12 agent calls. Screenshots
dominate input size, so each story references only the screens it needs.

### Files

```
skills/prototype-to-backlog/
  SKILL.md                     the workflow the agent follows
  references/personas.md       persona checklists, inputs, prompt, moderator rules
  references/ado.md            ADO fields, links, idempotency, board placement, mapping file
  references/inventory.md      screenshot config and serving the prototype
  references/backlog.schema.json
  scripts/backlog.py           validate / ready / render / approve / status
  scripts/ado_login.py         browser sign-in for non-developers
  scripts/ado_publish.py       dry-run-first, idempotent publish
  scripts/ado_sync_state.py    state + board column from plan checklists
  scripts/effort.py            optional effort line
  scripts/shoot.mjs            Playwright screenshots + inventory.json
```

### Tests

```
python3 -m unittest discover -s skills/tests     # from the repo root; no network, az is faked
```

Windows: `py -3 -m unittest discover -s skills\tests`.
