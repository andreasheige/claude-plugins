---
name: dotnet-observability
description: .NET logging, tracing and metrics: Serilog two-stage bootstrap, OpenTelemetry setup with sampler and OTLP, LoggerMessage source generation, ActivitySource, current semantic-convention names, Aspire dashboard for local viewing.
paths: ["**/*.cs", "**/*.csproj", "**/*.sln*", "**/*.razor", "**/*.cshtml"]
---

# Observability

Keep the repo's logging library and telemetry backend (Application Insights, Datadog,
OTLP collector, ...). The setup below is the default for a new service.

## Serilog two-stage bootstrap
A bootstrap logger catches startup failures. The real logger is configured from
`appsettings` once DI exists.

```csharp
Log.Logger = new LoggerConfiguration()
    .WriteTo.Console(formatProvider: CultureInfo.InvariantCulture)
    .CreateBootstrapLogger();
```

```csharp
builder.Services.AddSerilog((services, configuration) => configuration
    .ReadFrom.Configuration(builder.Configuration)
    .ReadFrom.Services(services)
    .Enrich.FromLogContext()
    .WriteTo.Console(formatProvider: CultureInfo.InvariantCulture)
    .WriteTo.OpenTelemetry());
```

```csharp
catch (Exception ex) when (ex is not HostAbortedException)
{
    Log.Fatal(ex, "Host terminated unexpectedly");
}
finally
{
    await Log.CloseAndFlushAsync();
}
```

`HostAbortedException` signals a deliberate host abort, e.g. from `dotnet ef` or other tools
that build the host and then stop it. Don't log it as fatal.
Serilog replaces the `ILogger` providers, so logs reach OTLP through
`Serilog.Sinks.OpenTelemetry`, not through OpenTelemetry's logging provider. Pick one log
pipeline; two would send every line twice.

## OpenTelemetry traces and metrics

```csharp
services.AddOpenTelemetry()
    .ConfigureResource(resource => resource.AddService(environment.ApplicationName))
    .WithTracing(tracing => tracing
        .AddSource(SourceName)
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddEntityFrameworkCoreInstrumentation() // beta package: pin it, expect renames
        .SetSampler(new ParentBasedSampler(new TraceIdRatioBasedSampler(0.25))))
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddMeter("System.Runtime") // built-in runtime metrics, .NET 9+
        .AddMeter("Polly"))         // resilience.polly.* instruments
    .UseOtlpExporter();             // honours OTEL_EXPORTER_OTLP_ENDPOINT / _PROTOCOL
```

- `ParentBasedSampler` must be given a root sampler. It follows the caller's sampling
  decision and samples new root traces by ratio. The SDK default is
  `ParentBased(AlwaysOn)`, which records every trace.
- `OpenTelemetry.Instrumentation.EntityFrameworkCore` is **prerelease** (`-beta`). Its span
  attributes can change between versions; pin the version and check the changelog when upgrading.
- `UseOtlpExporter()` configures every signal at once. Don't also call `AddOtlpExporter()` per signal.
- .NET 10: the default propagator is now W3C. It sends `baggage` instead of
  `Correlation-Context`; `DistributedContextPropagator.CreatePreW3CPropagator()` restores
  the old one.
- .NET 10 also has a narrow sampling change: `PropagationData` with a recorded parent no
  longer sets `Recorded`. The OTel parent-based sampler is unaffected.

## Semantic-convention names (stable HTTP conventions)
Metrics: `http.server.request.duration`, `http.client.request.duration` (seconds).
Metric attributes: `http.request.method`, `http.response.status_code`, `http.route` (server),
`url.scheme`, `server.address`, `error.type`. `url.path` exists on spans only, not on metrics. The old names (`http.method`,
`http.status_code`, `http.url`) are obsolete; don't use them in queries or dashboards.

## Structured logging
Named placeholders, never interpolation. Source-generated methods for hot paths:

```csharp
internal static partial class TodoLog
{
    [LoggerMessage(Level = LogLevel.Information, Message = "Created todo {TodoId} with priority {Priority}")]
    public static partial void TodoCreated(this ILogger logger, int todoId, int priority);
```

Don't log secrets or PII. Turn on EF `EnableSensitiveDataLogging()` only in Development.

## Custom spans

```csharp
public static readonly ActivitySource ActivitySource = new(SourceName);
```

Register the source name with `.AddSource(...)`, otherwise its activities are dropped.
`StartActivity` returns `null` when nobody listens, so use `activity?.SetTag(...)`.

## Local viewing: standalone Aspire dashboard

```bash
docker run --rm -it -p 18888:18888 -p 4317:18889 -p 4318:18890 -d --name aspire-dashboard mcr.microsoft.com/aspire/dashboard:latest
```

Then set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` on the app and open
http://localhost:18888 (the login token is printed in the container log). Older docs use
`mcr.microsoft.com/dotnet/aspire-dashboard`; the current image is `mcr.microsoft.com/aspire/dashboard`.

## Sources
Last verified: 2026-10-18. C# samples compile in `verify/`; the docker command is from the docs and was not run.
- https://learn.microsoft.com/en-us/dotnet/core/diagnostics/observability-with-otel
- https://learn.microsoft.com/en-us/dotnet/core/extensions/logger-message-generator
- https://learn.microsoft.com/en-us/aspnet/core/log-mon/metrics/built-in
- https://learn.microsoft.com/en-us/dotnet/core/compatibility/10
- https://opentelemetry.io/docs/specs/semconv/http/http-metrics/
- https://github.com/serilog/serilog-aspnetcore#two-stage-initialization
- https://aspire.dev/dashboard/standalone/
