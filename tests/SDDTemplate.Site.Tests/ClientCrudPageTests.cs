using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;

namespace SDDTemplate.Site.Tests
{
    public sealed class ClientCrudPageTests
    {
        [Fact]
        public async Task ClientsPageRendersCrudShell()
        {
            await using WebApplicationFactory<SiteAssemblyMarker> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync("/clients");
            string markup = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains("<h1>Clients</h1>", markup);
            Assert.Contains("id=\"client-form\"", markup);
            Assert.Contains("onsubmit=\"return false\"", markup);
            Assert.Contains("id=\"clients-list\"", markup);
            Assert.Contains("/api/clients", markup);
            Assert.Contains("fields.id.value.trim()", markup);
            Assert.Contains("method: id ? \"PUT\" : \"POST\"", markup);
            Assert.Contains("const apiBaseUrl", markup);
        }

        [Fact]
        public async Task MainNavigationLoadsClientsPageAsFullDocument()
        {
            await using WebApplicationFactory<SiteAssemblyMarker> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync("/");
            string markup = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains("href=\"/clients\"", markup);
            Assert.Contains("data-enhance-nav=\"false\"", markup, StringComparison.OrdinalIgnoreCase);
        }
    }
}
