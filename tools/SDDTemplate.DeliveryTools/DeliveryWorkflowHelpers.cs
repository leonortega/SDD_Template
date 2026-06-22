using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace SDDTemplate.DeliveryTools
{
    public static partial class DeliveryWorkflowHelpers
    {
        private static readonly JsonSerializerOptions IndentedJson = new() { WriteIndented = true };

        public static string ReadDeliveryPolicyTicketKeyPattern(string path)
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            return TryReadTicketKeyPattern(document.RootElement, out string? profilePattern)
                ? profilePattern
                : document.RootElement.TryGetProperty("ticketKeyPattern", out JsonElement pattern)
                && !string.IsNullOrWhiteSpace(pattern.GetString())
                    ? pattern.GetString()!
                    : throw new InvalidOperationException("delivery-policy.json must define ticketKeyPattern.");
        }

        public static string ReadProjectProfileTicketKeyPattern(string path)
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            return TryReadTicketKeyPattern(document.RootElement, out string? pattern)
                ? pattern
                : throw new InvalidOperationException("project-profile.json must define workflow.ticketKeyPattern.");
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

            if (root.TryGetProperty("includedTickets", out JsonElement includedTickets))
            {
                if (includedTickets.ValueKind != JsonValueKind.Array)
                {
                    errors.Add("includedTickets must be an array when present.");
                }
                else
                {
                    if (includedTickets.GetArrayLength() == 0)
                    {
                        errors.Add("includedTickets must contain at least one ticket when present.");
                    }

                    int index = 0;
                    foreach (JsonElement includedTicket in includedTickets.EnumerateArray())
                    {
                        if (includedTicket.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(includedTicket.GetString()))
                        {
                            errors.Add($"includedTickets[{index}] must be a non-empty string.");
                        }

                        index++;
                    }
                }
            }

            if (root.TryGetProperty("containerImages", out JsonElement containerImages))
            {
                ValidateContainerImages(containerImages, errors);
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

            File.WriteAllText(outputPath, JsonSerializer.Serialize(manifest, IndentedJson));
        }

        public static void CreateArtifactPointer(
            string outputPath,
            string version,
            string artifactCommitSha,
            string planeTicketKey,
            IEnumerable<string> includedTickets,
            DateTimeOffset? createdAtUtc = null)
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(version);
            ArgumentException.ThrowIfNullOrWhiteSpace(artifactCommitSha);
            ArgumentException.ThrowIfNullOrWhiteSpace(planeTicketKey);

            string[] normalizedTickets = [.. includedTickets
                .Where(ticket => !string.IsNullOrWhiteSpace(ticket))
                .Select(ticket => ticket.Trim())
                .Distinct(StringComparer.Ordinal)
                .Order(StringComparer.Ordinal)];

            if (normalizedTickets.Length == 0)
            {
                normalizedTickets = [planeTicketKey];
            }

            SortedDictionary<string, object?> pointer = new()
            {
                ["schemaVersion"] = 1,
                ["version"] = version,
                ["artifactCommitSha"] = artifactCommitSha,
                ["canonicalPath"] = $"app/{artifactCommitSha}/",
                ["releaseManifestPath"] = $"app/{artifactCommitSha}/release.json",
                ["planeTicketKey"] = planeTicketKey,
                ["includedTickets"] = normalizedTickets,
                ["createdAtUtc"] = (createdAtUtc ?? DateTimeOffset.UtcNow).ToString("O", CultureInfo.InvariantCulture),
            };

            string? parent = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrWhiteSpace(parent))
            {
                _ = Directory.CreateDirectory(parent);
            }

            File.WriteAllText(outputPath, JsonSerializer.Serialize(pointer, IndentedJson));
        }

        public static DeploymentConfigBuildResult BuildDeploymentConfig(string root, string topologyPath, string mappingPath, string outputPath)
        {
            JsonArray apps = ReadRequiredArray(topologyPath, "apps");
            JsonArray mappings = ReadRequiredArray(mappingPath, "settings");
            Dictionary<string, JsonObject> mappingsByKey = [];
            HashSet<string> ignoredPrefixes = ReadStringArray(mappingPath, "ignoredPrefixes");
            List<string> errors = [];
            JsonArray outputApps = [];

            foreach (JsonNode? mappingNode in mappings)
            {
                JsonObject mapping = mappingNode?.AsObject() ?? throw new InvalidOperationException("configuration.json settings entries must be objects.");
                string appId = RequiredString(mapping, "appId");
                string name = RequiredString(mapping, "name");
                mappingsByKey[$"{appId}:{name}"] = mapping;
            }

            foreach (JsonNode? appNode in apps)
            {
                JsonObject app = appNode?.AsObject() ?? throw new InvalidOperationException("apps.json app entries must be objects.");
                string appId = RequiredString(app, "appId");
                string role = RequiredString(app, "role");
                string projectPath = RequiredString(app, "projectPath");
                string projectDirectory = Path.GetDirectoryName(Path.Combine(root, projectPath))
                    ?? throw new InvalidOperationException($"Could not resolve project directory for {projectPath}.");

                SortedSet<string> discoveredSettings = DiscoverAppSettings(projectDirectory);
                JsonArray appSettings = [];

                foreach (string discovered in discoveredSettings)
                {
                    if (ignoredPrefixes.Any(prefix => discovered.StartsWith(prefix, StringComparison.Ordinal)))
                    {
                        continue;
                    }

                    if (!mappingsByKey.TryGetValue($"{appId}:{discovered}", out JsonObject? mapping))
                    {
                        errors.Add($"Missing deployment configuration mapping for {appId}:{discovered}.");
                        continue;
                    }

                    appSettings.Add(CloneObject(mapping));
                }

                foreach (JsonObject mapping in mappingsByKey.Values
                    .Where(mapping => RequiredString(mapping, "appId").Equals(appId, StringComparison.Ordinal)
                        && ReadBool(mapping, "additionalSetting")))
                {
                    if (!appSettings.OfType<JsonObject>().Any(setting => RequiredString(setting, "name").Equals(RequiredString(mapping, "name"), StringComparison.Ordinal)))
                    {
                        appSettings.Add(CloneObject(mapping));
                    }
                }

                foreach (JsonObject setting in appSettings.OfType<JsonObject>())
                {
                    string source = RequiredString(setting, "source");
                    bool required = ReadBool(setting, "required", fallback: true);
                    if (required && source.Equals("manualRequired", StringComparison.Ordinal))
                    {
                        errors.Add($"Required deployment configuration {appId}:{RequiredString(setting, "name")} is manualRequired. Run configure-cloud-environments and map this value before deploying.");
                    }
                }

                outputApps.Add(new JsonObject
                {
                    ["appId"] = appId,
                    ["role"] = role,
                    ["settings"] = appSettings,
                });
            }

            if (errors.Count > 0)
            {
                return new DeploymentConfigBuildResult(outputPath, false, errors);
            }

            JsonObject artifact = new()
            {
                ["schemaVersion"] = 1,
                ["generatedAtUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                ["apps"] = outputApps,
            };

            string? parent = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrWhiteSpace(parent))
            {
                _ = Directory.CreateDirectory(parent);
            }

            File.WriteAllText(outputPath, artifact.ToJsonString(IndentedJson));
            return new DeploymentConfigBuildResult(outputPath, true, []);
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
                    : new TicketReadinessResult("refinable", missing);
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
                || strategy.Equals("exception-ok", StringComparison.OrdinalIgnoreCase);

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
            string cacheJson = JsonSerializer.Serialize(cache, IndentedJson);
            bool cacheHit = File.Exists(indexPath)
                && File.Exists(cachePath)
                && string.Equals(File.ReadAllText(cachePath), cacheJson, StringComparison.Ordinal);

            if (!cacheHit)
            {
                _ = Directory.CreateDirectory(Path.GetDirectoryName(indexPath) ?? root);
                _ = Directory.CreateDirectory(Path.GetDirectoryName(cachePath) ?? root);
                File.WriteAllText(indexPath, JsonSerializer.Serialize(index, IndentedJson));
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

        private static bool TryReadTicketKeyPattern(JsonElement root, out string pattern)
        {
            pattern = string.Empty;
            if (root.TryGetProperty("workflow", out JsonElement workflow)
                && workflow.TryGetProperty("ticketKeyPattern", out JsonElement workflowPattern)
                && !string.IsNullOrWhiteSpace(workflowPattern.GetString()))
            {
                pattern = workflowPattern.GetString()!;
                return true;
            }

            return false;
        }

        private static void ValidateContainerImages(JsonElement containerImages, ICollection<string> errors)
        {
            if (containerImages.ValueKind != JsonValueKind.Array)
            {
                errors.Add("containerImages must be an array when present.");
                return;
            }

            int index = 0;
            foreach (JsonElement image in containerImages.EnumerateArray())
            {
                if (image.ValueKind != JsonValueKind.Object)
                {
                    errors.Add($"containerImages[{index}] must be an object.");
                    index++;
                    continue;
                }

                foreach (string field in new[] { "appId", "image", "tag", "digest", "reference" })
                {
                    if (!image.TryGetProperty(field, out JsonElement value) || IsMissing(value))
                    {
                        errors.Add($"containerImages[{index}] is missing required field: {field}");
                    }
                }

                if (image.TryGetProperty("digest", out JsonElement digest)
                    && !IsMissing(digest)
                    && !Regex.IsMatch(digest.GetString() ?? string.Empty, "^sha256:[0-9a-fA-F]{64}$", RegexOptions.CultureInvariant))
                {
                    errors.Add($"containerImages[{index}].digest must be a sha256 digest.");
                }

                if (image.TryGetProperty("reference", out JsonElement reference)
                    && !IsMissing(reference)
                    && !Regex.IsMatch(reference.GetString() ?? string.Empty, "@sha256:[0-9a-fA-F]{64}$", RegexOptions.CultureInvariant))
                {
                    errors.Add($"containerImages[{index}].reference must be pinned by sha256 digest.");
                }

                index++;
            }
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

        private static SortedSet<string> DiscoverAppSettings(string projectDirectory)
        {
            SortedSet<string> settings = new(StringComparer.Ordinal);
            if (!Directory.Exists(projectDirectory))
            {
                return settings;
            }

            foreach (string path in Directory.EnumerateFiles(projectDirectory, "appsettings*.json", SearchOption.TopDirectoryOnly).Order(StringComparer.Ordinal))
            {
                using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
                FlattenSettings(document.RootElement, string.Empty, settings);
            }

            return settings;
        }

        private static void FlattenSettings(JsonElement element, string prefix, ISet<string> settings)
        {
            if (element.ValueKind == JsonValueKind.Object)
            {
                foreach (JsonProperty property in element.EnumerateObject())
                {
                    string key = string.IsNullOrWhiteSpace(prefix) ? property.Name : $"{prefix}__{property.Name}";
                    FlattenSettings(property.Value, key, settings);
                }
            }
            else if (element.ValueKind == JsonValueKind.Array)
            {
                int index = 0;
                foreach (JsonElement item in element.EnumerateArray())
                {
                    FlattenSettings(item, $"{prefix}__{index}", settings);
                    index++;
                }
            }
            else if (!string.IsNullOrWhiteSpace(prefix))
            {
                _ = settings.Add(prefix);
            }
        }

        private static JsonArray ReadRequiredArray(string path, string propertyName)
        {
            JsonObject root = JsonNode.Parse(File.ReadAllText(path))?.AsObject()
                ?? throw new InvalidOperationException($"{path} must contain a JSON object.");
            return root[propertyName]?.AsArray()
                ?? throw new InvalidOperationException($"{path} must define {propertyName}.");
        }

        private static HashSet<string> ReadStringArray(string path, string propertyName)
        {
            JsonObject root = JsonNode.Parse(File.ReadAllText(path))?.AsObject()
                ?? throw new InvalidOperationException($"{path} must contain a JSON object.");
            JsonArray? array = root[propertyName]?.AsArray();
            return array is null
                ? []
                : [.. array.Select(item => item?.GetValue<string>() ?? string.Empty).Where(item => !string.IsNullOrWhiteSpace(item))];
        }

        private static JsonObject CloneObject(JsonObject source)
        {
            return JsonNode.Parse(source.ToJsonString())?.AsObject()
                ?? throw new InvalidOperationException("Could not clone JSON object.");
        }

        private static string RequiredString(JsonObject source, string propertyName)
        {
            return source[propertyName]?.GetValue<string>() is { Length: > 0 } value
                ? value
                : throw new InvalidOperationException($"Configuration mapping must define {propertyName}.");
        }

        private static bool ReadBool(JsonObject source, string propertyName, bool fallback = false)
        {
            return source[propertyName]?.GetValue<bool>() ?? fallback;
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

    public sealed record DeploymentConfigBuildResult(string OutputPath, bool Valid, IReadOnlyList<string> Errors);

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
