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
    }

    public sealed record ReleaseManifestValidation(string Path, bool Valid, IReadOnlyList<string> Errors);
}
