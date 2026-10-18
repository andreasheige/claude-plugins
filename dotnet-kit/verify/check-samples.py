#!/usr/bin/env python3
"""Fail if a C# code block in a dotnet-kit skill is not present, line for line, in verify/.

Rule from the plan: no sample enters a skill unless it compiles here. Whitespace and
blank lines are ignored; everything else must match a contiguous run of lines in one
.cs file under verify/Samples*.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^```(csharp|cs|c#)\s*$\n(.*?)^```\s*$", re.M | re.S)


def norm(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def contains(haystack, needle):
    n = len(needle)
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


sources = {
    path: norm(path.read_text())
    for path in (ROOT / "verify").glob("Samples*/**/*.cs")
    if "/obj/" not in str(path) and "/bin/" not in str(path)
}
docs = sorted((ROOT / "skills").glob("**/*.md"))
blocks = failures = 0
for doc in docs:
    for match in FENCE.finditer(doc.read_text()):
        blocks += 1
        lines = norm(match.group(2))
        if not any(contains(src, lines) for src in sources.values()):
            failures += 1
            line_no = doc.read_text()[: match.start()].count("\n") + 1
            print(f"NOT IN verify/: {doc.relative_to(ROOT)}:{line_no}: {lines[0] if lines else ''}")

print(f"{blocks} C# blocks checked in {len(docs)} files, {failures} missing")
sys.exit(1 if failures or blocks == 0 else 0)
