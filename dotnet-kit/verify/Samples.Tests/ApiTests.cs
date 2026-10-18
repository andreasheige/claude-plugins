using System.Net;
using System.Net.Http.Json;
using Samples.Api;

namespace Samples.Tests;

public sealed class ApiTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    private readonly HttpClient _client = factory.CreateClient();

    [Fact]
    public async Task Create_then_get_returns_the_todo()
    {
        var ct = TestContext.Current.CancellationToken;

        var created = await _client.PostAsJsonAsync("/api/todos", new CreateTodoRequest("Write tests", 2), ct);
        Assert.Equal(HttpStatusCode.Created, created.StatusCode);

        var body = await created.Content.ReadFromJsonAsync<TodoResponse>(ct);
        var fetched = await _client.GetFromJsonAsync<TodoResponse>($"/api/todos/{body!.Id}", ct);
        Assert.Equal("Write tests", fetched!.Title);
    }

    [Fact]
    public async Task Invalid_request_returns_validation_problem()
    {
        var ct = TestContext.Current.CancellationToken;

        var response = await _client.PostAsJsonAsync("/api/todos", new { Title = "", Priority = 9 }, ct);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        var problem = await response.Content.ReadAsStringAsync(ct);
        Assert.Contains("Title", problem, StringComparison.Ordinal);
        Assert.Contains("Priority", problem, StringComparison.Ordinal);
    }

    [Fact]
    public async Task Delete_without_token_is_unauthorized()
    {
        var response = await _client.DeleteAsync("/api/todos/1", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task Unhandled_exception_returns_problem_details()
    {
        var response = await _client.GetAsync("/boom", TestContext.Current.CancellationToken);

        Assert.Equal(HttpStatusCode.InternalServerError, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
    }

    [Fact]
    public async Task OpenApi_document_is_3_1()
    {
        var json = await _client.GetStringAsync("/openapi/v1.json", TestContext.Current.CancellationToken);

        Assert.Contains("\"openapi\": \"3.1", json, StringComparison.Ordinal);
    }
}
