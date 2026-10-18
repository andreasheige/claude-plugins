---
name: aspnetcore-api
description: ASP.NET Core 10 web APIs: minimal API endpoints and MapGroup, built-in validation and OpenAPI, ProblemDetails and IExceptionHandler, configuration precedence, JWT auth, HttpClientFactory and resilience defaults.
paths: ["**/*.cs", "**/*.csproj", "**/*.sln*", "**/*.razor", "**/*.cshtml"]
---

# ASP.NET Core APIs (.NET 10)

Follow the repo first. If it uses controllers, keep controllers. If endpoints are organised
another way (extension methods, a library, `IEndpoint` classes), copy that. Nothing here
requires a particular endpoint abstraction.

## Endpoints
Group routes with `MapGroup`, return `TypedResults`, and declare outcomes with `Results<...>`
so OpenAPI sees every response type:

```csharp
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
```

## Validation (new in .NET 10)
`builder.Services.AddValidation();` validates minimal API parameters with DataAnnotations,
including attributes on record parameters. Failures return 400 with a validation
ProblemDetails, with no extra code. Opt out per endpoint with `.DisableValidation()`.
If the repo already uses FluentValidation, keep it.

```csharp
public sealed record CreateTodoRequest(
    [Required, StringLength(200)] string Title,
    [Range(0, 5)] int Priority);
```

## Errors: ProblemDetails + IExceptionHandler

```csharp
builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
```

Then `app.UseExceptionHandler();` and `app.UseStatusCodePages();`.
**.NET 10 change:** when `TryHandleAsync` returns `true`, the middleware no longer logs the
exception. Log it yourself:

```csharp
public async ValueTask<bool> TryHandleAsync(
    HttpContext httpContext, Exception exception, CancellationToken cancellationToken)
{
    // .NET 10: the middleware no longer logs exceptions a handler reports as handled
    logger.UnhandledException(exception, httpContext.Request.Method, httpContext.Request.Path);

    httpContext.Response.StatusCode = StatusCodes.Status500InternalServerError;
    return await problemDetailsService.TryWriteAsync(new ProblemDetailsContext
    {
        HttpContext = httpContext,
        Exception = exception,
        ProblemDetails = { Title = "An unexpected error occurred." },
    });
}
```

## OpenAPI
`builder.Services.AddOpenApi();` plus `app.MapOpenApi();` (serves `/openapi/v1.json`;
Development only unless the repo publishes it). The document is OpenAPI 3.1 by default in .NET 10.
`WithOpenApi()` is deprecated in .NET 10. Templates have not included Swashbuckle since .NET 9;
keep it only where the repo already uses it.

## Configuration
Later sources override earlier ones: `appsettings.json` < `appsettings.{Environment}.json` <
user secrets (Development only) < environment variables < command-line arguments.
Nested keys in environment variables use `__` (`Catalog__BaseAddress`).
Bind and validate options at startup:

```csharp
services.AddOptions<CatalogOptions>()
    .BindConfiguration(CatalogOptions.SectionName)
    .ValidateDataAnnotations()
    .ValidateOnStart();
```

## Authentication (ask before changing auth)
Validate tokens from an identity provider (Entra ID, Keycloak, Auth0, ...) using asymmetric
keys from its OIDC metadata. Do not mint or validate tokens with a symmetric secret kept in
config, unless the repo already does and the user agrees.

```csharp
services.AddAuthentication().AddJwtBearer(options =>
{
    // Tokens come from an identity provider; signing keys are read from its
    // OpenID Connect metadata, so the API never holds a shared signing secret.
    options.Authority = configuration["Auth:Authority"];
    options.Audience = configuration["Auth:Audience"];
});
services.AddAuthorization();
```

.NET 10: cookie authentication now answers known API endpoints with 401/403 instead of
redirecting to a login page.

## HttpClient
Never `new HttpClient()` per call. Pick one approach:
- **Typed client** (registered as transient). Do not inject it into a singleton:
  that captures the handler and stops DNS refresh.
- **Keyed client** (.NET 9+): `AddHttpClient("name").AddAsKeyed()`, then inject
  `[FromKeyedServices("name")] HttpClient`. It is scoped by default.
  `ConfigureHttpClientDefaults(b => b.AddAsKeyed())` turns it on for every name.
  Per-name `AddAsKeyed`/`RemoveAsKeyed` calls override the defaults, whatever the call order.
- Only if a client must live in a singleton: `AddAsKeyed(ServiceLifetime.Singleton)` plus
  `UseSocketsHttpHandler((h, _) => h.PooledConnectionLifetime = TimeSpan.FromMinutes(2))`
  and `SetHandlerLifetime(Timeout.InfiniteTimeSpan)`. Making the consumer a singleton
  does not fix a captured client.

```csharp
services.AddHttpClient<CatalogClient>((serviceProvider, client) =>
    {
        var options = serviceProvider.GetRequiredService<IOptions<CatalogOptions>>().Value;
        client.BaseAddress = new Uri(options.BaseAddress);
    })
    .AddStandardResilienceHandler(options => options.Retry.DisableForUnsafeHttpMethods());
```

## Resilience (`Microsoft.Extensions.Http.Resilience`)
`AddStandardResilienceHandler()` defaults, outermost first:
| Strategy | Default |
|---|---|
| Rate limiter | 1000 permits, queue 0 |
| Total timeout | 30 s |
| Retry | 3 retries, exponential + jitter, 2 s base delay |
| Circuit breaker | failure ratio 10%, minimum throughput 100, sampling 30 s, break 5 s |
| Attempt timeout | 10 s |

- Add one resilience handler per client; don't stack them. Use
  `RemoveAllResilienceHandlers()` to replace one set by `ConfigureHttpClientDefaults`.
- Retries cover all methods by default; `DisableForUnsafeHttpMethods()` stops retrying POST/PUT/PATCH/DELETE/CONNECT.
- Telemetry: meter `Polly`, instruments `resilience.polly.strategy.events`,
  `resilience.polly.strategy.attempt.duration`, `resilience.polly.pipeline.duration`.

## Sources
Last verified: 2026-10-18. Samples compile and are exercised by tests in `verify/`.
- https://learn.microsoft.com/en-us/aspnet/core/release-notes/aspnetcore-10.0
- https://learn.microsoft.com/en-us/aspnet/core/breaking-changes/10/overview
- https://learn.microsoft.com/en-us/aspnet/core/fundamentals/configuration/
- https://learn.microsoft.com/en-us/aspnet/core/fundamentals/error-handling-api
- https://learn.microsoft.com/en-us/dotnet/core/extensions/httpclient-factory-keyed-di
- https://learn.microsoft.com/en-us/dotnet/core/resilience/http-resilience
- https://www.pollydocs.org/advanced/telemetry.html
