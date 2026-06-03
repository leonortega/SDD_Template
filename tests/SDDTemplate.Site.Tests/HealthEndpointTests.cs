using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;

namespace SDDTemplate.Site.Tests
{
    public sealed class HealthEndpointTests
    {
        [Fact]
        public async Task HealthEndpointReturnsOkStatus()
        {
            await using WebApplicationFactory<SiteAssemblyMarker> factory = new();
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
            await using WebApplicationFactory<SiteAssemblyMarker> factory = new();
            using HttpClient client = factory.CreateClient();

            string response = await client.GetStringAsync("/health");

            Assert.DoesNotContain("connection", response, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("secret", response, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("password", response, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("token", response, StringComparison.OrdinalIgnoreCase);
        }

        [Fact]
        public async Task MetricsEndpointReturnsPrometheusGauge()
        {
            await using WebApplicationFactory<SiteAssemblyMarker> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync("/metrics");
            string metrics = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.StartsWith("text/plain", response.Content.Headers.ContentType?.MediaType);
            Assert.Contains("# TYPE sddtemplate_health gauge", metrics);
            Assert.Contains("sddtemplate_health 1", metrics);
        }
    }
}
