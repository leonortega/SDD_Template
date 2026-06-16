using System.Diagnostics.CodeAnalysis;
using System.Globalization;
using System.Text.Json;
using SDDTemplate.DeliveryTools;

try
{
    Run(args);
}
catch (Exception ex)
{
    Console.Error.WriteLine(ex.Message);
    Environment.ExitCode = 1;
}

static void Run(string[] args)
{
    if (args.Length == 0)
    {
        throw new ArgumentException("Mode is required.");
    }

    string mode = args[0];
    Dictionary<string, string> options = ParseOptions(args[1..]);

    switch (mode)
    {
        case "ReadDeliveryPolicy":
            Console.WriteLine(DeliveryWorkflowHelpers.ReadDeliveryPolicyTicketKeyPattern(Required(options, "path")));
            break;
        case "ExtractTicketKey":
            Console.WriteLine(DeliveryWorkflowHelpers.ExtractTicketKey(
                Required(options, "message"),
                Required(options, "pattern"),
                options.GetValueOrDefault("fallback", string.Empty)));
            break;
        case "ReadCoverageThreshold":
            Console.WriteLine(DeliveryWorkflowHelpers.ReadCoverageThreshold(
                Required(options, "path"),
                int.Parse(options.GetValueOrDefault("fallback", "80"), CultureInfo.InvariantCulture)));
            break;
        case "ReadCoberturaLineRate":
            Console.WriteLine(DeliveryWorkflowHelpers.ReadCoberturaCoveragePercent(Required(options, "path")).ToString("0.00", CultureInfo.InvariantCulture));
            break;
        case "ValidateReleaseManifest":
            ReleaseManifestValidation validation = DeliveryWorkflowHelpers.ValidateReleaseManifest(Required(options, "path"));
            Console.WriteLine(JsonSerializer.Serialize(validation, IndentedJson));
            if (!validation.Valid)
            {
                Environment.ExitCode = 1;
            }
            break;
        case "CreateReleaseManifest":
            DeliveryWorkflowHelpers.CreateReleaseManifest(
                Required(options, "output"),
                Required(options, "commit-sha"),
                Required(options, "checksum"),
                Required(options, "artifact-url"),
                Required(options, "plane-ticket-key"),
                options.GetValueOrDefault("version-status", "unversioned"));
            break;
        case "CreateArtifactPointer":
            DeliveryWorkflowHelpers.CreateArtifactPointer(
                Required(options, "output"),
                Required(options, "version"),
                Required(options, "artifact-commit-sha"),
                Required(options, "plane-ticket-key"),
                SplitList(options.GetValueOrDefault("included-tickets", string.Empty)));
            break;
        case "BuildDeploymentConfig":
            DeploymentConfigBuildResult configResult = DeliveryWorkflowHelpers.BuildDeploymentConfig(
                Required(options, "root"),
                Required(options, "topology"),
                Required(options, "mapping"),
                Required(options, "output"));
            Console.WriteLine(JsonSerializer.Serialize(configResult, IndentedJson));
            if (!configResult.Valid)
            {
                Environment.ExitCode = 1;
            }

            break;
        case "ClassifyTicketReadiness":
            Console.WriteLine(JsonSerializer.Serialize(
                DeliveryWorkflowHelpers.ClassifyTicketReadiness(
                    options.GetValueOrDefault("title", string.Empty),
                    options.GetValueOrDefault("description", string.Empty)),
                IndentedJson));
            break;
        case "ClassifyDeliveryRisk":
            Console.WriteLine(JsonSerializer.Serialize(
                DeliveryWorkflowHelpers.ClassifyDeliveryRisk(
                    SplitList(options.GetValueOrDefault("paths", string.Empty)),
                    options.GetValueOrDefault("context", string.Empty),
                    int.Parse(options.GetValueOrDefault("changed-lines", "0"), CultureInfo.InvariantCulture)),
                IndentedJson));
            break;
        case "ParseWorkloadForecast":
            Console.WriteLine(JsonSerializer.Serialize(
                DeliveryWorkflowHelpers.ParseWorkloadForecast(Required(options, "markdown")),
                IndentedJson));
            break;
        case "DetectAdversarialReviewTrigger":
            Console.WriteLine(JsonSerializer.Serialize(
                DeliveryWorkflowHelpers.DetectAdversarialReviewTrigger(
                    SplitList(options.GetValueOrDefault("paths", string.Empty)),
                    options.GetValueOrDefault("context", string.Empty),
                    int.Parse(options.GetValueOrDefault("changed-lines", "0"), CultureInfo.InvariantCulture),
                    bool.Parse(options.GetValueOrDefault("explicit-request", "false"))),
                IndentedJson));
            break;
        case "WriteInstalledSkillIndex":
            string root = Required(options, "root");
            Console.WriteLine(JsonSerializer.Serialize(
                DeliveryWorkflowHelpers.WriteInstalledSkillIndex(
                    root,
                    options.GetValueOrDefault("index-path", Path.Combine(root, ".codex", "installed-skill-index.local.json")),
                    options.GetValueOrDefault("cache-path", Path.Combine(root, ".codex", "installed-skill-index.cache.local.json"))),
                IndentedJson));
            break;
        default:
            throw new ArgumentException($"Unsupported mode: {mode}");
    }
}

static Dictionary<string, string> ParseOptions(string[] args)
{
    Dictionary<string, string> options = new(StringComparer.OrdinalIgnoreCase);
    for (int i = 0; i < args.Length; i++)
    {
        string key = args[i];
        if (!key.StartsWith("--", StringComparison.Ordinal))
        {
            throw new ArgumentException($"Expected option name, got '{key}'.");
        }

        if (i + 1 >= args.Length)
        {
            throw new ArgumentException($"Missing value for {key}.");
        }

        options[key[2..]] = args[++i];
    }

    return options;
}

static string Required(Dictionary<string, string> options, string key)
{
    return options.TryGetValue(key, out string? value) && !string.IsNullOrWhiteSpace(value)
        ? value
        : throw new ArgumentException($"--{key} is required.");
}

static string[] SplitList(string value)
{
    return [.. value.Split([',', ';', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)];
}

[ExcludeFromCodeCoverage]
internal partial class Program
{
    private static readonly JsonSerializerOptions IndentedJson = new() { WriteIndented = true };
}
