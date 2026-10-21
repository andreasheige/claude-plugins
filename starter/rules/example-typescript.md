---
name: typescript-conventions
description: Conventions and validation commands for TypeScript changes. Use before writing or editing .ts/.tsx files and when validating TypeScript work.
paths: ["**/*.ts", "**/*.tsx"]
---

<!-- Path-scoped rule: copy to ~/.claude/rules/ (all repos) or <repo>/.claude/rules/.
     It loads only when the session touches a file matching `paths:`, so it costs
     no context in repos without TypeScript. Keep it short and specific. -->

Existing repo conventions win over everything here. Read neighbouring code first.

## Read the repo first
- `package.json` scripts, `tsconfig.json` (`strict`, `noUncheckedIndexedAccess`), the lint config.

## Rules
- No `any` without a comment explaining why; prefer `unknown` + narrowing.
- No `@ts-ignore`; use `@ts-expect-error` with a reason.

## Validate (in this order)
1. Type check: `npx tsc --noEmit`
2. Lint: the repo's lint script
3. Tests: the repo's test script, filtered to what changed first
4. Run it: start the app or call the code path and look at real output
