"""Backlog file: validate, Definition-of-Ready pre-check, render for approval, record approval.

  python backlog.py validate <backlog.json>
  python backlog.py ready    <backlog.json>          # which stories may skip the refinement swarm
  python backlog.py render   <backlog.json> [-o backlog.md]
  python backlog.py approve  <backlog.json> --by NAME (--all | --ids S1,S2) [--note TEXT]
  python backlog.py status   <backlog.json>

Exit codes: 0 ok, 1 nothing to do / not ready, 2 invalid input.
The rules mirror references/backlog.schema.json; standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

TYPES = ("Epic", "Feature", "User Story", "Task", "Bug")
KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
REF_RE = re.compile(r"^(#[0-9]+|[A-Za-z][A-Za-z0-9_.-]*)$")
TOP_KEYS = {"version", "project", "language", "source", "ado", "items", "approvals", "$schema"}
ITEM_KEYS = {"key", "type", "title", "description", "acceptanceCriteria", "parent", "dependsOn", "related",
             "screenshots", "tags", "state", "column", "assignedTo", "area", "iteration", "storyPoints",
             "refinement", "approval"}
# Item fields that end up in ADO. The approval hash covers these plus inherited defaults and the
# target (see effective), so any change after approval voids it.
PUBLISHED = ("type", "title", "description", "acceptanceCriteria", "parent", "dependsOn", "related",
             "screenshots", "tags", "state", "column", "assignedTo", "area", "iteration", "storyPoints")
FORBIDDEN_STATES = {"Closed", "Removed", "Done"}


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---- validation -------------------------------------------------------------------------------

def validate(data) -> list[str]:
    """Return a list of problems; empty means valid."""
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["backlog must be a JSON object"]
    for k in sorted(set(data) - TOP_KEYS):
        errs.append(f"unknown top-level field {k!r}")
    if data.get("version") != 1:
        errs.append("version must be 1")
    if not isinstance(data.get("project"), str) or not data.get("project", "").strip():
        errs.append("project must be a non-empty string")
    org = (data.get("ado") or {}).get("organization")
    if org is not None and not str(org).startswith("https://"):
        errs.append("ado.organization must start with https://")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return errs + ["items must be a non-empty list"]
    keys: dict[str, dict] = {}
    for n, it in enumerate(items):
        where = f"items[{n}]"
        if not isinstance(it, dict):
            errs.append(f"{where} must be an object")
            continue
        key = it.get("key")
        if not isinstance(key, str) or not KEY_RE.match(key):
            errs.append(f"{where}.key must match {KEY_RE.pattern}")
        elif key in keys:
            errs.append(f"duplicate key {key!r}")
        else:
            keys[key] = it
            where = key
        for k in sorted(set(it) - ITEM_KEYS):
            errs.append(f"{where}: unknown field {k!r}")
        if it.get("type") not in TYPES:
            errs.append(f"{where}: type must be one of {', '.join(TYPES)}")
        title = it.get("title")
        if not isinstance(title, str) or not title.strip():
            errs.append(f"{where}: title is required")
        elif len(title) > 255:
            errs.append(f"{where}: title is longer than 255 characters")
        if it.get("state") in FORBIDDEN_STATES:
            errs.append(f"{where}: state {it['state']!r} is never set by this tool")
        for f in ("description", "state", "column", "assignedTo", "area", "iteration"):
            if f in it and not isinstance(it[f], str):
                errs.append(f"{where}: {f} must be a string")
        for c in it.get("acceptanceCriteria") or []:
            if isinstance(c, str):
                if not c.strip():
                    errs.append(f"{where}: empty acceptance criterion")
            elif isinstance(c, dict):
                if set(c) != {"given", "when", "then"} or not all(isinstance(v, str) and v.strip() for v in c.values()):
                    errs.append(f"{where}: a structured criterion needs exactly non-empty given/when/then")
            else:
                errs.append(f"{where}: acceptance criteria are strings or given/when/then objects")
        for t in it.get("tags") or []:
            if not isinstance(t, str) or ";" in t or not t.strip():
                errs.append(f"{where}: tag {t!r} must be a non-empty string without ';'")
        sp = it.get("storyPoints")
        if sp is not None and (not isinstance(sp, (int, float)) or isinstance(sp, bool) or sp < 0):
            errs.append(f"{where}: storyPoints must be a number >= 0")
    # references
    for key, it in keys.items():
        for ref in refs(it):
            if not isinstance(ref, str) or not REF_RE.match(ref):
                errs.append(f"{key}: bad reference {ref!r}")
            elif not ref.startswith("#") and ref not in keys:
                errs.append(f"{key}: refers to unknown item {ref!r}")
            elif ref == key:
                errs.append(f"{key}: refers to itself")
    if not errs:
        cyc = find_cycle(keys)
        if cyc:
            errs.append("cycle in parent/dependsOn: " + " -> ".join(cyc))
    return errs


def refs(it: dict) -> list:
    out = [it["parent"]] if it.get("parent") else []
    return out + list(it.get("dependsOn") or []) + list(it.get("related") or [])


def find_cycle(keys: dict[str, dict]) -> list[str] | None:
    """parent and dependsOn must form a DAG (related links may go both ways)."""
    edges = {k: [r for r in ([it["parent"]] if it.get("parent") else []) + list(it.get("dependsOn") or [])
                 if not r.startswith("#")] for k, it in keys.items()}
    color: dict[str, int] = {}

    def visit(k, path):
        color[k] = 1
        for r in edges.get(k, []):
            if color.get(r) == 1:
                return path + [k, r]
            if not color.get(r):
                found = visit(r, path + [k])
                if found:
                    return found
        color[k] = 2
        return None

    for k in edges:
        if not color.get(k):
            found = visit(k, [])
            if found:
                return found[found.index(found[-1]):]
    return None


def publish_order(items: list[dict]) -> list[dict]:
    """Parents and predecessors before the items that point at them; otherwise file order."""
    by_key = {it["key"]: it for it in items}
    done: set[str] = set()
    out: list[dict] = []

    def add(it):
        if it["key"] in done:
            return
        done.add(it["key"])
        for r in ([it["parent"]] if it.get("parent") else []) + list(it.get("dependsOn") or []):
            if r in by_key:
                add(by_key[r])
        out.append(it)

    for it in items:
        add(it)
    return out


# ---- keys and hashes ---------------------------------------------------------------------------

def idempotency_tag(project: str, key: str) -> str:
    """The tag that identifies an item in ADO across runs: stable for project + key, not the title.

    Titles change during refinement; the key does not. The tag is what publish searches for before
    creating anything, so a second run (or a lost ids file) never makes a duplicate.
    """
    h = hashlib.sha256(f"{project.strip().lower()}\n{key}".encode("utf-8")).hexdigest()[:10]
    return f"ptb-{h}"


# Item fields that fall back to the backlog's `ado` block, and the publishing target.
INHERITED = ("area", "iteration", "assignedTo")
TARGET = ("organization", "project", "team", "board")


def effective(it: dict, data: dict) -> dict:
    """What publishing this item actually sends, and where: item fields with inherited defaults
    resolved, the ADO target, and the item's identity (backlog project + key)."""
    ado = data.get("ado") or {}
    body = {f: it.get(f) for f in PUBLISHED}
    for f in INHERITED:
        body[f] = it.get(f) or ado.get(f)
    body["_target"] = {t: ado.get(t) for t in TARGET}
    body["_identity"] = {"project": data.get("project"), "key": it.get("key")}
    return body


def content_hash(it: dict, data: dict) -> str:
    """Hash of the effective payload. Changing the item, an inherited default or the target voids approval."""
    canon = json.dumps(effective(it, data), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def is_approved(it: dict, data: dict) -> bool:
    a = it.get("approval") or {}
    return bool(a.get("hash")) and a["hash"] == content_hash(it, data)


def target_problems(data: dict) -> list[str]:
    """Approval and publishing need an explicit destination: az's own defaults must never choose it."""
    ado = data.get("ado") or {}
    return [f"ado.{f} is required to approve or publish (az defaults never pick the destination)"
            for f in ("organization", "project") if not ado.get(f)]


def approve(data: dict, by: str, ids: list[str] | None, note: str = "", now: dt.datetime | None = None) -> list[str]:
    """Mark items approved (all when ids is None). Returns the keys approved.
    Unknown ids raise KeyError; a backlog without an explicit ADO destination raises ValueError."""
    problems = target_problems(data)
    if problems:
        raise ValueError("; ".join(problems))
    known = {it["key"]: it for it in data["items"]}
    if ids is not None:
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise KeyError(f"unknown ids: {', '.join(unknown)}")
    chosen = list(known) if ids is None else ids
    at = (now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds")
    for k in chosen:
        known[k]["approval"] = {"at": at, "by": by, "hash": content_hash(known[k], data)}
    entry = {"at": at, "by": by, "scope": "all" if ids is None else "ids", "ids": chosen}
    if note:
        entry["note"] = note
    data.setdefault("approvals", []).append(entry)
    return chosen


# ---- Definition-of-Ready pre-check ------------------------------------------------------------

_STORY_SENTENCE = (
    re.compile(r"\bas an?\b.+\bi want\b.+\bso that\b", re.I | re.S),
    re.compile(r"\bsom\b.+\bvill jag\b.+\bså att\b", re.I | re.S),
)


def ready_problems(it: dict, has_prototype: bool = True) -> list[str]:
    """A cheap, deterministic check. A story with no problems skips the persona swarm.

    It does not judge quality; it only catches the gaps every persona would flag anyway.
    """
    if it.get("type") != "User Story":
        return []
    p = []
    desc = it.get("description") or ""
    if not any(r.search(desc) for r in _STORY_SENTENCE):
        p.append("no user-story sentence (As a … I want … so that … / Som … vill jag … så att …)")
    ac = it.get("acceptanceCriteria") or []
    if len(ac) < 2:
        p.append("fewer than 2 acceptance criteria")
    if any(not isinstance(c, dict) for c in ac):
        p.append("criteria not all Given/When/Then")
    if not it.get("parent"):
        p.append("no parent feature/epic")
    if has_prototype and not it.get("screenshots"):
        p.append("no screenshot reference")
    if len(it.get("title", "")) > 80:
        p.append("title longer than 80 characters (probably more than one thing)")
    if len(ac) > 8:
        p.append("more than 8 criteria (probably too big)")
    return p


# ---- rendering --------------------------------------------------------------------------------

def criterion_text(c) -> str:
    if isinstance(c, dict):
        return f"**Given** {c['given']} **when** {c['when']} **then** {c['then']}"
    return str(c)


def render_markdown(data: dict) -> str:
    """The page the human approves. Every published field is shown; nothing is hidden."""
    lines = [f"# Backlog: {data['project']}", ""]
    src = data.get("source") or {}
    if src:
        lines += [" · ".join(f"{k}: `{v}`" for k, v in src.items()), ""]
    ado = data.get("ado") or {}
    if ado:
        lines += ["Target: " + " · ".join(f"{k} `{v}`" for k, v in ado.items()), ""]
    approved = sum(1 for it in data["items"] if is_approved(it, data))
    lines += [f"{len(data['items'])} items, {approved} approved.",
              "", "To approve, answer with **all**, a list of keys (e.g. `S1, S3`), or the edits you want first.", ""]
    for it in data["items"]:
        mark = "approved" if is_approved(it, data) else ("edited after approval" if it.get("approval") else "not approved")
        lines.append(f"## {it['key']} · {it['type']}: {it['title']}  ({mark})")
        meta = []
        for f, label in (("parent", "parent"), ("dependsOn", "depends on"), ("related", "related"),
                         ("state", "state"), ("column", "column"), ("assignedTo", "assigned"),
                         ("iteration", "iteration"), ("area", "area"), ("storyPoints", "points"), ("tags", "tags")):
            v = it.get(f)
            if v not in (None, "", []):
                meta.append(f"{label}: {', '.join(map(str, v)) if isinstance(v, list) else v}")
        if meta:
            lines += ["", "*" + " · ".join(meta) + "*"]
        if it.get("description"):
            lines += ["", it["description"].strip()]
        if it.get("acceptanceCriteria"):
            lines += ["", "Acceptance criteria:"] + [f"- {criterion_text(c)}" for c in it["acceptanceCriteria"]]
        if it.get("screenshots"):
            lines += ["", "Screens: " + ", ".join(f"`{s}`" for s in it["screenshots"])]
        ref = it.get("refinement") or {}
        if ref:
            fixes = [v for v in ref.get("verdicts", []) if v.get("verdict") == "fix"]
            lines += ["", f"Refinement: {ref.get('status', '?')}, {ref.get('rounds', 0)} round(s)"
                      + (f", {len(fixes)} fix verdict(s) merged" if fixes else "")]
        lines.append("")
    for a in data.get("approvals") or []:
        lines.append(f"- Approved {a['at']} by {a['by']}: {a['scope']} ({', '.join(a['ids'])})"
                     + (f". {a['note']}" if a.get("note") else ""))
    return "\n".join(lines).rstrip() + "\n"


# ---- CLI --------------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "ready", "render", "approve", "status"):
        p = sub.add_parser(name)
        p.add_argument("backlog", type=Path)
        if name == "render":
            p.add_argument("-o", "--out", type=Path)
        if name == "approve":
            p.add_argument("--by", required=True)
            g = p.add_mutually_exclusive_group(required=True)
            g.add_argument("--all", action="store_true")
            g.add_argument("--ids", help="comma-separated keys")
            p.add_argument("--note", default="")
    a = ap.parse_args(argv)
    try:
        data = load(a.backlog)
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read {a.backlog}: {e}", file=sys.stderr)
        return 2
    errs = validate(data)
    if errs:
        print("invalid backlog:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2
    if a.cmd == "validate":
        print(f"ok: {len(data['items'])} items")
        return 0
    if a.cmd == "ready":
        has_proto = bool((data.get("source") or {}).get("prototype"))
        swarm = 0
        for it in data["items"]:
            if it["type"] != "User Story":
                continue
            p = ready_problems(it, has_proto)
            swarm += bool(p)
            print(f"{it['key']}: " + ("ready (skips the swarm)" if not p else "swarm: " + "; ".join(p)))
        return 1 if swarm else 0
    if a.cmd == "render":
        md = render_markdown(data)
        out = a.out or a.backlog.with_suffix(".md")
        out.write_text(md, encoding="utf-8")
        print(f"wrote {out}")
        return 0
    if a.cmd == "approve":
        ids = None if a.all else [s.strip() for s in a.ids.split(",") if s.strip()]
        try:
            chosen = approve(data, a.by, ids, a.note)
        except (KeyError, ValueError) as e:
            print(e.args[0], file=sys.stderr)
            return 2
        save(a.backlog, data)
        print(f"approved {len(chosen)}: {', '.join(chosen)}")
        return 0
    # status
    for it in data["items"]:
        st = "approved" if is_approved(it, data) else ("EDITED after approval" if it.get("approval") else "not approved")
        print(f"{it['key']:<10} {it['type']:<11} {st:<22} {it['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
