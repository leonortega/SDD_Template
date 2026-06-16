using Serilog;
using SDDTemplate.Site.Components;
using SDDTemplate.Common.Observability;

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

Log.Logger.Information("Configuring Site host");

_ = builder.Host.UseStandardSerilog();

_ = builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();
_ = builder.Services.AddHttpClient();

WebApplication app = builder.Build();
Log.Logger.Information("Starting Site app initialization");

if (!app.Environment.IsDevelopment())
{
    _ = app.UseExceptionHandler("/Error", createScopeForErrors: true);
    _ = app.UseHsts();
}
_ = app.UseWhen(
    context => !context.Request.Path.StartsWithSegments("/api"),
    branch => branch.UseStatusCodePagesWithReExecute("/not-found", createScopeForStatusCodePages: true));
_ = app.UseHttpsRedirection();
_ = app.UseCorrelationId();
_ = app.UseCorrelationAwareRequestLogging();

_ = app.UseAntiforgery();
Log.Logger.Debug("Site antiforgery middleware enabled");

_ = app.MapGet("/health", (IHostEnvironment environment) =>
    Results.Ok(new HealthResponse("ok", environment.EnvironmentName, DateTimeOffset.UtcNow)));
Log.Logger.Debug("Site health endpoint mapped");

_ = app.MapStaticAssets();
_ = app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();
Log.Logger.Information("Site static assets and Razor components mapped");

app.Run();

[System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]
public sealed partial class Program;
