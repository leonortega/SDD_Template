using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace SDDTemplate.DeliveryTools
{
    public static partial class DeliveryWorkflowHelpers
    {
        public static string ReadDeliveryPolicyTicketKeyPattern(string path)
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            return document.RootElement.TryGetProperty("ticketKeyPattern", out JsonElement pattern)
                && !string.IsNullOrWhiteSpace(pattern.GetString())
                    ? pattern.GetString()!
                    : throw new InvalidOperationException("delivery-policy.json must define ticketKeyPattern.");
        }

        public static string ExtractTicketKey(string commitMessage, string ticketKeyPattern, string fallback = "")
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(ticketKeyPattern);

            string firstLine = commitMessage.Replace("\r\n", "\n").Split('\n')[0];
            Match direct = Regex.Match(firstLine, $"^({ticketKeyPattern}): ", RegexOptions.CultureInvariant);
            if (direct.Success)
            {
                return direct.Groups[1].Value;
            }

            Match merge = Regex.Match(firstLine, $"^Merge pull request '({ticketKeyPattern}):", RegexOptions.CultureInvariant);
            return merge.Success ? merge.Groups[1].Value : fallback;
        }

        public static int ReadCoverageThreshold(string path, int fallback)
        {
            return File.Exists(path) ? ReadCoverageThresholdFromFile(path, fallback) : fallback;
        }

        public static decimal ReadCoberturaCoveragePercent(string path)
        {
            XDocument document = XDocument.Load(path);
            string? lineRate = document.Root?.Attribute("line-rate")?.Value;
            return !string.IsNullOrWhiteSpace(lineRate)
                && decimal.TryParse(lineRate, NumberStyles.Float, CultureInfo.InvariantCulture, out decimal rate)
                    ? Math.Round(rate * 100m, 2, MidpointRounding.AwayFromZero)
                    : throw new InvalidOperationException($"Could not read line-rate from {path}.");
        }

        public static ReleaseManifestValidation ValidateReleaseManifest(string path)
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            JsonElement root = document.RootElement;
            List<string> errors = [];

            foreach (string field in new[] { "schemaVersion", "commitSha", "checksum", "artifactUrl", "planeTicketKey", "versionStatus" })
            {
                if (!root.TryGetProperty(field, out JsonElement value) || IsMissing(value))
                {
                    errors.Add($"Missing required field: {field}");
                }
            }

            if (root.TryGetProperty("commitSha", out JsonElement commitSha)
                && !Regex.IsMatch(commitSha.GetString() ?? string.Empty, "^[0-9a-fA-F]{7,40}$", RegexOptions.CultureInvariant))
            {
                errors.Add("commitSha must be 7 to 40 hex characters.");
            }

            if (root.TryGetProperty("sourceRcVersion", out JsonElement sourceRcVersion)
                && !IsMissing(sourceRcVersion)
                && !Regex.IsMatch(sourceRcVersion.GetString() ?? string.Empty, "^v[0-9]+\\.[0-9]+\\.[0-9]+-rc\\.[0-9]+$", RegexOptions.CultureInvariant))
            {
                errors.Add("sourceRcVersion must use vMAJOR.MINOR.PATCH-rc.N.");
            }

            if (root.TryGetProperty("finalReleaseVersion", out JsonElement finalReleaseVersion)
                && !IsMissing(finalReleaseVersion)
                && !Regex.IsMatch(finalReleaseVersion.GetString() ?? string.Empty, "^v[0-9]+\\.[0-9]+\\.[0-9]+$", RegexOptions.CultureInvariant))
            {
                errors.Add("finalReleaseVersion must use vMAJOR.MINOR.PATCH.");
            }

            return new ReleaseManifestValidation(path, errors.Count == 0, errors);
        }

        public static void CreateReleaseManifest(
            string outputPath,
            string commitSha,
            string checksum,
            string artifactUrl,
            string planeTicketKey,
            string versionStatus)
        {
            SortedDictionary<string, object?> manifest = new()
            {
                ["schemaVersion"] = 1,
                ["commitSha"] = commitSha,
                ["checksum"] = checksum,
                ["artifactUrl"] = artifactUrl,
                ["planeTicketKey"] = planeTicketKey,
                ["versionStatus"] = versionStatus,
            };

            string? parent = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrWhiteSpace(parent))
            {
                _ = Directory.CreateDirectory(parent);
            }

            File.WriteAllText(outputPath, JsonSerializer.Serialize(manifest, new JsonSerializerOptions { WriteIndented = true }));
        }

        public static TicketReadinessResult ClassifyTicketReadiness(string title, string description)
        {
            string text = Normalize($"{title}\n{description}");
            List<string> missing = [];

            if (string.IsNullOrWhiteSpace(text) || text.Length < 30)
            {
                return new TicketReadinessResult("blocked", ["user-visible goal", "acceptance criteria", "validation expectation"]);
            }

            if (!HasAny(text, "as a ", "i want", "needs", "should", "must", "add ", "create ", "fix ", "update ", "implement ", "allow ", "prevent "))
            {
                missing.Add("user-visible goal");
            }

            if (!HasAny(text, "acceptance criteria", "given ", "when ", "then ", "- [ ]", "- ", "shall", "must", "should"))
            {
                missing.Add("acceptance criteria");
            }

            if (!HasAny(text, "test", "validate", "verify", "qa", "e2e", "coverage", "health", "curl", "playwright"))
            {
                missing.Add("validation expectation");
            }

            return missing.Contains("user-visible goal", StringComparer.Ordinal) || missing.Count >= 3
                ? new TicketReadinessResult("blocked", missing)
                : missing.Count == 0
                    ? new TicketReadinessResult("ready", [])
                    : new TicketReadinessResult("enrichable", missing);
        }

        public static DeliveryRiskResult ClassifyDeliveryRisk(IEnumerable<string> changedPaths, string contextText, int estimatedChangedLines)
        {
            string[] paths = [.. changedPaths.Select(path => path.Replace('\\', '/'))];
            string combined = Normalize($"{string.Join('\n', paths)}\n{contextText}");
            List<string> reasons = [];

            string[] highRiskTerms =
            [
                "auth",
                "authorization",
                "authentication",
                "secret",
                "token",
                "password",
                "migration",
                "deployment",
                "rollback",
                "hotfix",
                "public api",
                "/health",
                "release.json",
                "nexus",
                "azure",
                "gitea/workflows",
                "infra/deployment",
                "infra/azure",
                "appsettings",
                "program.cs",
                ".csproj",
            ];

            foreach (string term in highRiskTerms)
            {
                if (combined.Contains(term, StringComparison.Ordinal))
                {
                    reasons.Add($"high-risk surface: {term}");
                }
            }

            if (estimatedChangedLines >= 500)
            {
                reasons.Add("large diff >= 500 changed lines");
            }

            if (reasons.Count > 0)
            {
                return new DeliveryRiskResult("high", reasons);
            }

            int nonDocsPathCount = paths.Count(path => !IsDocumentationPath(path));
            return estimatedChangedLines > 80 || nonDocsPathCount > 1
                ? new DeliveryRiskResult("standard", ["normal implementation or multi-file review surface"])
                : new DeliveryRiskResult("low", ["localized low-risk change"]);
        }

        public static WorkloadForecast ParseWorkloadForecast(string markdown)
        {
            string risk = ReadForecastValue(markdown, "400-line budget risk");
            string chained = ReadForecastValue(markdown, "Chained PRs recommended");
            string decision = ReadForecastValue(markdown, "Decision needed before apply");
            string strategy = ReadForecastValue(markdown, "Delivery strategy", required: false);
            string estimated = ReadForecastValue(markdown, "Estimated changed lines", required: false);

            bool requiresDecision = IsYes(decision)
                || IsYes(chained)
                || risk.Equals("High", StringComparison.OrdinalIgnoreCase)
                || strategy.Equals("single-pr", StringComparison.OrdinalIgnoreCase);

            return new WorkloadForecast(
                string.IsNullOrWhiteSpace(estimated) ? "unknown" : estimated,
                string.IsNullOrWhiteSpace(risk) ? "Unknown" : risk,
                IsYes(chained),
                IsYes(decision),
                string.IsNullOrWhiteSpace(strategy) ? "unspecified" : strategy,
                requiresDecision);
        }

        public static AdversarialReviewTrigger DetectAdversarialReviewTrigger(
            IEnumerable<string> changedPaths,
            string contextText,
            int changedLines,
            bool explicitRequest)
        {
            DeliveryRiskResult risk = ClassifyDeliveryRisk(changedPaths, contextText, changedLines);
            bool required = explicitRequest || risk.Level == "high" || changedLines >= 500;
            List<string> reasons = [.. risk.Reasons];
            if (explicitRequest)
            {
                reasons.Insert(0, "explicit user request");
            }

            return new AdversarialReviewTrigger(required, required ? "adversarial" : "standard", reasons);
        }

        public static InstalledSkillIndex BuildInstalledSkillIndex(string root)
        {
            string skillRoot = Path.Combine(root, ".codex", "skills");
            List<InstalledSkillEntry> skills = [];

            if (!Directory.Exists(skillRoot))
            {
                return new InstalledSkillIndex(1, []);
            }

            foreach (string skillPath in Directory.EnumerateFiles(skillRoot, "SKILL.md", SearchOption.AllDirectories).Order(StringComparer.Ordinal))
            {
                string relativePath = Path.GetRelativePath(root, skillPath).Replace('\\', '/');
                if (relativePath.Contains("/_shared/", StringComparison.Ordinal) || relativePath.StartsWith(".codex/skills/_shared/", StringComparison.Ordinal))
                {
                    continue;
                }

                string content = File.ReadAllText(skillPath);
                FileInfo info = new(skillPath);
                skills.Add(new InstalledSkillEntry(
                    ReadFrontmatterValue(content, "name") ?? Path.GetFileName(Path.GetDirectoryName(skillPath)) ?? "unknown",
                    ReadFrontmatterValue(content, "description") ?? string.Empty,
                    "project",
                    relativePath,
                    info.Length,
                    info.LastWriteTimeUtc));
            }

            return new InstalledSkillIndex(1, skills);
        }

        public static SkillIndexWriteResult WriteInstalledSkillIndex(string root, string indexPath, string cachePath)
        {
            InstalledSkillIndex index = BuildInstalledSkillIndex(root);
            SkillIndexCache cache = new(1, [.. index.Skills.Select(skill => new SkillIndexFingerprint(skill.Path, skill.SizeBytes, skill.LastWriteTimeUtc))]);
            JsonSerializerOptions options = new() { WriteIndented = true };
            string cacheJson = JsonSerializer.Serialize(cache, options);
            bool cacheHit = File.Exists(indexPath)
                && File.Exists(cachePath)
                && string.Equals(File.ReadAllText(cachePath), cacheJson, StringComparison.Ordinal);

            if (!cacheHit)
            {
                _ = Directory.CreateDirectory(Path.GetDirectoryName(indexPath) ?? root);
                _ = Directory.CreateDirectory(Path.GetDirectoryName(cachePath) ?? root);
                File.WriteAllText(indexPath, JsonSerializer.Serialize(index, options));
                File.WriteAllText(cachePath, cacheJson);
            }

            return new SkillIndexWriteResult(indexPath, cachePath, index.Skills.Count, cacheHit);
        }

        private static int ReadCoverageThresholdFromFile(string path, int fallback)
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            return document.RootElement.TryGetProperty("coverage", out JsonElement coverage)
                && coverage.TryGetProperty("minimumPercent", out JsonElement minimum)
                && minimum.TryGetInt32(out int value)
                    ? value
                    : fallback;
        }

        private static bool IsMissing(JsonElement value)
        {
            return value.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined
                || (value.ValueKind == JsonValueKind.String && string.IsNullOrWhiteSpace(value.GetString()));
        }

        private static bool HasAny(string text, params string[] needles)
        {
            return needles.Any(needle => text.Contains(needle, StringComparison.Ordinal));
        }

        private static string Normalize(string text)
        {
            return Regex.Replace(text.ToLowerInvariant(), "\\s+", " ").Trim();
        }

        private static bool IsDocumentationPath(string path)
        {
            return path.StartsWith("docs/", StringComparison.Ordinal)
                || path.EndsWith(".md", StringComparison.OrdinalIgnoreCase)
                || path.EndsWith(".txt", StringComparison.OrdinalIgnoreCase);
        }

        private static string ReadForecastValue(string markdown, string key, bool required = true)
        {
            Match plain = Regex.Match(markdown, $"(?im)^\\s*{Regex.Escape(key)}\\s*:\\s*(.+?)\\s*$", RegexOptions.CultureInvariant);
            if (plain.Success)
            {
                return plain.Groups[1].Value.Trim();
            }

            Match table = Regex.Match(markdown, $"(?im)^\\s*\\|\\s*{Regex.Escape(key)}\\s*\\|\\s*(.+?)\\s*\\|\\s*$", RegexOptions.CultureInvariant);
            return table.Success
                ? table.Groups[1].Value.Trim()
                : required ? throw new InvalidOperationException($"Workload forecast is missing '{key}'.") : string.Empty;
        }

        private static bool IsYes(string value)
        {
            return value.Equals("yes", StringComparison.OrdinalIgnoreCase) || value.Equals("true", StringComparison.OrdinalIgnoreCase);
        }

        private static string? ReadFrontmatterValue(string content, string key)
        {
            if (!content.StartsWith("---", StringComparison.Ordinal))
            {
                return null;
            }

            Match frontmatter = Regex.Match(content, "(?s)^---\\s*(.*?)\\s*---", RegexOptions.CultureInvariant);
            if (!frontmatter.Success)
            {
                return null;
            }

            Match value = Regex.Match(frontmatter.Groups[1].Value, $"(?im)^\\s*{Regex.Escape(key)}\\s*:\\s*(.+?)\\s*$", RegexOptions.CultureInvariant);
            return value.Success ? value.Groups[1].Value.Trim().Trim('"', '\'') : null;
        }
    }

    public sealed record ReleaseManifestValidation(string Path, bool Valid, IReadOnlyList<string> Errors);

    public sealed record TicketReadinessResult(string Status, IReadOnlyList<string> Missing);

    public sealed record DeliveryRiskResult(string Level, IReadOnlyList<string> Reasons);

    public sealed record WorkloadForecast(
        string EstimatedChangedLines,
        string BudgetRisk,
        bool ChainedPrsRecommended,
        bool DecisionNeededBeforeApply,
        string DeliveryStrategy,
        bool RequiresResolutionBeforeApply);

    public sealed record AdversarialReviewTrigger(bool Required, string Mode, IReadOnlyList<string> Reasons);

    public sealed record InstalledSkillEntry(
        string Name,
        string Description,
        string Scope,
        string Path,
        long SizeBytes,
        DateTime LastWriteTimeUtc);

    public sealed record InstalledSkillIndex(int SchemaVersion, IReadOnlyList<InstalledSkillEntry> Skills);

    public sealed record SkillIndexFingerprint(string Path, long SizeBytes, DateTime LastWriteTimeUtc);

    public sealed record SkillIndexCache(int SchemaVersion, IReadOnlyList<SkillIndexFingerprint> Skills);

    public sealed record SkillIndexWriteResult(string IndexPath, string CachePath, int SkillCount, bool CacheHit);
}
