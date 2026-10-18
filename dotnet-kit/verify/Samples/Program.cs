using System.Globalization;
using Microsoft.EntityFrameworkCore;
using Samples.Api;
using Samples.Data;
using Samples.Observability;
using Serilog;

Log.Logger = new LoggerConfiguration()
    .WriteTo.Console(formatProvider: CultureInfo.InvariantCulture)
    .CreateBootstrapLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);

    builder.Services.AddSerilog((services, configuration) => configuration
        .ReadFrom.Configuration(builder.Configuration)
        .ReadFrom.Services(services)
        .Enrich.FromLogContext()
        .WriteTo.Console(formatProvider: CultureInfo.InvariantCulture)
        .WriteTo.OpenTelemetry());

    builder.Services.AddTelemetry(builder.Environment);
    builder.Services.AddProblemDetails();
    builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
    builder.Services.AddValidation();
    builder.Services.AddOpenApi();
    builder.Services.AddApiAuth(builder.Configuration);
    builder.Services.AddCatalogClient();
    builder.Services.AddDbContext<AppDbContext>((services, options) => options
        .UseSqlite(services.GetRequiredService<IConfiguration>().GetConnectionString("Todos")));

    var app = builder.Build();

    app.UseExceptionHandler();
    app.UseStatusCodePages();
    app.UseAuthentication();
    app.UseAuthorization();

    if (app.Environment.IsDevelopment())
    {
        app.MapOpenApi();
    }

    app.MapTodoEndpoints();
    app.MapGet("/boom", () => { throw new InvalidOperationException("Simulated failure"); });

    await app.RunAsync();
}
catch (Exception ex) when (ex is not HostAbortedException)
{
    Log.Fatal(ex, "Host terminated unexpectedly");
}
finally
{
    await Log.CloseAndFlushAsync();
}
