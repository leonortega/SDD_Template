namespace SDDTemplate.Site
{
    public sealed record HealthResponse(string Status, string Environment, DateTimeOffset Timestamp);
}
