using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace SDDTemplate.Data
{
    public static class DatabaseSetup
    {
        public static IServiceCollection AddApplicationDatabase(this IServiceCollection services, IConfiguration configuration, IHostEnvironment environment)
        {
            string defaultPath = Path.Combine(environment.ContentRootPath, "App_Data", "sddtemplate.db");
            string connectionString = configuration.GetConnectionString("ClientsDb") ?? $"Data Source={defaultPath}";

            return services.AddDbContext<ApplicationDbContext>(options => options.UseSqlite(connectionString));
        }

        public static async Task MigrateApplicationDatabaseAsync(this IServiceProvider services)
        {
            using IServiceScope scope = services.CreateScope();
            ApplicationDbContext db = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

            string? dataSource = db.Database.GetDbConnection().DataSource;
            if (!string.IsNullOrWhiteSpace(dataSource) && dataSource != ":memory:")
            {
                string? directory = Path.GetDirectoryName(Path.GetFullPath(dataSource));
                if (!string.IsNullOrWhiteSpace(directory))
                {
                    _ = Directory.CreateDirectory(directory);
                }
            }

            await db.Database.MigrateAsync();
        }
    }
}
