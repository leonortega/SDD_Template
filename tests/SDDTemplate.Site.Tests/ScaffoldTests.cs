namespace SDDTemplate.Site.Tests
{
    public sealed class ScaffoldTests
    {
        [Fact]
        public void SiteProjectTargetsNet10()
        {
            FileInfo projectFile = FindRepositoryRoot()
                .GetFiles("SDDTemplate.Site.csproj", SearchOption.AllDirectories)
                .Single(file => file.FullName.Contains(Path.Combine("src", "SDDTemplate.Site")));

            string projectXml = File.ReadAllText(projectFile.FullName);

            Assert.Contains($"<TargetFramework>{ScaffoldInfo.TargetFramework}</TargetFramework>", projectXml);
        }

        [Theory]
        [MemberData(nameof(RequiredFiles))]
        public void SiteProjectContainsStandardBlazorScaffoldFiles(string relativePath)
        {
            string siteRoot = Path.Combine(FindRepositoryRoot().FullName, "src", "SDDTemplate.Site");
            string filePath = Path.Combine(siteRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));

            Assert.True(File.Exists(filePath), $"Expected scaffold file '{relativePath}' to exist.");
        }

        [Fact]
        public void HomePageRemainsMinimal()
        {
            string homePage = Path.Combine(
                FindRepositoryRoot().FullName,
                "src",
                "SDDTemplate.Site",
                "Components",
                "Pages",
                "Home.razor");

            string markup = File.ReadAllText(homePage);

            Assert.False(ScaffoldInfo.IsTemplateSampleContent(markup));
        }

        public static TheoryData<string> RequiredFiles()
        {
            return [.. ScaffoldInfo.RequiredFiles];
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
