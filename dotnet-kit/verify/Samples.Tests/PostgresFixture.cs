using Testcontainers.PostgreSql;

namespace Samples.Tests;

public sealed class PostgresFixture : IAsyncLifetime
{
    public PostgreSqlContainer Container { get; } = new PostgreSqlBuilder("postgres:17-alpine").Build();

    public string ConnectionString => Container.GetConnectionString();

    public async ValueTask InitializeAsync() => await Container.StartAsync();

    public async ValueTask DisposeAsync() => await Container.DisposeAsync();
}

public sealed class PostgresTests(PostgresFixture postgres) : IClassFixture<PostgresFixture>
{
    // Needs a container runtime; excluded from the default run by the trait filter
    [Fact]
    [Trait("Category", "Docker")]
    public async Task Container_accepts_queries()
    {
        var result = await postgres.Container.ExecScriptAsync("SELECT 1;", TestContext.Current.CancellationToken);

        Assert.Equal(0, result.ExitCode);
        Assert.Contains("Host=", postgres.ConnectionString, StringComparison.Ordinal);
    }
}
