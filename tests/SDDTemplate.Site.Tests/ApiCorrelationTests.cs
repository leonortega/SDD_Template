using System.Net;
using ApiProgram = SDDTemplate.Api.Program;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;

namespace SDDTemplate.Site.Tests
{
    public sealed class ApiCorrelationTests(WebApplicationFactory<ApiProgram> factory) : IClassFixture<WebApplicationFactory<ApiProgram>>
    {
        private readonly WebApplicationFactory<ApiProgram> _factory = factory;

        [Fact]
        public async Task ApiHealthGeneratesCorrelationIdWhenMissing()
        {
            using HttpClient client = _factory.CreateClient();

            using HttpResponseMessage response = await client.GetAsync("/health");

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.True(response.Headers.TryGetValues("X-Correlation-ID", out IEnumerable<string>? values));
            string? correlationId = values.SingleOrDefault();
            Assert.False(string.IsNullOrWhiteSpace(correlationId));
        }

        [Fact]
        public async Task ApiHealthReusesIncomingCorrelationId()
        {
            using HttpClient client = _factory.CreateClient();
            const string correlationId = "api-correlation-id";

            using HttpRequestMessage request = new(HttpMethod.Get, "/health");
            _ = request.Headers.TryAddWithoutValidation("X-Correlation-ID", correlationId);

            using HttpResponseMessage response = await client.SendAsync(request);

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.True(response.Headers.TryGetValues("X-Correlation-ID", out IEnumerable<string>? values));
            Assert.Equal(correlationId, values.Single());
        }

        [Fact]
        public async Task ApiExceptionPathReusesIncomingCorrelationId()
        {
            await using WebApplicationFactory<ApiProgram> factory = _factory.WithWebHostBuilder(builder =>
            {
                _ = builder.UseEnvironment("Testing");
            });
            using HttpClient client = factory.CreateClient();
            const string correlationId = "api-exception-correlation-id";

            using HttpRequestMessage request = new(HttpMethod.Get, "/__test/throw");
            _ = request.Headers.TryAddWithoutValidation("X-Correlation-ID", correlationId);

            using HttpResponseMessage response = await client.SendAsync(request);
            string responseBody = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.InternalServerError, response.StatusCode);
            Assert.True(response.Headers.TryGetValues("X-Correlation-ID", out IEnumerable<string>? values));
            Assert.Equal(correlationId, values.Single());
            Assert.DoesNotContain("Intentional test exception", responseBody, StringComparison.OrdinalIgnoreCase);
        }
    }
}
