using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;
using SDDTemplate.Site.Components;

namespace SDDTemplate.Site.Tests
{
    public sealed class ProductCrudPageTests
    {
        [Fact]
        public async Task ProductsPageRendersCrudShell()
        {
            await using WebApplicationFactory<App> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync("/products");
            string markup = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains("<h1>Products</h1>", markup);
            Assert.Contains("id=\"product-form\"", markup);
            Assert.Contains("id=\"products-list\"", markup);
            Assert.Contains("Save product", markup);
            Assert.Contains("SKU", markup);
            Assert.Contains("_framework/blazor.web.js", markup);
        }

        [Fact]
        public async Task MainNavigationLoadsProductsPageAsFullDocument()
        {
            await using WebApplicationFactory<App> factory = new();
            using HttpClient client = factory.CreateClient();

            HttpResponseMessage response = await client.GetAsync("/");
            string markup = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains("href=\"/products\"", markup);
            Assert.Contains("data-enhance-nav=\"false\"", markup, StringComparison.OrdinalIgnoreCase);
        }
    }
}
