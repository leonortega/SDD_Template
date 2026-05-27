using SDDTemplate.Site.Components;

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

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
_ = app.UseStatusCodePagesWithReExecute("/not-found", createScopeForStatusCodePages: true);
_ = app.UseHttpsRedirection();

_ = app.UseAntiforgery();

_ = app.MapStaticAssets();
_ = app.MapRazorComponents<App>();

app.Run();

[System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]
internal sealed partial class Program;
