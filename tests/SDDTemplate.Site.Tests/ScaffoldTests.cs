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

            Assert.Contains($"<TargetFramework>{TestScaffoldInfo.TargetFramework}</TargetFramework>", projectXml);
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

            Assert.False(TestScaffoldInfo.IsTemplateSampleContent(markup));
        }

        [Fact]
        public void BlankSiteDefinesWhitePageBackground()
        {
            string appCss = Path.Combine(
                FindRepositoryRoot().FullName,
                "src",
                "SDDTemplate.Site",
                "wwwroot",
                "app.css");

            string styles = File.ReadAllText(appCss);

            Assert.Contains("html,", styles);
            Assert.Contains("body", styles);
            Assert.Contains("background: #fff;", styles);
        }

        public static TheoryData<string> RequiredFiles()
        {
            return [.. TestScaffoldInfo.RequiredFiles];
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

        private static class TestScaffoldInfo
        {
            public const string TargetFramework = "net10.0";

            public static IReadOnlyList<string> RequiredFiles { get; } =
            [
                "Program.cs",
                "Components/App.razor",
                "Components/Routes.razor",
                "Components/Layout/MainLayout.razor",
                "Components/Pages/Home.razor",
                "HealthResponse.cs",
                "wwwroot/app.css",
            ];

            public static bool IsTemplateSampleContent(string markup)
            {
                return markup.Contains("Hello, world!", StringComparison.Ordinal) ||
                    markup.Contains("Welcome to your new app.", StringComparison.Ordinal);
            }
        }
    }
}
