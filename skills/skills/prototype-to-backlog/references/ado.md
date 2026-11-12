# Azure DevOps details

## Work item fields used

| Backlog field | ADO | Notes |
|---|---|---|
| `type` | Epic, Feature, User Story, Task, Bug | Agile process names. Scrum uses Product Backlog Item, Basic uses Issue: rename `type` before publishing. |
| `title` | `--title` | max 255 characters |
| `description` (+ screenshots, effort) | `System.Description` | HTML; publish escapes the text, blank lines = paragraphs, `- ` lines = list |
| `acceptanceCriteria` | `Microsoft.VSTS.Common.AcceptanceCriteria` | HTML list; Given/When/Then in bold |
| `storyPoints` | `Microsoft.VSTS.Scheduling.StoryPoints` | Scrum: `Effort` instead |
| `tags` + idempotency tag | `System.Tags` | `; `-separated |
| `assignedTo`, `iteration`, `area` | `--assigned-to`, `--iteration`, `--area` | per item, else the `ado` block's default |
| `state`, `column` | `--state`, the board's Kanban column field | see "Board placement" |

Relations (`az boards work-item relation add --relation-type ...`):

| Backlog | relation type | reference name |
|---|---|---|
| `parent` | `parent` | `System.LinkTypes.Hierarchy-Reverse` |
| each `dependsOn` entry | `predecessor` | `System.LinkTypes.Dependency-Reverse` |
| each `related` entry | `related` | `System.LinkTypes.Related` |

A reference is another item's key, or `#12345` for a work item that already exists in ADO.
Publish checks the item's existing relations (`work-item show --expand relations`) before adding one.

Screenshots are referenced by file name in the description. Publish does not upload attachments.

## Idempotency (never create duplicates)

A create script that ran twice once made a full duplicate set, which then had to be set to Removed by
hand. So publish never creates before it has looked:

1. The tag `ptb-<10 hex>` = sha256(project + key). It depends on the item **key**, not the title, so
   refinement can rename a story freely. Never renumber keys once a backlog has been published.
2. The ids file `~/.prototype-to-backlog/<project slug>/ids-<hash>.json`, one per backlog and
   destination (the hash covers the exact backlog project name, organization and ADO project), written
   after every single create, so an interrupted run resumes without duplicates.
3. For each approved item: ids file -> `work-item show`; the cached id is used only if the item exists,
   is not Removed, carries this item's exact tag and is in the target project (otherwise forget it) ->
   WIQL query for the tag (excluding Removed) -> only then create. More than one hit is reported; the
   lowest id is used. Ids of earlier-published items that links point at are verified the same way.
   Sync refuses an id whose item does not carry the tag. The mapping's `ado` block must name the same
   organization/project as the backlog, so both find the same ids file.

Re-running publish is safe: existing items are reported as `exists as #id` and not touched (except the
effort line with `--effort`, and missing links).

## Board placement (state + column)

A team's board shows a work item in the column whose `stateMappings` maps its type to its state. If no
column maps a state, the item disappears from the board: a team board without a Resolved column lost
every Resolved story. Rules in `adolib.place`:

- The board's columns and Kanban column field come from the board itself:
  `az devops invoke --area work --resource columns --route-parameters project=P team=T board=Stories`
  and `--resource boards ... id=Stories` (`fields.columnField.referenceName`, a `WEF_<guid>_Kanban.Column` name).
- An item's `state` must have a column on the board for its type, and a named `column` must map that type to
  that state. Otherwise publish/sync refuses **before writing anything**.
- Types the board does not show (Features on the Stories board, Tasks) get only the state.
- Closed / Done / Removed are never set by publish. Sync sets Closed/Done only when the mapping has
  `"allowDone": true` (a board whose done column means "merged"), never Removed.

## Mapping file (sync and effort)

`ado_sync_state.py` and `effort.py` read one JSON file next to the plans:

```json
{
  "plans": ["plans/redesign.md", "plans/fidelity.md"],
  "items": {
    "S1": ["0.*", "1.*"],
    "S2": ["2.*", "3.*"],
    "T1": ["fidelity:S.*"]
  },
  "ado": { "organization": "https://dev.azure.com/example-org", "project": "Example", "team": "Example Team", "board": "Stories" },
  "rules": [
    { "when": "none", "state": "New" },
    { "when": "some", "state": "Active", "column": "In development" },
    { "when": "all",  "state": "Active", "column": "Test/Design review" }
  ],
  "allowDone": false,
  "effort": { "repo": "~/Dev/my-app", "since": "2026-11-10T13:00:00Z", "note": "Claude Sonnet via plan-runner." }
}
```

- `plans`: markdown checklists, paths relative to the mapping file. Items are `- [x] <id> ...`
  (`[ ]` open, `[~]` in progress, optional `@agent` before the id).
- `items`: backlog key -> fnmatch patterns over plan item ids. The first key that matches wins (file
  order). `stem:pattern` matches only in the plan whose file name (without `.md`) is `stem`.
- `rules`: none / some / all of a key's plan items ticked -> state and optional column. Default: New /
  Active / Active without columns.
- `effort`: optional. Each ticked item ends at its newest commit (hashes written in the item) after
  `since`; tokens are read from Claude Code's transcripts for `repo`. Approximate: parallel work is
  counted for the item that finished.

```
python scripts/ado_sync_state.py plans/ado-map.json --project "<backlog project>"            # dry run
python scripts/ado_sync_state.py plans/ado-map.json --project "<backlog project>" --apply --effort
```

## Sign-in options, in order

1. `scripts/ado_login.py` (browser sign-in via az; `--device-code` on a remote machine).
2. Microsoft's Azure DevOps MCP server, if the user already has it connected: create the same items
   with its tools, still checking for the idempotency tag first and writing the ids file.
3. Neither: stop after approval and hand over `backlog.json` + `backlog.md`; someone with access runs publish.

Never ask for, store or print a PAT or token, in chat or in files.
