namespace SDDTemplate.Common.Observability
{
    public sealed record HealthResponse(string Status, string Environment, DateTimeOffset Timestamp);
}
