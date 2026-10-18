using Microsoft.EntityFrameworkCore;

namespace Samples.Data;

public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<Todo> Todos => Set<Todo>();

    public DbSet<Category> Categories => Set<Category>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Todo>(todo =>
        {
            todo.Property(t => t.Title).HasMaxLength(200);

            // EF 10: named filters can be disabled one at a time
            todo.HasQueryFilter(TodoFilters.SoftDelete, t => !t.IsDeleted);

            // EF 10: complex type stored as a single JSON column
            todo.ComplexProperty(t => t.Details, details => details.ToJson());
        });
    }
}

public static class TodoFilters
{
    public const string SoftDelete = nameof(SoftDelete);
}

public sealed class Todo
{
    public int Id { get; set; }

    public required string Title { get; set; }

    public bool IsDone { get; set; }

    public bool IsDeleted { get; set; }

    public int? CategoryId { get; set; }

    public TodoDetails Details { get; set; } = new();
}

public sealed class TodoDetails
{
    public string? Notes { get; set; }

    public int Priority { get; set; }
}

public sealed class Category
{
    public int Id { get; set; }

    public required string Name { get; set; }
}
