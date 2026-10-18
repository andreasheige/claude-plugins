# Upgrading to .NET 10: the breaking changes that bite most often

A curated list, not the full one. Before upgrading a real project, read the full pages
(linked under each heading) for the areas the project uses.

## SDK, NuGet and tooling
Full list: https://learn.microsoft.com/en-us/dotnet/core/compatibility/10#sdk-and-msbuild
- For projects targeting net10.0+, `NuGetAuditMode` defaults to `all`. Transitive
  vulnerabilities now warn (NU1901-NU1904) and fail restore under `TreatWarningsAsErrors`.
  Trace the source with `dotnet nuget why`, then upgrade or pin the package. Use
  `WarningsNotAsErrors`/`NuGetAuditSuppress` only as a last resort.
- `PackageReference` without a version is an error (NU1015, previously warning NU1604).
  This does not apply under Central Package Management.
- NU1510 (a warning, net10.0+ targets only): a direct reference to a package the framework
  already provides. Remove it, or condition it on older TFMs.
- `dotnet new sln` creates `.slnx` by default; `--format sln` gives the old format.
- `dotnet package list` runs a restore first. CLI commands write non-command output to stderr.
- `dotnet test` gains an MTP mode, enabled via `global.json` `"test": {"runner": ...}`.

## C# 14 compiler
- The `field` keyword: a member named `field` used inside an accessor now means the backing
  field. Use `@field`/`this.field` or rename it.
- Span conversions change overload resolution: arrays bind to `MemoryExtensions` span
  methods, including inside `Expression<>` lambdas (fails under interpretation). Cast to
  `IEnumerable<T>` or call `Enumerable.X` explicitly.
  https://learn.microsoft.com/en-us/dotnet/core/compatibility/core-libraries/10.0/csharp-overload-resolution

## Core libraries and extensions
Full list: https://learn.microsoft.com/en-us/dotnet/core/compatibility/10
- `System.Linq.AsyncEnumerable` is now part of the core libraries and clashes with the
  community `System.Linq.Async` package (ambiguous calls). Fixes:
  - Remove the direct reference, or upgrade it to 7.0.0.
  - If it arrives transitively, add a PackageReference with `ExcludeAssets="compile"`.
  - Some names changed, e.g. `SelectAwait` becomes `Select` with an async lambda.
- `BackgroundService.ExecuteAsync` runs entirely as a Task. Synchronous code before the
  first `await` no longer blocks startup. Put code that must run first in the constructor
  or in a `StartAsync` override.
- Configuration: JSON `null` is no longer turned into `""`. The binder now binds nulls
  (it used to skip them and keep initializer defaults). `null` on a non-nullable value
  type yields `default(T)`, and `[]` binds as an empty array.
- The runtime no longer installs default SIGTERM handlers. The generic host still handles
  shutdown. A bare console app without a host now dies on SIGTERM without raising
  `ProcessExit`; use `PosixSignalRegistration` if it needs cleanup.
- The default propagator follows W3C: it uses the `baggage` header instead of
  `Correlation-Context`. Revert with `DistributedContextPropagator.CreatePreW3CPropagator()`.
  An `ActivitySource` sampling change only affects custom `ActivityListener.Sample` code
  that returns `PropagationData`.
- System.Text.Json throws `InvalidOperationException` when a property name collides with a
  reserved metadata name (`$type`, `$id`, `$ref`) or a custom
  `TypeDiscriminatorPropertyName`. Rename the property or add `[JsonIgnore]`.

## ASP.NET Core 10
Full list: https://learn.microsoft.com/en-us/aspnet/core/breaking-changes/10/overview
- Cookie auth: known API endpoints now get 401/403 instead of a login redirect. That means
  `[ApiController]`, JSON minimal APIs, `TypedResults` and SignalR endpoints. Opt back in
  per endpoint with `.AllowCookieRedirect()`.
- Exception handler: for exceptions handled by an `IExceptionHandler` (`TryHandleAsync`
  returns `true`), the middleware no longer produces diagnostics: no log, no EventSource
  event, no `error.type` metric tag. Restore them with
  `ExceptionHandlerOptions.SuppressDiagnosticsCallback = _ => false`.
- `WithOpenApi()` is deprecated (ASPDEPR002); use `AddOpenApiOperationTransformer`.
  OpenAPI documents default to version 3.1 (see the ASP.NET Core 10 release notes).
- `WebHostBuilder`/`IWebHost`/`WebHost` are obsolete: move to `WebApplication`/generic host.
- Razor runtime compilation is obsolete. `IActionContextAccessor` is obsolete.
  `Microsoft.AspNetCore.HttpOverrides.IPNetwork` and `ForwardedHeadersOptions.KnownNetworks`
  are obsolete (ASPDEPR005); use `System.Net.IPNetwork` with `KnownIPNetworks`.

## EF Core 10
Full list: https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/breaking-changes
- EF tools: `dotnet ef ...` needs `--framework` for multi-targeted projects (Medium impact).
- `ExecuteUpdateAsync` setters are a `Func<>`, not an expression. Hand-built expression trees break.
- Parameterized collections (`ids.Contains(x)`) send one parameter per value by default.
- SQL Server: with `UseAzureSql` or compatibility level 170+, JSON maps to the native
  `json` type, and the next migration alters existing `nvarchar(max)` JSON columns.
  Plain `UseSqlServer` defaults to level 150, so nothing changes unless you opt in.
- EF injects `Application Name` into SQL Server connection strings that lack one. Mixing EF
  and ADO.NET/Dapper in one `TransactionScope` can then escalate to a distributed transaction.
- Complex type column names are uniquified, and nested complex properties use the full path.
  Check the generated migrations.
- SQL parameter names are simplified (`@city`). Snapshot tests on SQL text change, and most
  cached query plans recompile after deployment.
- Microsoft.Data.Sqlite has three high-impact changes:
  - `GetDateTimeOffset` on a value without an offset assumes UTC.
  - A `DateTimeOffset` written to a REAL column is converted to UTC.
  - `GetDateTime` on a value with an offset returns UTC.
  - Temporary revert: AppContext switch `Microsoft.Data.Sqlite.Pre10TimeZoneHandling`.

## Containers
https://learn.microsoft.com/en-us/dotnet/core/compatibility/containers/10.0/default-images-use-ubuntu
- Default image tags use Ubuntu 24.04 (noble); no Debian images are shipped for .NET 10.
  If you install packages with `apt` in a Dockerfile, check the package names.

Last verified: 2026-10-18 against the pages linked above.
