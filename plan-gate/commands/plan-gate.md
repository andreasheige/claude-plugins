---
description: Work through a plan file without stopping between items, until it is done or BLOCKED
argument-hint: <path/to/plan.md | off>
---

Plan gate: `$ARGUMENTS`

If the argument is `off`, the gate is now off: say so in one line and stop.

Otherwise the plugin's Stop hook (`scripts/plan-gate.mjs`) now keeps this session going until every checkbox in that plan is ticked. Work like this:

1. Read the plan. Take the first open item (`- [ ]` or `- [~]`).
2. Do it, verify it, then tick it (`- [x]`). Don't ask whether to continue to the next item.
3. Stop only when one of these is true, after first writing a line `BLOCKED: <reason>` into the plan:
   - the item is genuinely ambiguous and a guess could be wrong in a way that matters;
   - it touches an ask-first area (auth, payments, PII, migrations, infrastructure);
   - it needs an outward-facing action the user hasn't approved (pushing, landing a PR, publishing).
4. When the user answers, remove the `BLOCKED:` line and continue.

The hook gives up after 10 automatic continuations per prompt, and does nothing once all items are ticked.
