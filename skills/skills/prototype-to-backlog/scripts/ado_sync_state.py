"""Set each published item's state and board column from plan checklists. Dry run unless --apply.

  python ado_sync_state.py <mapping.json> --project NAME [--apply] [--effort]

The mapping (references/ado.md) lists the plan files, which plan items belong to which backlog key,
and the rules: none / some / all items ticked -> state (+ column). Placement is state + column on the
team's own board, read from ADO: a state with no column on the board is refused (it would vanish,
as Resolved did on a board without a Resolved column). Closed/Done only when the mapping sets
"allowDone": true (a board whose done column means merged); Removed never.
--effort also rewrites the effort line in each description.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import adolib
import backlog
import plans


def decide(rules, marks: list[str], columns: list[dict], wtype: str, allow_done: bool):
    """(state, column, note) for one item. Pure; raises ValueError on a placement the board can't show."""
    done = sum(1 for m in marks if m == "x")
    state, column = plans.target(rules, done, len(marks))
    col = adolib.place(columns, wtype, state, column, allow_done=allow_done)
    return state, (col if column else None), f"{done}/{len(marks)} done"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mapping", type=Path)
    ap.add_argument("--project", required=True, help="backlog project name, exactly as in backlog.json (selects the ids file)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--effort", action="store_true", help="also rewrite the effort line")
    ap.add_argument("--ids-file", type=Path)
    a = ap.parse_args(argv)
    m = plans.load_mapping(a.mapping)
    ado = m.get("ado") or {}
    ids_path = a.ids_file or adolib.ids_path(a.project, ado.get("organization"), ado.get("project"))
    if not ids_path.is_file():
        print(f"no ids file at {ids_path}: publish first", file=sys.stderr)
        return 2
    ids = adolib.read_json(ids_path)
    az = adolib.Az()
    if not az.available:
        print("az is not installed. Run scripts/ado_login.py first.", file=sys.stderr)
        return 3
    org = ["--org", ado["organization"]] if ado.get("organization") else []
    try:
        board = {"columns": [], "columnField": None}
        if ado.get("project") and ado.get("team"):
            board = adolib.read_board(az, ado["project"], ado["team"], ado.get("board", "Stories"),
                                      ado.get("organization"))
        else:
            print("mapping has no ado.project/ado.team: board columns not checked, states only")
        items = plans.collect(m)
        lines = {}
        if a.effort:
            import effort
            agg, asof = effort.compute(m)
            note = (m.get("effort") or {}).get("note", "")
            lines = {k: effort.line(agg.get(k), asof, note) for k in m["items"]}
        rules = m.get("rules") or plans.DEFAULT_RULES
        rc = 0
        for key in m["items"]:
            wid = ids.get(key)
            if wid is None:
                print(f"{key}: not in the ids file, skipped")
                continue
            f = az("boards", "work-item", "show", "--id", str(wid), *org)["fields"]
            tag = backlog.idempotency_tag(a.project, key)
            if not adolib.has_tag(f.get("System.Tags"), tag):
                print(f"#{wid} {key}: refused: it does not carry {tag}, so it is not this backlog's item")
                rc = 2
                continue
            cur, curcol, wtype = f["System.State"], f.get("System.BoardColumn"), f["System.WorkItemType"]
            marks = [mk for mk, _, _ in items.get(key, [])]
            try:
                state, col, note = decide(rules, marks, board["columns"], wtype, bool(m.get("allowDone")))
            except ValueError as e:
                print(f"#{wid} {key}: refused: {e}")
                rc = 2
                continue
            args = []
            if cur != state:
                args += ["--state", state]
            fields, eff = [], False
            if col and curcol != col and board["columnField"]:
                fields.append(f"{board['columnField']}={col}")
            if lines.get(key):
                import ado_publish
                desc = f.get("System.Description", "")
                new = ado_publish.with_effort(desc, lines[key])
                if new != desc:
                    fields.append(f"System.Description={new}")
                    eff = True
            if fields:
                args += ["--fields", *fields]
            if not args:
                print(f"#{wid} {key}: {cur}/{curcol} unchanged ({note})")
                continue
            if a.apply:
                az("boards", "work-item", "update", "--id", str(wid), *args, *org)
            print(f"#{wid} {key}: {cur}/{curcol} -> {state}/{col or curcol}"
                  f"{'' if a.apply else ' (dry run)'} ({note}{', effort line' if eff else ''})")
        return rc
    except adolib.AzError as e:
        print(str(e), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
