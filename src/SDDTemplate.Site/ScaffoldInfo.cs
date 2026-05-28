namespace SDDTemplate.Site
{
    public static class ScaffoldInfo
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
