using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;
using SDDTemplate.Site.Components;

namespace SDDTemplate.Site.Tests
{
    public sealed class LandingPageTests
    {
        [Fact]
        public async Task HomePageRendersLandingPageContent()
        {
            await using WebApplicationFactory<App> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync("/");
            string markup = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains("StockPilot", markup);
            Assert.Contains("Run stock, orders, and clients from one calm dashboard.", markup);
            Assert.Contains("Inventory dashboard showing stock levels and warehouse activity", markup);
            Assert.Contains("id=\"services\"", markup);
            Assert.Contains("id=\"benefits\"", markup);
            Assert.Contains("id=\"contact\"", markup);
            Assert.Contains("Plan a demo", markup);
        }

        [Fact]
        public async Task HomePageNavigationIncludesRoutesAndSections()
        {
            await using WebApplicationFactory<App> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync("/");
            string markup = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains("href=\"/\"", markup);
            Assert.Contains("href=\"/clients\"", markup);
            Assert.Contains("href=\"/products\"", markup);
            Assert.Contains("href=\"/#services\"", markup);
            Assert.Contains("href=\"/#benefits\"", markup);
            Assert.Contains("href=\"/#contact\"", markup);
            Assert.Contains("data-enhance-nav=\"false\"", markup, StringComparison.OrdinalIgnoreCase);
        }

        [Theory]
        [InlineData("/clients", "<h1>Clients</h1>")]
        [InlineData("/products", "<h1>Products</h1>")]
        public async Task ExistingApplicationRoutesRemainAccessible(string path, string expectedMarkup)
        {
            await using WebApplicationFactory<App> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync(path);
            string markup = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains(expectedMarkup, markup);
        }
    }
}
