"""Shared helpers for the ADO scripts: run az safely, read the team board, place items by state + column.

Standard library only; runs on Windows and macOS. az is found with shutil.which and always called
with an argument list, never a shell string. Tokens stay in az's own cache: nothing here reads them.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

STATE_ROOT = Path.home() / ".prototype-to-backlog"

# States publish and sync never set: Closed means "verified in production" on most boards, and a
# board without a column for a state hides the item (the Resolved lesson).
FORBIDDEN_STATES = {"Closed", "Removed", "Done"}

# cmd.exe metacharacters. Only relevant when az can only be reached through az.cmd on Windows.
_CMD_META = re.compile(r'[&|<>^%!"\r\n]')


class AzError(RuntimeError):
    pass


def project_slug(name: str) -> str:
    """A folder-safe name for a project: lower case, letters/digits/dashes only."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "default"


def state_dir(project: str) -> Path:
    """Where a project's ids file and drafts live. Created on first write, not here (dry runs write nothing)."""
    return STATE_ROOT / project_slug(project)


def ids_path(project: str, org: str | None, ado_project: str | None) -> Path:
    """The ids file for one backlog in one ADO destination.

    The folder is readable (slug); the file name hashes the exact backlog project name plus the
    organization and ADO project, so two backlogs whose names slug alike, or one backlog published to
    two destinations, never share ids.
    """
    ident = hashlib.sha256(f"{project}\n{org or ''}\n{ado_project or ''}".encode("utf-8")).hexdigest()[:10]
    return state_dir(project) / f"ids-{ident}.json"


def has_tag(tags: str | None, tag: str) -> bool:
    """Exact tag match in an ADO System.Tags value ('a; b; c')."""
    return tag in [t.strip() for t in (tags or "").split(";")]


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def az_command() -> list[str] | None:
    """The argv prefix that runs az, or None when az is not installed.

    On Windows az is az.cmd, and arguments passed through a .cmd file are re-parsed by cmd.exe
    (& | % ^ break titles). The Azure CLI installer ships its own python.exe next to az.cmd's
    folder, so call that directly when it is there: no cmd.exe in between.
    """
    found = shutil.which("az")
    if not found:
        return None
    if _is_cmd(found):
        py = os.path.join(os.path.dirname(os.path.dirname(found)), "python.exe")
        if os.path.isfile(py):
            return [py, "-IBm", "azure.cli"]
    return [found]


def _is_cmd(path: str) -> bool:
    # os.path, not pathlib: the decision is about the running OS's az.cmd shim.
    return os.name == "nt" and os.path.splitext(path)[1].lower() in (".cmd", ".bat")


class Az:
    """Runs az commands. `runner` is injectable so tests never touch the network."""

    def __init__(self, prefix: list[str] | None = None, runner=None):
        self.prefix = prefix if prefix is not None else az_command()
        self.runner = runner or self._run

    @property
    def available(self) -> bool:
        return bool(self.prefix)

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", AZURE_CORE_ONLY_SHOW_ERRORS="true")
        return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)

    def __call__(self, *args: str, check: bool = True):
        if not self.prefix:
            raise AzError("az is not installed (run scripts/ado_login.py)")
        if _is_cmd(self.prefix[0]):
            bad = [a for a in args if _CMD_META.search(a)]
            if bad:
                raise AzError("az is only reachable through az.cmd here, and cmd.exe would mangle an argument "
                              f"containing & | < > ^ % ! or a quote: {bad[0][:60]!r}. Reinstall the Azure CLI with the "
                              "MSI/winget installer (it ships python.exe), or remove the character.")
        r = self.runner([*self.prefix, *args, "-o", "json"])
        if r.returncode:
            if not check:
                return None
            raise AzError(f"az {' '.join(args[:3])} failed: {(r.stderr or '').strip()[-800:]}")
        out = (r.stdout or "").strip()
        return json.loads(out) if out else None


# ---- board -------------------------------------------------------------------------------------

def read_board(az: Az, project: str, team: str, board: str, org: str | None = None) -> dict:
    """Columns and the board's Kanban column field. Both come from the team's own board settings,
    in the same organization the items are written to (not az's default)."""
    common = (["--org", org] if org else []) + ["--route-parameters", f"project={project}", f"team={team}"]
    cols = az("devops", "invoke", "--area", "work", "--resource", "columns",
              *common, f"board={board}", "--api-version", "7.1")
    info = az("devops", "invoke", "--area", "work", "--resource", "boards",
              *common, f"id={board}", "--api-version", "7.1")
    field = ((info or {}).get("fields") or {}).get("columnField") or {}
    return {"columns": (cols or {}).get("value", []), "columnField": field.get("referenceName")}


def place(columns: list[dict], wtype: str, state: str, column: str | None = None,
          allow_done: bool = False) -> str | None:
    """Return the board column for (type, state, wanted column), or raise ValueError.

    - A state in FORBIDDEN_STATES is refused, except Closed/Done with allow_done (a team whose board
      maps its done column to "merged"); Removed is always refused.
    - With a column: it must exist and map this type to this state.
    - Without one: the first column that maps the type to the state.
    - A type the board does not show at all (e.g. Feature on the Stories board) gets no column.
    - A state the board has no column for is refused: the item would vanish from the board.
    """
    if state in FORBIDDEN_STATES and not (allow_done and state != "Removed"):
        raise ValueError(f"state {state!r} is never set by this tool")
    shown = [c for c in columns if wtype in (c.get("stateMappings") or {})]
    if not shown:
        return None
    if column:
        for c in shown:
            if c.get("name") == column:
                mapped = c["stateMappings"][wtype]
                if mapped != state:
                    raise ValueError(f"column {column!r} holds {wtype} in state {mapped!r}, not {state!r}")
                return column
        raise ValueError(f"the board has no column {column!r} for {wtype} "
                         f"(columns: {', '.join(c.get('name', '?') for c in shown)})")
    for c in shown:
        if c["stateMappings"][wtype] == state:
            return c.get("name")
    raise ValueError(f"no board column shows {wtype} in state {state!r}; the item would drop off the board")


def eprint(*a) -> None:
    print(*a, file=sys.stderr)
