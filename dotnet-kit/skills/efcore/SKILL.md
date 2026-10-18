---
name: efcore
description: EF Core 10 data access: DbContext lifetime, no-tracking projections, ExecuteUpdate/Delete, named query filters, LeftJoin, complex types as JSON, FromSql vs SqlQuery, migrations and EF 10 breaking changes.
paths: ["**/*.cs", "**/*.csproj", "**/*.sln*", "**/*.razor", "**/*.cshtml"]
---

# EF Core 10

## Repository or DbContext?
This depends on the repo. If it has repositories or a unit-of-work layer, go through
them. In a greenfield project, using `DbContext` directly from handlers is fine:
`DbSet<T>` is already a repository and `DbContext` a unit of work. Don't add or remove
a repository layer without asking.

## Lifetime
- `AddDbContext` registers a scoped context. A context is not thread-safe: never run two
  queries at once on one instance (no `Task.WhenAll` over the same context).
- For singletons, background services or Blazor Server, use `AddDbContextFactory` and
  `await using var db = await factory.CreateDbContextAsync(ct);`.

## Reads
Use no tracking and project only the columns you need. .NET 10 adds `LeftJoin`/`RightJoin`,
and EF 10 translates them:

```csharp
db.Todos
    .AsNoTracking()
    .Where(t => !t.IsDone)
    .OrderBy(t => t.Id)
    .LeftJoin(
        db.Categories,
        todo => todo.CategoryId,
        category => (int?)category.Id,
        (todo, category) => new TodoSummary(todo.Id, todo.Title, category == null ? "(none)" : category.Name))
    .ToListAsync(cancellationToken);
```

## Named query filters (EF 10)
An entity can now have several filters, and you can switch them off one at a time:

```csharp
// EF 10: named filters can be disabled one at a time
todo.HasQueryFilter(TodoFilters.SoftDelete, t => !t.IsDeleted);
```

```csharp
db.Todos
    .IgnoreQueryFilters([TodoFilters.SoftDelete])
    .CountAsync(cancellationToken);
```

## Bulk updates
`ExecuteUpdateAsync`/`ExecuteDeleteAsync` run one SQL statement. They skip the change
tracker, `SaveChanges` interceptors and concurrency tokens. EF 10 takes a normal lambda,
so you can add setters conditionally:

```csharp
.ExecuteUpdateAsync(setters =>
{
    setters.SetProperty(t => t.IsDone, true);
    if (clearNotes)
    {
        setters.SetProperty(t => t.Details.Notes, (string?)null);
    }
}, cancellationToken);
```

Breaking: code that built `Expression<Func<SetPropertyCalls<T>, ...>>` by hand no longer compiles.

## Complex types (EF 10)
Value-like objects without identity. EF 10 adds optional complex types, struct complex
types, and mapping to one JSON column. Prefer them over owned types for new JSON columns.

```csharp
// EF 10: complex type stored as a single JSON column
todo.ComplexProperty(t => t.Details, details => details.ToJson());
```

SQL Server uses the native `json` type with `UseAzureSql` or compatibility level 170+.
Existing `nvarchar(max)` JSON columns are then altered by the next migration
(see `../dotnet-conventions/references/breaking-changes-10.md`).

## Raw SQL
- `FromSql($"... {value}")` returns **entity types**; interpolated values become parameters.
  You can compose LINQ on top of it, and query filters apply.
- `Database.SqlQuery<T>($"...")` returns **scalars or unmapped types**. For scalars,
  name the column `Value`. Entity query filters do not apply.
- `FromSqlRaw`/`ExecuteSqlRaw` take a plain string. Never concatenate input into it;
  EF 10 warns about concatenation inside these calls.

```csharp
db.Todos
    .FromSql($"SELECT * FROM Todos WHERE Title LIKE {"%" + term + "%"}")
    .AsNoTracking()
    .ToListAsync(cancellationToken);
```

```csharp
db.Database
    .SqlQuery<int>($"SELECT Id AS Value FROM Todos WHERE IsDone = {false}")
    .ToListAsync(cancellationToken);
```

## EF 10 behaviour changes to know
- `ids.Contains(x)` now sends one parameter per value (padded), not a JSON array.
  Change it with `UseParameterizedCollectionMode(...)` or per query with
  `EF.Constant` / `EF.Parameter`.
- SQL parameter names are simpler (`@city`, not `@__city_0`). Snapshot tests of SQL text will change.
- Projects with `<TargetFrameworks>`: `dotnet ef ... --framework net10.0` is required.
- Microsoft.Data.Sqlite 10: date/time values without an offset are now read as UTC.

## Migrations (ask before running against a shared database)
`dotnet ef migrations add <Name>`; review the generated code. Ship it with
`dotnet ef migrations script --idempotent` or a bundle (`dotnet ef migrations bundle`).
Don't call `Database.Migrate()` at app startup in multi-instance deployments unless the repo already does.

## Testing
Test against the real provider (Testcontainers), see `dotnet-testing`. Don't use the
EF InMemory provider for query behaviour.

## Sources
Last verified: 2026-10-18. Samples compile and are exercised against SQLite in `verify/`.
- https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/whatsnew
- https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/breaking-changes
- https://learn.microsoft.com/en-us/ef/core/querying/sql-queries
- https://learn.microsoft.com/en-us/ef/core/querying/filters
- https://learn.microsoft.com/en-us/ef/core/dbcontext-configuration/
- https://learn.microsoft.com/en-us/ef/core/saving/execute-insert-update-delete
