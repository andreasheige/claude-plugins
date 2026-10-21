#!/usr/bin/python3
"""PostToolUse (Write|Edit): check the YAML frontmatter of Claude Code commands, skills and agents.

A file Claude Code can't parse is skipped or loads without its description, so a
parse error here is fed back to the model as a block, to be fixed right away.
"""
import json
import re
import sys

import yaml

TARGET = re.compile(r"/\.claude/(commands/.+\.md|skills/.+/SKILL\.md|agents/.+\.md)$")


def main():
    data = json.load(sys.stdin)
    path = (data.get("tool_input") or {}).get("file_path") or (data.get("tool_response") or {}).get("filePath") or ""
    if not TARGET.search(path):
        return
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return
    if not text.startswith("---"):
        return
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        problem = "opening `---` has no closing `---` line"
    else:
        try:
            meta = yaml.safe_load(m.group(1))
            problem = None if isinstance(meta, dict) else f"frontmatter is a {type(meta).__name__}, not a key: value mapping"
        except yaml.YAMLError as e:
            problem = str(e).replace("\n", " ")
    if problem:
        print(json.dumps({
            "decision": "block",
            "reason": f"Invalid YAML frontmatter in {path}: {problem}. "
                      "Quote values that start with [ { * & ! | > % @ ` or contain ': ' or ' #'.",
        }))


if __name__ == "__main__":
    main()
