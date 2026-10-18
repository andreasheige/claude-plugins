---
name: dotnet-architecture
description: Architecture options for a NEW (greenfield) .NET service - project layout, vertical slices vs layers, Result vs exceptions, DbContext vs repositories, mediator and messaging libraries. Run only on explicit request.
disable-model-invocation: true
---

# Greenfield .NET architecture options

Use this skill only for a new codebase, and only because the user asked. In an existing
repo, its current architecture is the answer. Do not apply anything below to it, and do
not suggest migrating to it.

Present the options, recommend one with the reason, let the user decide, and write the
decision down as a short ADR (`docs/adr/NNNN-title.md`, or wherever the repo keeps ADRs).

## 1. Code organisation
| Option | Fits when | Costs |
|---|---|---|
| Vertical slices (one folder per feature: endpoint, request, handler, validation, tests nearby) | Many independent use cases, CRUD-plus APIs, small teams | Some duplication between slices; needs discipline about shared code |
| Layered / Clean (Api, Application, Domain, Infrastructure projects) | Rich domain rules shared by many use cases, several delivery channels | More projects and mapping; ceremony for simple features |
| Modular monolith (modules with their own data and a public contract, inside one deployable) | Clear bounded contexts, possible later split | Needs enforced module boundaries (tests or analyzers) |

Default for a small new API: one web project with vertical slices, plus a test project.
Add projects when a real boundary appears, not before.

## 2. Errors: exceptions vs Result
- **Exceptions + ProblemDetails** (`IExceptionHandler`): least code, idiomatic ASP.NET Core.
  Good when failures are rare or exceptional.
- **Result type** (`Result<T>`/`OneOf`/hand-rolled): explicit expected failures
  (not found, conflict, validation) in signatures. Good when callers branch on outcomes.
  Map results to `TypedResults` at the edge. Exceptions stay for bugs and infrastructure faults.
- Don't mix the two styles for the same kind of failure.

## 3. Data access
- **DbContext directly** in handlers: least code. EF is already a repository plus unit of work.
  Put query reuse in extension methods or specification-style helpers.
- **Repositories**: when the domain must not see EF, when there are several data sources,
  or when the team insists on persistence ignorance. Cost: leaky `IQueryable` or many
  narrow methods.
- Raw SQL / Dapper for hot read paths is fine next to EF.

## 4. In-process mediator and messaging (check licences first)
- Plain handler classes registered in DI are enough for most APIs. A mediator mostly buys
  pipeline behaviours (logging, validation, transactions), and endpoint filters or
  decorators can do that too.
- MediatR: 12.x is Apache-2.0. From 13.0 it is dual RPL-1.5 / commercial (Lucky Penny Software).
- Wolverine (JasperFx): MIT. In-process mediator plus messaging, with its own conventions.
- MassTransit: v8 is Apache-2.0; v9+ is commercial.
- Details: `../dotnet-conventions/references/licensing.md`.

## 5. Cross-cutting defaults for any choice
- `TreatWarningsAsErrors`, `Nullable`, `AnalysisLevel` (`latest-recommended`), and
  `.editorconfig` from day one.
- Central package management (`Directory.Packages.props`).
- `global.json` pinning the SDK, and the MTP test runner if the tests use it.
- Integration tests with WebApplicationFactory plus Testcontainers from the first endpoint.
- OpenTelemetry + health checks (`AddHealthChecks`, `MapHealthChecks("/health")`) before the first deploy.

Last verified: 2026-10-18. Opinions, not facts: no learn.microsoft.com claim depends on this
file except the licensing lines, checked against nuget.org licence metadata and vendor announcements.
