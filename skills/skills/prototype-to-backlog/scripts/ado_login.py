"""Sign in to Azure DevOps through the browser, for people who have never used az.

  python ado_login.py --org https://dev.azure.com/<org> --project <project> [--tenant <tenant id or domain>]
  python ado_login.py --check-only --org ... --project ...     # no sign-in, only report what is missing

Steps, each skipped when already done:
  1. az installed? If not, print the installer command for this OS and exit 4. Nothing is installed
     without the user: run the printed command (or let the agent run it after asking), then run this again.
  2. The azure-devops extension (az's own extension, added with az).
  3. Signed in? If not: az login --allow-no-subscriptions [--tenant T]. az opens the browser; the user
     signs in there. --allow-no-subscriptions because PM/design/QA usually have ADO but no Azure subscription.
  4. az devops configure --defaults organization=... project=...
  5. A read-only check: count the work items assigned to the user. Nothing is written to ADO.

The token stays in az's own cache. This script never reads, prints or stores it.
Exit: 0 ready, 1 a step failed, 2 bad arguments, 4 az missing.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys

import adolib

INSTALL = {
    "Darwin": "brew install azure-cli",
    "Windows": "winget install -e --id Microsoft.AzureCLI",
    "Linux": "see https://learn.microsoft.com/cli/azure/install-azure-cli-linux",
}


def install_hint(system: str | None = None) -> str:
    return INSTALL.get(system or platform.system(), "see https://learn.microsoft.com/cli/azure/install-azure-cli")


def step(msg: str) -> None:
    print(f"- {msg}", flush=True)


def run_quiet(prefix: list[str], *args: str) -> bool:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([*prefix, *args, "-o", "none"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return r.returncode == 0


def run_interactive(prefix: list[str], *args: str) -> bool:
    """Inherit the terminal so the user sees az's own browser/sign-in messages. Output is discarded (-o none)."""
    return subprocess.run([*prefix, *args, "-o", "none"]).returncode == 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--org", required=True, help="https://dev.azure.com/<org>")
    ap.add_argument("--project", required=True)
    ap.add_argument("--tenant", help="tenant id or domain, when the account belongs to several")
    ap.add_argument("--device-code", action="store_true",
                    help="sign in with a code instead of a local browser (remote or locked-down machines)")
    ap.add_argument("--check-only", action="store_true", help="report what is missing; change nothing")
    a = ap.parse_args(argv)
    if not a.org.startswith("https://"):
        ap.error("--org must be the https://dev.azure.com/<org> URL")

    prefix = adolib.az_command()
    if not prefix:
        print("The Azure CLI (az) is not installed. It is needed once, to sign in as yourself.")
        print(f"Install it with:  {install_hint()}")
        print("Then open a new terminal and run this script again.")
        return 4
    step("az found")

    if run_quiet(prefix, "extension", "show", "--name", "azure-devops"):
        step("azure-devops extension present")
    elif a.check_only:
        step("MISSING: azure-devops extension (az extension add --name azure-devops)")
        return 1
    else:
        step("adding the azure-devops extension")
        if not run_quiet(prefix, "extension", "add", "--name", "azure-devops", "--yes"):
            print("Could not add the azure-devops extension.", file=sys.stderr)
            return 1

    if run_quiet(prefix, "account", "show"):
        step("already signed in")
    elif a.check_only:
        step("MISSING: sign-in (run without --check-only)")
        return 1
    else:
        step("opening the sign-in page in your browser; sign in there, then come back here")
        args = ["login", "--allow-no-subscriptions"]
        if a.tenant:
            args += ["--tenant", a.tenant]
        if a.device_code:
            args.append("--use-device-code")
        if not run_interactive(prefix, *args):
            print("Sign-in did not complete. Run this again; add --tenant <your org's tenant> if you have several accounts.",
                  file=sys.stderr)
            return 1
        step("signed in")

    if not a.check_only:
        if not run_quiet(prefix, "devops", "configure", "--defaults", f"organization={a.org}", f"project={a.project}"):
            print("Could not set the default organization/project.", file=sys.stderr)
            return 1
        step(f"defaults set: {a.org} / {a.project}")

    az = adolib.Az(prefix)
    try:
        rows = az("boards", "query", "--org", a.org, "--project", a.project, "--wiql",
                  "SELECT [System.Id] FROM WorkItems WHERE [System.AssignedTo] = @Me "
                  "AND [System.TeamProject] = @project AND [System.State] <> 'Removed'")
    except adolib.AzError as e:
        print(f"Signed in, but reading {a.project} failed. Check the project name and that you have access.\n{e}",
              file=sys.stderr)
        return 1
    step(f"read access OK: {len(rows or [])} work item(s) assigned to you in {a.project}")
    print("Ready. Publishing still needs your approval of the backlog first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
