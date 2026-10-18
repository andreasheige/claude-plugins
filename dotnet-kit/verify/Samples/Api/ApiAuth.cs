namespace Samples.Api;

public static class ApiAuth
{
    public static IServiceCollection AddApiAuth(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddAuthentication().AddJwtBearer(options =>
        {
            // Tokens come from an identity provider; signing keys are read from its
            // OpenID Connect metadata, so the API never holds a shared signing secret.
            options.Authority = configuration["Auth:Authority"];
            options.Audience = configuration["Auth:Audience"];
        });
        services.AddAuthorization();

        return services;
    }
}
