namespace SDDTemplate.Site.Tests
{
    public sealed class ProductMigrationTests
    {
        [Fact]
        public void ProductMigrationCreatesProductColumnsAndSkuIndex()
        {
            DirectoryInfo repositoryRoot = FindRepositoryRoot();
            string migrationsRoot = Path.Combine(
                repositoryRoot.FullName,
                "src",
                "SDDTemplate.Data",
                "Migrations");
            string migration = File.ReadAllText(Directory.GetFiles(migrationsRoot, "*_AddProductStorage.cs").Single());

            Assert.Contains("name: \"Products\"", migration);
            Assert.Contains("Name = table.Column<string>", migration);
            Assert.Contains("Sku = table.Column<string>", migration);
            Assert.Contains("Status = table.Column<string>", migration);
            Assert.Contains("Price = table.Column<decimal>", migration);
            Assert.Contains("Category = table.Column<string>", migration);
            Assert.Contains("LastUpdated = table.Column<DateTimeOffset>", migration);
            Assert.Contains("name: \"IX_Products_Sku\"", migration);
            Assert.Contains("unique: true", migration);
        }

        private static DirectoryInfo FindRepositoryRoot()
        {
            DirectoryInfo? current = new(AppContext.BaseDirectory);

            while (current is not null && !File.Exists(Path.Combine(current.FullName, "SDDTemplate.slnx")))
            {
                current = current.Parent;
            }

            return current ?? throw new DirectoryNotFoundException("Could not locate repository root.");
        }
    }
}
