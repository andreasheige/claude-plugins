using System.Diagnostics;
using OpenTelemetry;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

namespace Samples.Observability;

public static class Telemetry
{
    public const string SourceName = "Samples";

    public static readonly ActivitySource ActivitySource = new(SourceName);

    public static IServiceCollection AddTelemetry(this IServiceCollection services, IHostEnvironment environment)
    {
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

        return services;
    }
}
