using Serilog;
using SDDTemplate.Site;
using SDDTemplate.Site.Components;
using SDDTemplate.Common.Observability;

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

Log.Logger.Information("Configuring Site host");

_ = builder.Host.UseSerilog((context, services, loggerConfiguration) => loggerConfiguration
    .ReadFrom.Configuration(context.Configuration)
    .ReadFrom.Services(services)
    .Enrich.FromLogContext());

// Add services to the container.
_ = builder.Services.AddRazorComponents();

WebApplication app = builder.Build();
Log.Logger.Information("Starting Site app initialization");

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    _ = app.UseExceptionHandler("/Error", createScopeForErrors: true);
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    _ = app.UseHsts();
}
_ = app.UseWhen(
    context => !context.Request.Path.StartsWithSegments("/api"),
    branch => branch.UseStatusCodePagesWithReExecute("/not-found", createScopeForStatusCodePages: true));
_ = app.UseHttpsRedirection();
_ = app.UseCorrelationId();
_ = app.UseSerilogRequestLogging(options =>
{
    options.EnrichDiagnosticContext = (diagnosticContext, httpContext) =>
    {
        diagnosticContext.Set("CorrelationId", httpContext.GetCorrelationId());
        diagnosticContext.Set("RequestPath", httpContext.Request.Path.Value ?? string.Empty);
        diagnosticContext.Set("RequestMethod", httpContext.Request.Method);
    };
});

_ = app.UseAntiforgery();
Log.Logger.Debug("Site antiforgery middleware enabled");

_ = app.MapGet("/health", (IHostEnvironment environment) =>
    Results.Ok(new HealthResponse("ok", environment.EnvironmentName, DateTimeOffset.UtcNow)));
Log.Logger.Debug("Site health endpoint mapped");

_ = app.MapStaticAssets();
_ = app.MapRazorComponents<App>();
Log.Logger.Information("Site static assets and Razor components mapped");

app.Run();

[System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]
public sealed partial class Program;
