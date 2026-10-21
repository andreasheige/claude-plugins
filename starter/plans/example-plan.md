# Add rate limiting to the public API

Goal: anonymous clients get at most 60 requests/minute per IP; authenticated clients 600.
Non-goals: per-endpoint limits, a distributed store (single instance today).

## Design
- Middleware in front of the router; fixed-window counter in memory.
- 429 with `Retry-After`; limits read from config, not hard-coded.

## Open decisions
- (none — if one appears mid-work, write `BLOCKED: <question>` below and stop)

## Steps
Each step says how it is verified. `/plan-gate plans/example-plan.md` keeps the agent going
until every box is ticked or a `BLOCKED:` line appears.

- [x] 1. Read the existing middleware chain and config loading
      → verify: list the files touched by step 2 in this plan.
- [~] @agent-1 2. Add the limiter middleware with config-driven limits
      → verify: unit test — 61st anonymous request in a window returns 429 with `Retry-After`.
- [ ] 3. Exempt health checks
      → verify: 1000 calls to `/health` in a loop all return 200.
- [ ] 4. Run the real server and hit it with `hey -n 100`
      → verify: observed 429 count matches the limit (paste the output).
- [ ] 5. Update the API docs
      → verify: docs build passes; the new section renders.

## Review
<!-- Filled in when done: what changed, what was verified, what is left. -->
