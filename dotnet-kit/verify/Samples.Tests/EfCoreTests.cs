using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Samples.Data;

namespace Samples.Tests;

public sealed class EfCoreTests : IAsyncLifetime
{
    private readonly SqliteConnection _connection = new("Data Source=:memory:");
    private AppDbContext _db = null!;

    public async ValueTask InitializeAsync()
    {
        await _connection.OpenAsync(TestContext.Current.CancellationToken);
        _db = new AppDbContext(new DbContextOptionsBuilder<AppDbContext>().UseSqlite(_connection).Options);
        await _db.Database.EnsureCreatedAsync(TestContext.Current.CancellationToken);

        var work = new Category { Name = "Work" };
        _db.AddRange(
            work,
            new Todo { Title = "alpha", Details = { Notes = "n1" } },
            new Todo { Title = "beta", IsDeleted = true });
        await _db.SaveChangesAsync(TestContext.Current.CancellationToken);
        _db.Add(new Todo { Title = "gamma", CategoryId = work.Id });
        await _db.SaveChangesAsync(TestContext.Current.CancellationToken);
        _db.ChangeTracker.Clear();
    }

    public async ValueTask DisposeAsync()
    {
        await _db.DisposeAsync();
        await _connection.DisposeAsync();
    }

    [Fact]
    public async Task LeftJoin_keeps_todos_without_category_and_filter_hides_deleted()
    {
        var open = await TodoQueries.ListOpenAsync(_db, TestContext.Current.CancellationToken);

        Assert.Equal(["alpha:(none)", "gamma:Work"], open.Select(t => $"{t.Title}:{t.Category}"));
    }

    [Fact]
    public async Task Named_filter_can_be_ignored()
    {
        Assert.Equal(3, await TodoQueries.CountIncludingDeletedAsync(_db, TestContext.Current.CancellationToken));
    }

    [Fact]
    public async Task ExecuteUpdate_with_conditional_setters_updates_json_property()
    {
        var ct = TestContext.Current.CancellationToken;
        var alpha = await _db.Todos.SingleAsync(t => t.Title == "alpha", ct);

        var affected = await TodoQueries.CompleteAsync(_db, [alpha.Id], clearNotes: true, ct);

        _db.ChangeTracker.Clear();
        var reloaded = await _db.Todos.SingleAsync(t => t.Id == alpha.Id, ct);
        Assert.Equal(1, affected);
        Assert.True(reloaded.IsDone);
        Assert.Null(reloaded.Details.Notes);
    }

    [Fact]
    public async Task Raw_sql_queries_are_parameterized()
    {
        var ct = TestContext.Current.CancellationToken;

        var found = await TodoQueries.SearchByTitleAsync(_db, "amm", ct);
        var openIds = await TodoQueries.OpenIdsAsync(_db, ct);

        Assert.Equal("gamma", Assert.Single(found).Title);
        Assert.Equal(3, openIds.Count); // SqlQuery is not subject to entity query filters
    }
}
