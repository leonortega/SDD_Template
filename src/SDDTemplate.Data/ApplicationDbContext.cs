using Microsoft.EntityFrameworkCore;
using SDDTemplate.Data.Clients;

namespace SDDTemplate.Data
{
    public sealed class ApplicationDbContext(DbContextOptions<ApplicationDbContext> options) : DbContext(options)
    {
        public DbSet<Client> Clients => Set<Client>();

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            _ = modelBuilder.Entity<Client>(client =>
            {
                _ = client.ToTable("Clients");
                _ = client.HasKey(item => item.Id);

                _ = client.Property(item => item.Name).HasMaxLength(100).IsRequired();
                _ = client.Property(item => item.LastName).HasMaxLength(100).IsRequired();
                _ = client.Property(item => item.Address).HasMaxLength(200).IsRequired();
                _ = client.Property(item => item.BornDate).IsRequired();
                _ = client.Property(item => item.City).HasMaxLength(100).IsRequired();
                _ = client.Property(item => item.Country).HasMaxLength(100).IsRequired();
                _ = client.Property(item => item.ZipCode).HasMaxLength(12).IsRequired();
            });
        }
    }
}
