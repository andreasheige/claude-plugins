"""Optional effort line per ticket: wall-clock hours and Claude tokens spent on its plan items.

Each ticked plan item ends at the newest commit (hash in the item text) after `since`. Items are
ordered by that time; an item owns the time and tokens between the previous item's end and its own.
Tokens come from Claude Code's transcripts for the repo: ~/.claude/projects/<repo path, non
alphanumerics as '-'>/**/*.jsonl. Approximate by design: parallel work is attributed to whichever
item finished.

  python effort.py <mapping.json>          # prints the line per backlog key
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

import plans

HASH_RE = re.compile(r"\b[0-9a-f]{7,40}\b")


def claude_project_dir(repo: Path, home: Path | None = None) -> Path:
    return (home or Path.home()) / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo))


def parse_ts(s: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def parse_usage(lines) -> list[tuple[dt.datetime, int, int, int]]:
    """[(timestamp, input incl. cache, output, cache read)] from transcript lines, one per API message."""
    seen, out = set(), []
    for line in lines:
        if '"usage"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        m = d.get("message") or {}
        u, ts = m.get("usage"), d.get("timestamp")
        if not isinstance(u, dict) or not ts:
            continue
        k = (m.get("id"), d.get("requestId"))
        if k in seen:
            continue
        seen.add(k)
        cr = u.get("cache_read_input_tokens", 0) or 0
        inp = (u.get("input_tokens", 0) or 0) + (u.get("cache_creation_input_tokens", 0) or 0) + cr
        out.append((parse_ts(ts), inp, u.get("output_tokens", 0) or 0, cr))
    out.sort()
    return out


def aggregate(done_items, usage, start: dt.datetime) -> dict[str, dict]:
    """done_items: [(end time, key, item id)]. Returns {key: {h, in, out, cr, items}}."""
    agg: dict[str, dict] = {}
    prev = start
    for end, key, iid in sorted(done_items):
        a = agg.setdefault(key, {"h": 0.0, "in": 0, "out": 0, "cr": 0, "items": []})
        a["items"].append(iid)
        if end <= prev:  # finished in the same instant as the previous item: no extra time
            continue
        a["h"] += (end - prev).total_seconds() / 3600
        for ts, i, o, cr in usage:
            if prev < ts <= end:
                a["in"] += i
                a["out"] += o
                a["cr"] += cr
        prev = end
    return agg


def line(a: dict | None, asof: dt.datetime, note: str = "", label: str = "Effort") -> str:
    if not a:
        return ""
    return (f"{label} so far (AI run, as of {asof:%Y-%m-%d %H:%M}): {a['h']:.1f} h wall-clock, "
            f"{a['in'] / 1e6:.1f} M input tokens ({a['cr'] / 1e6:.1f} M cached), {a['out'] / 1e6:.2f} M output tokens."
            + (f" {note}" if note else ""))


def total_line(agg: dict, asof: dt.datetime, note: str = "") -> str:
    s = {k: sum(a[k] for a in agg.values()) for k in ("h", "in", "out", "cr")}
    return line(s, asof, note, "Total effort") if agg else ""


def commit_time(repo: Path, h: str) -> dt.datetime | None:
    r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%aI", h],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return parse_ts(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def compute(mapping: dict, commit_time=commit_time, usage_lines=None):
    """(agg, asof) for a loaded mapping with an `effort` block {repo, since, note?}."""
    eff = mapping.get("effort") or {}
    if not eff.get("repo") or not eff.get("since"):
        raise ValueError("mapping needs effort.repo and effort.since for the effort line")
    repo = Path(eff["repo"]).expanduser()
    since = parse_ts(eff["since"])
    cache: dict[str, dt.datetime | None] = {}
    done = []
    for key, items in plans.collect(mapping).items():
        for mark, iid, body in items:
            if mark != "x":
                continue
            ts = []
            for h in set(HASH_RE.findall(body)):
                if h not in cache:
                    cache[h] = commit_time(repo, h)
                if cache[h] and cache[h] > since:
                    ts.append(cache[h])
            if ts:
                done.append((max(ts), key, iid))
    if usage_lines is None:
        d = claude_project_dir(repo)
        usage_lines = (ln for f in sorted(d.rglob("*.jsonl")) if f.stat().st_mtime >= since.timestamp()
                       for ln in f.open(encoding="utf-8", errors="ignore"))
    usage = parse_usage(usage_lines)
    agg = aggregate(done, usage, since)
    asof = max((e for e, _, _ in done), default=since)
    return agg, asof


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    m = plans.load_mapping(Path(argv[0]))
    agg, asof = compute(m)
    note = (m.get("effort") or {}).get("note", "")
    for k in m["items"]:
        print(f"{k}: {line(agg.get(k), asof, note) or '(no finished items)'}")
    print(total_line(agg, asof, note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
