using Serilog;
using SDDTemplate.Api;
using SDDTemplate.Api.Clients;
using SDDTemplate.Data;

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

_ = builder.Host.UseSerilog((context, services, loggerConfiguration) => loggerConfiguration
    .ReadFrom.Configuration(context.Configuration)
    .ReadFrom.Services(services)
    .Enrich.FromLogContext());

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

_ = app.MapClientEndpoints();

app.Run();

namespace SDDTemplate.Api
{
    public sealed record HealthResponse(string Status, string Environment, DateTimeOffset Timestamp);

    [System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]
    public sealed class ApiAssemblyMarker;
}
