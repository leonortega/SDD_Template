using Serilog;
using SDDTemplate.Api.Clients;
using SDDTemplate.Common.Observability;
using SDDTemplate.Data;

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

Log.Logger.Information("Configuring API host");

_ = builder.Host.UseStandardSerilog();

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
Log.Logger.Information("Starting API app initialization");
await app.Services.MigrateApplicationDatabaseAsync();
Log.Logger.Debug("API database migration completed");

if (!app.Environment.IsDevelopment())
{
    _ = app.UseExceptionHandler("/error");
    _ = app.UseHsts();
}

_ = app.UseHttpsRedirection();
_ = app.UseCorrelationId();
_ = app.UseCorrelationAwareRequestLogging();
if (allowedOrigins.Length > 0)
{
    _ = app.UseCors("ConfiguredSiteOrigins");
    Log.Logger.Information("API CORS enabled with {OriginCount} configured origins", allowedOrigins.Length);
}

_ = app.MapGet("/health", (IHostEnvironment environment) =>
    Results.Ok(new HealthResponse("ok", environment.EnvironmentName, DateTimeOffset.UtcNow)));
Log.Logger.Debug("API health endpoint mapped");

_ = app.Map("/error", errorApp =>
    errorApp.Run(context =>
        Results.Problem(statusCode: StatusCodes.Status500InternalServerError, title: "An unexpected error occurred.")
            .ExecuteAsync(context)));

if (app.Environment.IsEnvironment("Testing"))
{
    _ = app.MapGet("/__test/throw", _ => throw new InvalidOperationException("Intentional test exception."));
}

_ = app.MapClientEndpoints();
Log.Logger.Information("API client endpoints mapped");

app.Run();

namespace SDDTemplate.Api
{
    [System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]
    public sealed partial class Program;
}
