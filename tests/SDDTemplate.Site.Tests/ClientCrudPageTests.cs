using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;

namespace SDDTemplate.Site.Tests
{
    public sealed class ClientCrudPageTests
    {
        [Fact]
        public async Task ClientsPageRendersCrudShell()
        {
            await using WebApplicationFactory<Program> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync("/clients");
            string markup = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains("<h1>Clients</h1>", markup);
            Assert.Contains("id=\"client-form\"", markup);
            Assert.Contains("id=\"clients-list\"", markup);
            Assert.Contains("/api/clients", markup);
        }
    }
}
