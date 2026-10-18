using Microsoft.EntityFrameworkCore;

namespace Samples.Data;

public sealed record TodoSummary(int Id, string Title, string Category);

public static class TodoQueries
{
    // Read path: no tracking, project only the columns you need
    public static Task<List<TodoSummary>> ListOpenAsync(AppDbContext db, CancellationToken cancellationToken) =>
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

    // Bypass only the soft-delete filter, keep any other named filters
    public static Task<int> CountIncludingDeletedAsync(AppDbContext db, CancellationToken cancellationToken) =>
        db.Todos
            .IgnoreQueryFilters([TodoFilters.SoftDelete])
            .CountAsync(cancellationToken);

    // Set-based update without loading entities; setters can now be a normal lambda
    public static Task<int> CompleteAsync(
        AppDbContext db, int[] ids, bool clearNotes, CancellationToken cancellationToken) =>
        db.Todos
            .Where(t => ids.Contains(t.Id))
            .ExecuteUpdateAsync(setters =>
            {
                setters.SetProperty(t => t.IsDone, true);
                if (clearNotes)
                {
                    setters.SetProperty(t => t.Details.Notes, (string?)null);
                }
            }, cancellationToken);

    // Raw SQL returning entities: FromSql parameterizes the interpolated value
    public static Task<List<Todo>> SearchByTitleAsync(AppDbContext db, string term, CancellationToken cancellationToken) =>
        db.Todos
            .FromSql($"SELECT * FROM Todos WHERE Title LIKE {"%" + term + "%"}")
            .AsNoTracking()
            .ToListAsync(cancellationToken);

    // Raw SQL returning a scalar or unmapped type: Database.SqlQuery<T>
    public static Task<List<int>> OpenIdsAsync(AppDbContext db, CancellationToken cancellationToken) =>
        db.Database
            .SqlQuery<int>($"SELECT Id AS Value FROM Todos WHERE IsDone = {false}")
            .ToListAsync(cancellationToken);
}
