using SDDTemplate.Api;
using SDDTemplate.Api.Clients;
using SDDTemplate.Data;

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

_ = builder.Services.AddApplicationDatabase(builder.Configuration, builder.Environment);
string[] allowedOrigins = builder.Configuration.GetSection("Cors:AllowedOrigins").Get<string[]>() ?? [];
if (allowedOrigins.Length > 0)
{
    _ = builder.Services.AddCors(options =>
        options.AddPolicy("ConfiguredSiteOrigins", policy =>
            _ = policy
                .WithOrigins(allowedOrigins)
                .AllowAnyHeader()
                .AllowAnyMethod()));
}

WebApplication app = builder.Build();
await app.Services.MigrateApplicationDatabaseAsync();

if (!app.Environment.IsDevelopment())
{
    _ = app.UseExceptionHandler("/error");
    _ = app.UseHsts();
}

_ = app.UseHttpsRedirection();
if (allowedOrigins.Length > 0)
{
    _ = app.UseCors("ConfiguredSiteOrigins");
}

_ = app.MapGet("/health", (IHostEnvironment environment) =>
    Results.Ok(new HealthResponse("ok", environment.EnvironmentName, DateTimeOffset.UtcNow)));

_ = app.MapGet("/metrics", () => Results.Text(
    "# HELP sddtemplate_api_health Application API health status.`n" +
    "# TYPE sddtemplate_api_health gauge`n" +
    "sddtemplate_api_health 1`n",
    "text/plain; version=0.0.4"));

_ = app.MapClientEndpoints();

app.Run();

namespace SDDTemplate.Api
{
    public sealed record HealthResponse(string Status, string Environment, DateTimeOffset Timestamp);

    [System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]
    public sealed class ApiAssemblyMarker;
}
