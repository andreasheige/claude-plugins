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

Restart the session. Ask for it ("turn this prototype into user stories", "publish the backlog to Azure
DevOps") or run `/skills:prototype-to-backlog`.

## prototype-to-backlog

Give it a prototype (a URL or a folder), optionally the repo and an Azure DevOps project. It:

1. **Inventories** the prototype: screenshots per screen, phone and desktop, light and dark.
2. **Drafts** features and user stories with Given/When/Then criteria and dependencies.
3. **Refines** them with persona agents (product owner, UX, tech lead, QA, backend). Nobody is asked anything.
4. **Asks you to approve**: all, some, or with edits. This is the only human step.
5. **Publishes** what you approved to Azure DevOps as you, after a dry run, without duplicates.
6. Optionally **syncs** each story's board column with a plan checklist.

### Prerequisites

| | macOS | Windows |
|---|---|---|
| Python 3 | preinstalled `python3`, or `brew install python` | `winget install -e --id Python.Python.3.12` |
| Azure CLI (only to publish) | `brew install azure-cli` | `winget install -e --id Microsoft.AzureCLI` |
| Node 18+ (only for screenshots) | `brew install node` | `winget install -e --id OpenJS.NodeJS.LTS` |

The skill offers these when something is missing and asks before installing. Without the Azure CLI it
stops at the approved backlog for someone else to publish.

### Signing in to Azure DevOps

You don't need to know the Azure CLI. When it is time to publish, the skill:

1. shows the one install command for your computer if the Azure CLI is missing;
2. **opens the sign-in page in your browser**: sign in with your work account and come back;
3. checks that you can see the project, without changing anything.

Tickets are created as you, with your own rights. The skill never sees, asks for or saves a password or token.

### Cost

The refinement swarm is the expensive part: each round is one Sonnet call per persona plus one moderator
call. Stories that are already complete skip it, and there are at most two rounds.

### Tests

```
python3 -m unittest discover -s skills/tests     # from the repo root; no network, az is faked
```

Windows: `py -3 -m unittest discover -s skills\tests`.
