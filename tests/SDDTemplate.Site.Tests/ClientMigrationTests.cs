namespace SDDTemplate.Site.Tests
{
    public sealed class ClientMigrationTests
    {
        [Fact]
        public void InitialClientMigrationCreatesClientColumns()
        {
            DirectoryInfo repositoryRoot = FindRepositoryRoot();
            string migrationsRoot = Path.Combine(
                repositoryRoot.FullName,
                "src",
                "SDDTemplate.Data",
                "Migrations");
            string migration = File.ReadAllText(Directory.GetFiles(migrationsRoot, "*_InitialClientStorage.cs").Single());

            Assert.Contains("name: \"Clients\"", migration);
            Assert.Contains("Name = table.Column<string>", migration);
            Assert.Contains("LastName = table.Column<string>", migration);
            Assert.Contains("Address = table.Column<string>", migration);
            Assert.Contains("BornDate = table.Column<DateOnly>", migration);
            Assert.Contains("City = table.Column<string>", migration);
            Assert.Contains("Country = table.Column<string>", migration);
            Assert.Contains("ZipCode = table.Column<string>", migration);
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
