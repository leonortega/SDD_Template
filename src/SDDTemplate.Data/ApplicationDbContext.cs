using Microsoft.EntityFrameworkCore;
using SDDTemplate.Data.Clients;
using SDDTemplate.Data.Products;

namespace SDDTemplate.Data
{
    public sealed class ApplicationDbContext(DbContextOptions<ApplicationDbContext> options) : DbContext(options)
    {
        public DbSet<Client> Clients => Set<Client>();

        public DbSet<Product> Products => Set<Product>();

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

            _ = modelBuilder.Entity<Product>(product =>
            {
                _ = product.ToTable("Products");
                _ = product.HasKey(item => item.Id);

                _ = product.Property(item => item.Name).HasMaxLength(100).IsRequired();
                _ = product.Property(item => item.Sku).HasMaxLength(40).IsRequired();
                _ = product.HasIndex(item => item.Sku).IsUnique();
                _ = product.Property(item => item.Status).HasMaxLength(40).IsRequired();
                _ = product.Property(item => item.Price).HasPrecision(18, 2).IsRequired();
                _ = product.Property(item => item.Category).HasMaxLength(100).IsRequired();
                _ = product.Property(item => item.LastUpdated).IsRequired();
            });
        }
    }
}
