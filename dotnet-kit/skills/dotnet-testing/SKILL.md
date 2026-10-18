---
name: dotnet-testing
description: .NET testing: xUnit v3 lifetimes and fixtures, Microsoft.Testing.Platform vs VSTest commands, WebApplicationFactory integration tests, Testcontainers databases, FakeTimeProvider. Use when writing, running or fixing .NET tests.
paths: ["**/*.cs", "**/*.csproj", "**/*.sln*", "**/*.razor", "**/*.cshtml"]
---

# Testing .NET code

Use the repo's framework (xUnit, NUnit, MSTest), assertion style and mocking library.
Don't introduce a new one; see `../dotnet-conventions/references/licensing.md` for assertion libraries.

## Which runner? (decides the command line)
- `global.json` has `"test": { "runner": "Microsoft.Testing.Platform" }` → MTP mode:
  `dotnet test --project tests/X.Tests.csproj`, `dotnet test --solution X.slnx`,
  options go straight through, e.g. `--filter-class`, `--filter-not-trait "Category=Docker"`.
- Otherwise VSTest mode: `dotnet test X.sln --filter "Category!=Docker"`.
  Caveat: `xunit.v3` 4.x uses MTP v2, and the old MTP-through-VSTest bridge does not
  work with MTP v2 on the .NET 10 SDK. If `dotnet test` reports a compatibility error,
  add the `global.json` runner setting above.
- xUnit v3 test projects are executables (`<OutputType>Exe</OutputType>`) and can also
  be run directly with `dotnet run --project tests/X.Tests`.

## xUnit v3 essentials
- Package `xunit.v3`; the old `xunit` package is v2. Release 4.x of `xunit.v3` is still
  the v3 framework and defaults to MTP v2.
- `IAsyncLifetime` now uses `ValueTask` and extends `IAsyncDisposable`:
  `ValueTask InitializeAsync()` plus `ValueTask DisposeAsync()`.
- `TestContext.Current.CancellationToken`: pass it to async calls so cancelled runs stop.
- Fixtures: `IClassFixture<T>` (per class), `ICollectionFixture<T>` with `[CollectionDefinition]`
  (shared across classes), `[assembly: AssemblyFixture(typeof(T))]` (once per assembly, new in v3).
- Skips: `Assert.Skip("reason")` at runtime, `[Fact(Explicit = true)]` runs only on request.

## Integration tests with WebApplicationFactory
.NET 10 generates `public partial class Program` for top-level-statement apps, and an
analyzer suggests removing a hand-written one. For net8.0/net9.0 apps, still add
`public partial class Program;` at the end of `Program.cs`.

```csharp
// No "public partial class Program" in the app: .NET 10 generates it.
public sealed class ApiFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    private readonly string _databasePath = Path.Combine(Path.GetTempPath(), $"todos-{Guid.NewGuid():N}.db");

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Development");
        builder.UseSetting("ConnectionStrings:Todos", $"Data Source={_databasePath};Pooling=False");
    }

    public async ValueTask InitializeAsync()
    {
        await using var scope = Services.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        await db.Database.EnsureCreatedAsync(TestContext.Current.CancellationToken);
    }
```

Read connection strings when the service is resolved, e.g.
`AddDbContext<T>((sp, o) => o.UseX(sp.GetRequiredService<IConfiguration>()...))`, so test
overrides always win.

```csharp
public sealed class ApiTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    private readonly HttpClient _client = factory.CreateClient();

    [Fact]
    public async Task Create_then_get_returns_the_todo()
    {
        var ct = TestContext.Current.CancellationToken;

        var created = await _client.PostAsJsonAsync("/api/todos", new CreateTodoRequest("Write tests", 2), ct);
        Assert.Equal(HttpStatusCode.Created, created.StatusCode);
```

## Databases: Testcontainers, not EF InMemory
- Default: the real engine in a container (Testcontainers). Builders take the image in
  the constructor (`new PostgreSqlBuilder("postgres:17-alpine")`); pin the tag.
- SQLite in-memory (`Data Source=:memory:` on a connection kept open) is a last-resort
  fake. The EF docs prefer the real engine, then a repository layer. SQLite differs from
  production in case sensitivity, translation and raw SQL, so a test can pass on SQLite
  and fail in production.
- Don't use `UseInMemoryDatabase` to test queries. It isn't relational: it ignores
  transactions, rejects raw SQL, and evaluates LINQ in memory instead of translating it.
  The EF docs call it "highly discouraged".

```csharp
public sealed class PostgresFixture : IAsyncLifetime
{
    public PostgreSqlContainer Container { get; } = new PostgreSqlBuilder("postgres:17-alpine").Build();

    public string ConnectionString => Container.GetConnectionString();

    public async ValueTask InitializeAsync() => await Container.StartAsync();

    public async ValueTask DisposeAsync() => await Container.DisposeAsync();
}
```

Tag Docker-backed tests (`[Trait("Category", "Docker")]`) so they can be filtered out
where no container runtime is available. A failing class fixture fails every test in the
class, `Explicit` ones included.

## Time
Inject `TimeProvider`; test with `FakeTimeProvider` (`Microsoft.Extensions.TimeProvider.Testing`):

```csharp
var time = new FakeTimeProvider(new DateTimeOffset(2026, 1, 1, 12, 0, 0, TimeSpan.Zero));
var checker = new DueDateChecker(time);
var dueAt = time.GetUtcNow().AddHours(1);

Assert.False(checker.IsOverdue(dueAt));
time.Advance(TimeSpan.FromHours(2));
Assert.True(checker.IsOverdue(dueAt));
```

## Sources
Last verified: 2026-10-18. Samples compile and run green in `verify/` (xunit.v3 4.0.2, MTP mode).
- https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-with-dotnet-test
- https://learn.microsoft.com/en-us/dotnet/core/testing/microsoft-testing-platform-intro
- https://learn.microsoft.com/en-us/aspnet/core/test/integration-tests
- https://learn.microsoft.com/en-us/aspnet/core/release-notes/aspnetcore-10.0
- https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.extensions.time.testing.faketimeprovider
- https://xunit.net/docs/getting-started/v3/whats-new
- https://xunit.net/releases/v3/4.0.0
- https://dotnet.testcontainers.org/modules/postgres/
