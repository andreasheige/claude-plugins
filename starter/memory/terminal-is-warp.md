---
name: terminal-is-warp
description: The terminal is Warp, not Terminal.app; scripts that open a terminal must not hard-code it
tags:
  - type/gotcha        # decision | convention | gotcha | preference | reference
  - tool/any           # which agent/tool this applies to
metadata:
  added_by: claude-code
  date: 2026-10-20
---

Anything that opens or scripts "a terminal" must not assume Terminal.app, iTerm or any
named application.

**Why:** a launch button was built with `open -a Terminal` and opened the wrong application
on the first real try.
**How to apply:** macOS sets `__CFBundleIdentifier` on a launched app and every child
process inherits it. Read it and pass it to `open -b <id>`; fall back to a bare `open`.
Never a lookup table of terminal names — it is wrong for whatever ships next.
