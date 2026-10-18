# Upgrading to .NET 10: the breaking changes that bite most often

A curated list, not the full one. Before upgrading a real project, read the full pages
(linked under each heading) for the areas the project uses.

## SDK, NuGet and tooling
Full list: https://learn.microsoft.com/en-us/dotnet/core/compatibility/10#sdk-and-msbuild
- `dotnet restore` now audits **transitive** packages. Expect new NU190x warnings, which
  become errors under `TreatWarningsAsErrors`.
- `PackageReference` without a version is an error (NU1015). NU1510 is raised for direct
  references that NuGet prunes, because the framework already provides them.
- `dotnet new sln` creates `.slnx` by default.
- `dotnet package list` runs a restore first. CLI commands write non-command output to stderr.
- `dotnet test` gains an MTP mode, enabled via `global.json` `"test": {"runner": ...}`.
- `dotnet ef` needs `--framework` for multi-targeted projects (EF 10).

## C# 14 compiler
- The `field` keyword: a member named `field` used inside an accessor now means the backing
  field. Use `@field`/`this.field` or rename it.
- Span conversions change overload resolution: arrays bind to `MemoryExtensions` span
  methods, including inside `Expression<>` lambdas (fails under interpretation). Cast to
  `IEnumerable<T>` or call `Enumerable.X` explicitly.
  https://learn.microsoft.com/en-us/dotnet/core/compatibility/core-libraries/10.0/csharp-overload-resolution

## Core libraries and extensions
Full list: https://learn.microsoft.com/en-us/dotnet/core/compatibility/10
- `System.Linq.AsyncEnumerable` is now part of the core libraries. It clashes with the
  `System.Linq.Async` package; remove that package or alias it.
- `BackgroundService.ExecuteAsync` runs entirely as a Task. Synchronous code before the
  first `await` no longer blocks startup.
- Configuration now preserves `null` values. Previously they became empty strings.
- The runtime no longer installs default SIGTERM handlers; the generic host still handles shutdown.
- The default trace context propagator is now W3C. `ActivitySource.StartActivity`
  sampling behaviour changed.
- System.Text.Json now rejects property-name conflicts it used to let through.

## ASP.NET Core 10
Full list: https://learn.microsoft.com/en-us/aspnet/core/breaking-changes/10/overview
- Cookie auth: known API endpoints now get 401/403 instead of a login redirect.
- Exception handler: exceptions handled by an `IExceptionHandler` (`TryHandleAsync` returns
  `true`) are no longer logged by the middleware.
- `WithOpenApi()` is deprecated. OpenAPI documents default to version 3.1.
- `WebHostBuilder`/`IWebHost`/`WebHost` are obsolete: move to `WebApplication`/generic host.
- Razor runtime compilation is obsolete. `IActionContextAccessor` is obsolete.
  `IPNetwork`/`ForwardedHeadersOptions.KnownNetworks` are obsolete; use `KnownIPNetworks`.

## EF Core 10
Full list: https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/breaking-changes
- `ExecuteUpdateAsync` setters are a `Func<>`, not an expression. Hand-built expression trees break.
- Parameterized collections (`ids.Contains(x)`) send one parameter per value by default.
- SQL Server: with `UseAzureSql` or compatibility level 170+, JSON maps to the native
  `json` type, and the next migration alters existing `nvarchar(max)` JSON columns.
- EF injects `Application Name` into SQL Server connection strings that lack one. Mixing EF
  and ADO.NET/Dapper in one `TransactionScope` can then escalate to a distributed transaction.
- Complex type column names are uniquified, and nested complex properties use the full path.
  Check the generated migrations.
- SQL parameter names are simplified (`@city`). Snapshot tests on SQL text change.
- Microsoft.Data.Sqlite: values without an offset are treated as UTC (high impact for SQLite users).

## Containers
https://learn.microsoft.com/en-us/dotnet/core/compatibility/containers/10.0/default-images-use-ubuntu
- Default image tags use Ubuntu 24.04 (noble); no Debian images are shipped for .NET 10.
  If you install packages with `apt` in a Dockerfile, check the package names.

Last verified: 2026-10-18 against the pages linked above.
