using Serilog;
using SDDTemplate.Site;
using SDDTemplate.Site.Components;

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

_ = builder.Host.UseSerilog((context, services, loggerConfiguration) => loggerConfiguration
    .ReadFrom.Configuration(context.Configuration)
    .ReadFrom.Services(services)
    .Enrich.FromLogContext());

// Add services to the container.
_ = builder.Services.AddRazorComponents();

WebApplication app = builder.Build();

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

_ = app.UseAntiforgery();

_ = app.MapGet("/health", (IHostEnvironment environment) =>
    Results.Ok(new HealthResponse("ok", environment.EnvironmentName, DateTimeOffset.UtcNow)));

_ = app.MapGet("/metrics", () => Results.Text(
    "# HELP sddtemplate_health Application health status.`n" +
    "# TYPE sddtemplate_health gauge`n" +
    "sddtemplate_health 1`n",
    "text/plain; version=0.0.4"));

_ = app.MapStaticAssets();
_ = app.MapRazorComponents<App>();

app.Run();

[System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]
public sealed partial class Program;
