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
            Console.WriteLine(JsonSerializer.Serialize(validation, new JsonSerializerOptions { WriteIndented = true }));
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

[ExcludeFromCodeCoverage]
internal partial class Program;
