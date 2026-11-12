"""Read plan checklists and map their items to backlog keys (used by ado_sync_state.py and effort.py).

A plan is markdown with checklist lines `- [x] <id> ...` (`[ ]` open, `[~]` in progress, an optional
`@agent` before the id). The mapping file (JSON, see references/ado.md) says which plan item ids
belong to which backlog key, with fnmatch patterns; the first key whose pattern matches wins.
A pattern `stem:pattern` only matches items in the plan file with that stem.
"""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

ITEM_RE = re.compile(r"^- \[(.)\] (?:@\S+ )?(\S+)(.*?)(?=^- \[|^#|\Z)", re.M | re.S)


def parse_plan(text: str) -> list[tuple[str, str, str]]:
    """[(mark, id, body)] for every checklist item. body is the rest of the item, continuation lines included."""
    return [(m.group(1), m.group(2), m.group(3)) for m in ITEM_RE.finditer(text)]


def key_for(patterns: dict[str, list[str]], stem: str, iid: str) -> str | None:
    for key, pats in patterns.items():
        for p in pats:
            if ":" in p:
                pstem, p = p.split(":", 1)
                if pstem != stem:
                    continue
            if fnmatch.fnmatchcase(iid, p):
                return key
    return None


def load_mapping(path: Path) -> dict:
    path = Path(path)
    m = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(m.get("items"), dict) or not m.get("plans"):
        raise ValueError("mapping needs 'plans' (list of files) and 'items' ({key: [patterns]})")
    m["_plans"] = [(path.parent / p).resolve() if not Path(p).is_absolute() else Path(p) for p in m["plans"]]
    return m


def collect(mapping: dict, read=lambda p: Path(p).read_text(encoding="utf-8")) -> dict[str, list[tuple[str, str, str]]]:
    """{backlog key: [(mark, plan item id, body)]} across every plan in the mapping."""
    out: dict[str, list] = {}
    for p in mapping["_plans"]:
        stem = Path(p).stem
        for mark, iid, body in parse_plan(read(p)):
            k = key_for(mapping["items"], stem, iid)
            if k:
                out.setdefault(k, []).append((mark, iid, body))
    return out


DEFAULT_RULES = [
    {"when": "none", "state": "New"},
    {"when": "some", "state": "Active"},
    {"when": "all", "state": "Active"},
]


def target(rules: list[dict], done: int, total: int) -> tuple[str, str | None]:
    """(state, column or None) for a key with `done` of `total` plan items ticked."""
    when = "none" if done == 0 or total == 0 else ("all" if done == total else "some")
    for r in rules:
        if r.get("when") == when:
            return r["state"], r.get("column")
    raise ValueError(f"mapping has no rule for when={when!r}")
