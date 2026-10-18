using System.ComponentModel.DataAnnotations;
using Microsoft.Extensions.Http.Resilience;
using Microsoft.Extensions.Options;

namespace Samples.Api;

public sealed class CatalogOptions
{
    public const string SectionName = "Catalog";

    [Required, Url]
    public required string BaseAddress { get; init; }
}

public sealed record CatalogItem(int Id, string Name);

// Typed client: transient, gets a pooled handler from IHttpClientFactory
public sealed class CatalogClient(HttpClient httpClient)
{
    public Task<CatalogItem?> GetItemAsync(int id, CancellationToken cancellationToken) =>
        httpClient.GetFromJsonAsync<CatalogItem>(new Uri($"items/{id}", UriKind.Relative), cancellationToken);
}

public static class CatalogRegistration
{
    public static IServiceCollection AddCatalogClient(this IServiceCollection services)
    {
        services.AddOptions<CatalogOptions>()
            .BindConfiguration(CatalogOptions.SectionName)
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services.AddHttpClient<CatalogClient>((serviceProvider, client) =>
            {
                var options = serviceProvider.GetRequiredService<IOptions<CatalogOptions>>().Value;
                client.BaseAddress = new Uri(options.BaseAddress);
            })
            .AddStandardResilienceHandler(options => options.Retry.DisableForUnsafeHttpMethods());

        // Keyed alternative (.NET 9+): inject with [FromKeyedServices("github")] HttpClient
        services.AddHttpClient("github", client => client.BaseAddress = new Uri("https://api.github.com/"))
            .AddAsKeyed();

        return services;
    }
}
