using System.ComponentModel.DataAnnotations;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;
using Samples.Data;
using Samples.Observability;

namespace Samples.Api;

public sealed record CreateTodoRequest(
    [Required, StringLength(200)] string Title,
    [Range(0, 5)] int Priority);

public sealed record TodoResponse(int Id, string Title, bool IsDone);

public static class TodoEndpoints
{
    public static RouteGroupBuilder MapTodoEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/todos").WithTags("Todos");

        group.MapGet("/{id:int}", GetByIdAsync).WithName("GetTodo");
        group.MapPost("/", CreateAsync);
        group.MapDelete("/{id:int}", DeleteAsync).RequireAuthorization();

        return group;
    }

    private static async Task<Results<Ok<TodoResponse>, NotFound>> GetByIdAsync(
        int id, AppDbContext db, CancellationToken cancellationToken)
    {
        var todo = await db.Todos
            .AsNoTracking()
            .Where(t => t.Id == id)
            .Select(t => new TodoResponse(t.Id, t.Title, t.IsDone))
            .FirstOrDefaultAsync(cancellationToken);

        return todo is null ? TypedResults.NotFound() : TypedResults.Ok(todo);
    }

    private static async Task<CreatedAtRoute<TodoResponse>> CreateAsync(
        CreateTodoRequest request, AppDbContext db, ILogger<Todo> logger, CancellationToken cancellationToken)
    {
        var todo = new Todo { Title = request.Title, Details = { Priority = request.Priority } };
        db.Todos.Add(todo);
        await db.SaveChangesAsync(cancellationToken);

        logger.TodoCreated(todo.Id, request.Priority);
        return TypedResults.CreatedAtRoute(
            new TodoResponse(todo.Id, todo.Title, todo.IsDone), "GetTodo", new { id = todo.Id });
    }

    private static async Task<Results<NoContent, NotFound>> DeleteAsync(
        int id, AppDbContext db, CancellationToken cancellationToken)
    {
        var affected = await db.Todos
            .Where(t => t.Id == id)
            .ExecuteUpdateAsync(s => s.SetProperty(t => t.IsDeleted, true), cancellationToken);

        return affected == 0 ? TypedResults.NotFound() : TypedResults.NoContent();
    }
}
