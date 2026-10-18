---
name: dotnet-conventions
description: Conventions and validation commands for any C#/.NET change. Use before writing or editing .cs, .csproj, .sln/.slnx, .razor or .cshtml files, and when validating .NET work (build, format, test, vulnerable packages).
paths: ["**/*.cs", "**/*.csproj", "**/*.sln*", "**/*.razor", "**/*.cshtml"]
---

Existing repo conventions win over everything in this kit. Read neighbouring code before writing new code.

## Read the repo first
- `global.json` (SDK, test runner), `Directory.Build.props`, `Directory.Packages.props`
  (central package management: versions live there, not in the `.csproj`), `.editorconfig`.
- Per project: `TargetFramework(s)`, `LangVersion`, `Nullable`, `TreatWarningsAsErrors`.
  Use only language features that `LangVersion` allows (net8 = C# 12, net9 = 13, net10 = 14).
- Copy what is already there: DI registration style, folder layout, naming, test framework,
  logging and mocking libraries. Ask before adding a package, pattern or project.

## Defaults when the repo has no convention
- Nullable on. A `!` needs a comment saying why it is safe.
- Async all the way: no `.Result`, `.Wait()` or `.GetAwaiter().GetResult()`. Take a
  `CancellationToken` and pass it to every I/O call.
- Structured logging with named placeholders (`"Order {OrderId}"`), never interpolated
  strings. Use `[LoggerMessage]` on hot paths.
- `sealed` classes unless designed for inheritance. If the repo leaves classes unsealed,
  follow the repo.
- Inject `TimeProvider` instead of reading `DateTime.UtcNow` in code you test.
- No secrets in `appsettings*.json`: user secrets locally, environment or a vault when deployed.
- Ask first: auth, payments, PII, EF migrations against shared databases, infra.

## Validation map (devsecops `/validate` levels)
- **L1** `dotnet build -warnaserror`, then `dotnet format --verify-no-changes`.
  If the baseline already fails, compare against it and do not fix unrelated code;
  narrow format with `--include <changed files>`.
- **L2/L3** `dotnet test`. Check `global.json` first:
  - `"test": { "runner": "Microsoft.Testing.Platform" }` means MTP mode (.NET 10 SDK):
    `dotnet test --project X.csproj` / `--solution X.slnx`, and test-app options go
    straight on the command line (xUnit v3: `--filter-class`, `--filter-trait`).
  - Otherwise VSTest mode: `dotnet test X.sln --filter "FullyQualifiedName~Foo"`.
    For MTP-based test projects in this mode, put MTP options after `--`.
- **L4** Run it: `dotnet run --project <app>`, then call the endpoint (curl) or read
  the console output. A green test run is not L4.
- **L5** `dotnet package list --vulnerable --include-transitive`
  (older spelling: `dotnet list package ...`).

## Topic skills in this plugin
- `csharp-modern`, `aspnetcore-api`, `efcore`, `dotnet-testing`,
  `dotnet-observability`, `dotnet-containers`.
- Upgrading to .NET 10: [references/breaking-changes-10.md](references/breaking-changes-10.md).
- Before adding a NuGet package: [references/licensing.md](references/licensing.md).
- Architecture choices for a new project only: the user runs `/dotnet-kit:dotnet-architecture`.

Last verified: 2026-10-18 against
https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-with-dotnet-test,
https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/configure-language-version,
https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-package-list.
