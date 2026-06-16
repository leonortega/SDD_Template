using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using SDDTemplate.Common.Observability;
using SDDTemplate.Site.Components;

namespace SDDTemplate.Site.Tests
{
    public sealed class HealthEndpointTests
    {
        [Fact]
        public async Task HealthEndpointReturnsOkStatus()
        {
            await using WebApplicationFactory<App> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync("/health");
            HealthResponse? health = await response.Content.ReadFromJsonAsync<HealthResponse>();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.NotNull(health);
            Assert.Equal("ok", health.Status);
            Assert.False(string.IsNullOrWhiteSpace(health.Environment));
            Assert.True(health.Timestamp <= DateTimeOffset.UtcNow);
        }

        [Fact]
        public async Task HealthEndpointDoesNotExposeSensitiveConfiguration()
        {
            await using WebApplicationFactory<App> factory = new();
            using HttpClient client = factory.CreateClient();

            string response = await client.GetStringAsync("/health");

            Assert.DoesNotContain("connection", response, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("secret", response, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("password", response, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("token", response, StringComparison.OrdinalIgnoreCase);
        }

        [Fact]
        public async Task HealthEndpointGeneratesCorrelationIdWhenMissing()
        {
            await using WebApplicationFactory<App> factory = new();
            using HttpClient client = factory.CreateClient();

            using HttpResponseMessage response = await client.GetAsync("/health");

            Assert.True(response.Headers.TryGetValues("X-Correlation-ID", out IEnumerable<string>? values));
            string? correlationId = values.SingleOrDefault();
            Assert.False(string.IsNullOrWhiteSpace(correlationId));
        }

        [Fact]
        public async Task HealthEndpointReusesIncomingCorrelationId()
        {
            await using WebApplicationFactory<App> factory = new();
            using HttpClient client = factory.CreateClient();
            const string correlationId = "test-correlation-id";

            using HttpRequestMessage request = new(HttpMethod.Get, "/health");
            _ = request.Headers.TryAddWithoutValidation("X-Correlation-ID", correlationId);

            using HttpResponseMessage response = await client.SendAsync(request);

            Assert.True(response.Headers.TryGetValues("X-Correlation-ID", out IEnumerable<string>? values));
            Assert.Equal(correlationId, values.Single());
        }

    }
}
