"""Publish the approved items of a backlog to Azure DevOps. Dry run unless --apply.

  python ado_publish.py <backlog.json>                 # dry run: reads ADO, prints what it would do
  python ado_publish.py <backlog.json> --offline       # dry run without az (no ADO reads)
  python ado_publish.py <backlog.json> --apply         # create / link / place
  python ado_publish.py <backlog.json> --apply --effort mapping.json   # add the effort line

Idempotent. Each item carries a tag derived from project + key (backlog.idempotency_tag). Before
creating, publish looks in the ids file (~/.prototype-to-backlog/<project>/ids-<hash>.json, one per
backlog and destination; a cached id is used only if that item carries the tag) and then in ADO for
the tag; an item found either way is reused, never created again. The ids file is written after
every create, so an interrupted run resumes cleanly.

Only items whose approval hash matches their current content are published. States are placed on
the team board by state + column (read from the board itself); Closed/Removed/Done are never set.
Exit: 0 ok, 1 nothing approved, 2 invalid input or refused placement, 3 az failed.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

import adolib
import backlog as bl

REL = {
    "parent": "System.LinkTypes.Hierarchy-Reverse",
    "predecessor": "System.LinkTypes.Dependency-Reverse",
    "related": "System.LinkTypes.Related",
}
EFFORT_RE = re.compile(r"<p><em>(Total effort|Effort) so far.*?</em></p>", re.S)


# ---- pure helpers (unit-tested) ---------------------------------------------------------------

def text_to_html(text: str) -> str:
    """Blank lines split paragraphs; consecutive '- ' lines become a list. Everything is escaped."""
    out = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if all(ln.lstrip().startswith("- ") for ln in lines):
            out.append("<ul>" + "".join(f"<li>{html.escape(ln.lstrip()[2:])}</li>" for ln in lines) + "</ul>")
        else:
            out.append("<p>" + "<br>".join(html.escape(ln) for ln in lines) + "</p>")
    return "".join(out)


def criteria_html(ac: list) -> str:
    def one(c):
        if isinstance(c, dict):
            return (f"<b>Given</b> {html.escape(c['given'])} <b>when</b> {html.escape(c['when'])} "
                    f"<b>then</b> {html.escape(c['then'])}")
        return html.escape(str(c))
    return "<ul>" + "".join(f"<li>{one(c)}</li>" for c in ac) + "</ul>" if ac else ""


def description_html(it: dict, effort_line: str = "") -> str:
    d = text_to_html(it.get("description", ""))
    if it.get("screenshots"):
        d += "<p>Prototype screens: " + ", ".join(f"<code>{html.escape(s)}</code>" for s in it["screenshots"]) + "</p>"
    if effort_line:
        d += f"<p><em>{html.escape(effort_line)}</em></p>"
    return d


def with_effort(desc: str, effort_line: str) -> str:
    """Replace the effort paragraph in an existing description, or append one."""
    para = f"<p><em>{html.escape(effort_line)}</em></p>"
    new, n = EFFORT_RE.subn(lambda _: para, desc or "", count=1)
    return new if n else (desc or "") + para


def tags_for(project: str, it: dict) -> str:
    return "; ".join([bl.idempotency_tag(project, it["key"]), *(it.get("tags") or [])])


def existing_targets(relations: list | None, rel: str) -> set[int]:
    out = set()
    for r in relations or []:
        if r.get("rel") == rel:
            m = re.search(r"/workItems/(\d+)$", r.get("url", ""), re.I)
            if m:
                out.add(int(m.group(1)))
    return out


def select(data: dict) -> tuple[list[dict], list[str]]:
    """(approved items in publish order, notes about the rest). Refs to unapproved, unpublished items are errors."""
    notes, chosen = [], []
    for it in data["items"]:
        if bl.is_approved(it, data):
            chosen.append(it)
        elif it.get("approval"):
            notes.append(f"{it['key']}: edited after approval, skipped (approve again)")
        else:
            notes.append(f"{it['key']}: not approved, skipped")
    return bl.publish_order(chosen), notes


# ---- publisher --------------------------------------------------------------------------------

class Publisher:
    def __init__(self, data: dict, az: adolib.Az | None, apply: bool, ids_path: Path,
                 effort: dict | None = None, out=print):
        self.data, self.az, self.apply, self.ids_path, self.out = data, az, apply, ids_path, out
        self.project = data["project"]
        self.ado = data.get("ado") or {}
        loaded = adolib.load_ids(ids_path)
        self.ids: dict[str, int] = {k: v["id"] for k, v in loaded.items()}
        self.placed: dict[str, bool | None] = {k: v["placed"] for k, v in loaded.items()}
        self.effort = effort or {}
        self.board: dict = {"columns": [], "columnField": None}
        self.planned: dict[str, str] = {}  # key -> "#id" or "(new)"

    # az with the organization passed explicitly when the backlog names one
    def _az(self, *args, project=False, check=True):
        extra = []
        if self.ado.get("organization"):
            extra += ["--org", self.ado["organization"]]
        if project and self.ado.get("project"):
            extra += ["--project", self.ado["project"]]
        return self.az(*args, *extra, check=check)

    @property
    def online(self) -> bool:
        return self.az is not None

    def load_board(self) -> None:
        if not self.online:
            return
        if not (self.ado.get("project") and self.ado.get("team")):
            self.out("board: ado.project/ado.team not set, columns not checked")
            return
        self.board = adolib.read_board(self.az, self.ado["project"], self.ado["team"], self.ado.get("board", "Stories"),
                                       self.ado.get("organization"))

    def check_placement(self, items: list[dict]) -> list[str]:
        errs = []
        for it in items:
            try:
                adolib.place(self.board["columns"], it["type"], it.get("state", "New"), it.get("column"))
            except ValueError as e:
                errs.append(f"{it['key']}: {e}")
            if it.get("column") and self.online and not self.board["columnField"] and self.board["columns"]:
                errs.append(f"{it['key']}: the board's column field is unknown, cannot set column")
        return errs

    def verify_cached(self, key: str) -> int | None:
        """The id cached for key, only if that work item still exists, is not Removed, carries this
        backlog's exact idempotency tag and lives in the target project. Otherwise forget it."""
        wid = self.ids.get(key)
        if wid is None or not self.online:
            return wid
        w = self._az("boards", "work-item", "show", "--id", str(wid), check=False)
        f = (w or {}).get("fields") or {}
        tag = bl.idempotency_tag(self.project, key)
        if not w:
            why = "is gone"
        elif f.get("System.State") == "Removed":
            why = "is Removed"
        elif not adolib.has_tag(f.get("System.Tags"), tag):
            why = f"does not carry {tag} (not this backlog's item)"
        elif f.get("System.TeamProject") != self.ado.get("project"):
            why = f"is in project {f.get('System.TeamProject')!r}, not {self.ado['project']!r}"
        else:
            return int(wid)
        self.out(f"{key}: cached #{wid} {why}; ignoring it")
        del self.ids[key]
        self.placed.pop(key, None)
        return None

    def find_existing(self, it: dict) -> int | None:
        key = it["key"]
        wid = self.verify_cached(key)
        if wid is not None or not self.online:
            return wid
        tag = bl.idempotency_tag(self.project, key)
        wiql = ("SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project "
                f"AND [System.Tags] CONTAINS '{tag}' AND [System.State] <> 'Removed'")
        rows = self._az("boards", "query", "--wiql", wiql, project=True) or []
        found = sorted(int(r["id"]) for r in rows if "id" in r)
        if len(found) > 1:
            self.out(f"{key}: WARNING {len(found)} items carry {tag} (#{', #'.join(map(str, found))}); using #{found[0]}")
        return found[0] if found else None

    def save_ids(self) -> None:
        if self.apply:
            adolib.write_json(self.ids_path, {k: {"id": v, "placed": self.placed.get(k)} for k, v in self.ids.items()})

    def resolve(self, ref: str) -> int | None:
        if ref.startswith("#"):
            return int(ref[1:])
        return self.ids.get(ref)

    def create(self, it: dict) -> int | None:
        ado = self.ado
        fields = [f"System.Description={description_html(it, self.effort.get(it['key'], ''))}",
                  f"System.Tags={tags_for(self.project, it)}"]
        if it.get("acceptanceCriteria"):
            fields.append(f"Microsoft.VSTS.Common.AcceptanceCriteria={criteria_html(it['acceptanceCriteria'])}")
        if it.get("storyPoints") is not None:
            fields.append(f"Microsoft.VSTS.Scheduling.StoryPoints={it['storyPoints']}")
        args = ["boards", "work-item", "create", "--type", it["type"], "--title", it["title"], "--fields", *fields]
        for flag, f in (("--assigned-to", "assignedTo"), ("--iteration", "iteration"), ("--area", "area")):
            v = it.get(f) or ado.get(f)
            if v:
                args += [flag, v]
        if not self.apply:
            self.out(f"{it['key']}: would create {it['type']} \"{it['title']}\"")
            return None
        w = self._az(*args, project=True)
        wid = int(w["id"])
        self.ids[it["key"]] = wid
        self.placed[it["key"]] = False  # until place_item succeeds; a re-run resumes it
        self.save_ids()  # after every create: a crash never loses an id
        self.out(f"{it['key']}: created #{wid} {it['type']} \"{it['title']}\"")
        return wid

    def needs_placement(self, it: dict, wid: int) -> bool:
        """For an item that already exists: place it only if its placement never took effect.

        Placement is only ever applied to an item that is still in New (every item is created in New).
        So whatever the ids file says (placed false after a lost response, or unknown after a lost ids
        file), the current ADO state decides: still New and the target differs -> place; otherwise the
        update already landed or the team has moved the item on, so it is left alone and marked placed.
        """
        if self.placed.get(it["key"]) is True:
            return False
        state, column = it.get("state", "New"), it.get("column")
        if state == "New" and not column:
            return False
        if not self.online:
            return self.placed.get(it["key"]) is False
        w = self._az("boards", "work-item", "show", "--id", str(wid), check=False)
        f = (w or {}).get("fields") or {}
        if f.get("System.State") != "New":
            return False
        return state != "New" or (column is not None and f.get("System.BoardColumn") != column)

    def place_item(self, it: dict, wid: int | None) -> None:
        state, column = it.get("state", "New"), it.get("column")
        if state == "New" and not column:
            self.mark_placed(it)
            return
        args = ["boards", "work-item", "update", "--id", str(wid), "--state", state]
        if column and self.board["columnField"]:
            args += ["--fields", f"{self.board['columnField']}={column}"]
        if not self.apply or wid is None:
            self.out(f"{it['key']}: would set state {state}" + (f", column {column}" if column else ""))
            return
        self._az(*args)
        self.mark_placed(it)
        self.out(f"{it['key']}: state {state}" + (f", column {column}" if column else ""))

    def mark_placed(self, it: dict) -> None:
        if self.apply and it["key"] in self.ids:
            self.placed[it["key"]] = True
            self.save_ids()

    def link(self, it: dict, wid: int | None) -> None:
        wanted = []
        if it.get("parent"):
            wanted.append(("parent", it["parent"]))
        wanted += [("predecessor", r) for r in it.get("dependsOn") or []]
        wanted += [("related", r) for r in it.get("related") or []]
        if not wanted:
            return
        rels = None
        if wid is not None and self.online:
            w = self._az("boards", "work-item", "show", "--id", str(wid), "--expand", "relations", check=False)
            rels = (w or {}).get("relations") or []
        for kind, ref in wanted:
            target = self.resolve(ref)
            if wid is not None and target is not None and target in existing_targets(rels, REL[kind]):
                continue
            label = f"#{target}" if target else f"{ref} (new)"
            if not self.apply or wid is None or target is None:
                self.out(f"{it['key']}: would link {kind} -> {label}")
                continue
            self._az("boards", "work-item", "relation", "add", "--id", str(wid),
                     "--relation-type", kind, "--target-id", str(target))
            self.out(f"{it['key']}: linked {kind} -> #{target}")

    def run(self) -> int:
        problems = bl.target_problems(self.data)
        if problems:
            self.out("refused: " + "; ".join(problems))
            return 2
        items, notes = select(self.data)
        for n in notes:
            self.out(n)
        if not items:
            self.out("nothing approved to publish")
            return 1
        keys = {i["key"] for i in items}
        earlier = {r for it in items for r in bl.refs(it) if not r.startswith("#") and r not in keys}
        verified = {r for r in earlier if self.verify_cached(r) is not None}
        missing = [f"{it['key']} -> {r}" for it in items for r in bl.refs(it) if r in earlier - verified]
        if missing:
            self.out("refused: these items point at items that are neither approved now nor published before: "
                     + ", ".join(missing))
            return 2
        self.load_board()
        errs = self.check_placement(items)
        if errs:
            self.out("refused, board placement:\n  " + "\n  ".join(errs))
            return 2
        mode = "APPLY" if self.apply else ("DRY RUN" + ("" if self.online else ", offline (no ADO reads)"))
        self.out(f"{mode}: {len(items)} approved item(s) for {self.ado.get('organization', '(default org)')} "
                 f"/ {self.ado.get('project', '(default project)')}")
        created = reused = 0
        resolved: dict[str, int | None] = {}
        for it in items:
            wid = self.find_existing(it)
            if wid is not None:
                reused += 1
                self.ids[it["key"]] = wid
                self.out(f"{it['key']}: exists as #{wid}, not created again")
                if self.needs_placement(it, wid):
                    self.place_item(it, wid)
                elif self.placed.get(it["key"]) is not True:
                    self.mark_placed(it)
                if self.effort.get(it["key"]) and self.online:
                    self.update_effort(it, wid)
            else:
                wid = self.create(it)
                created += 1
                self.place_item(it, wid)
            resolved[it["key"]] = wid
        self.save_ids()
        for it in items:
            self.link(it, resolved[it["key"]])
        verb = "created" if self.apply else "to create"
        self.out(f"done: {created} {verb}, {reused} already in ADO. ids file: {self.ids_path}")
        return 0

    def update_effort(self, it: dict, wid: int) -> None:
        w = self._az("boards", "work-item", "show", "--id", str(wid))
        desc = (w.get("fields") or {}).get("System.Description", "")
        new = with_effort(desc, self.effort[it["key"]])
        if new == desc:
            return
        if not self.apply:
            self.out(f"{it['key']}: would update the effort line")
            return
        self._az("boards", "work-item", "update", "--id", str(wid), "--fields", f"System.Description={new}")
        self.out(f"{it['key']}: effort line updated")


def effort_lines(mapping_path: Path) -> dict[str, str]:
    import effort
    import plans
    m = plans.load_mapping(mapping_path)
    agg, asof = effort.compute(m)
    note = (m.get("effort") or {}).get("note", "")
    return {k: effort.line(agg.get(k), asof, note) for k in m["items"] if agg.get(k)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("backlog", type=Path)
    ap.add_argument("--apply", action="store_true", help="write to ADO (default: dry run)")
    ap.add_argument("--offline", action="store_true", help="dry run without calling az at all")
    ap.add_argument("--effort", type=Path, metavar="MAPPING", help="add the effort line (see effort.py)")
    ap.add_argument("--ids-file", type=Path, help="override ~/.prototype-to-backlog/<project>/ids-<hash>.json")
    a = ap.parse_args(argv)
    if a.apply and a.offline:
        ap.error("--apply needs ADO; drop --offline")
    try:
        data = bl.load(a.backlog)
    except (OSError, ValueError) as e:
        print(f"cannot read {a.backlog}: {e}", file=sys.stderr)
        return 2
    errs = bl.validate(data)
    if errs:
        print("invalid backlog:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2
    az = None
    if not a.offline:
        az = adolib.Az()
        if not az.available:
            if a.apply:
                print("az is not installed. Run scripts/ado_login.py first.", file=sys.stderr)
                return 3
            print("az not found: offline dry run (no ADO reads). Run scripts/ado_login.py to check against ADO.")
            az = None
    ado = data.get("ado") or {}
    ids_path = a.ids_file or adolib.ids_path(data["project"], ado.get("organization"), ado.get("project"))
    try:
        eff = effort_lines(a.effort) if a.effort else {}
        return Publisher(data, az, a.apply, ids_path, eff).run()
    except adolib.AzError as e:
        print(str(e), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
