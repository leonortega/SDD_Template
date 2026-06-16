using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using SDDTemplate.Api.Products;

namespace SDDTemplate.Site.Tests
{
    public sealed class ProductApiTests
    {
        [Fact]
        public async Task ProductApiCreatesListsUpdatesAndDeletesProduct()
        {
            await using WebApplicationFactory<ProductRequest> factory = CreateFactory();
            using HttpClient httpClient = factory.CreateClient();
            ProductRequest createRequest = ValidRequest(name: "Desk", sku: "desk-001");

            HttpResponseMessage createResponse = await httpClient.PostAsJsonAsync("/api/products", createRequest);
            ProductResponse? created = await createResponse.Content.ReadFromJsonAsync<ProductResponse>();

            Assert.Equal(HttpStatusCode.Created, createResponse.StatusCode);
            Assert.NotNull(created);
            Assert.Equal("Desk", created.Name);
            Assert.Equal("DESK-001", created.Sku);
            Assert.True(created.LastUpdated <= DateTimeOffset.UtcNow);

            ProductResponse[]? products = await httpClient.GetFromJsonAsync<ProductResponse[]>("/api/products");
            Assert.NotNull(products);
            ProductResponse product = Assert.Single(products);
            Assert.Equal(created.Id, product.Id);

            ProductRequest updateRequest = ValidRequest(name: "Standing Desk", sku: "desk-001", price: 399.99m);
            HttpResponseMessage updateResponse = await httpClient.PutAsJsonAsync($"/api/products/{created.Id}", updateRequest);
            ProductResponse? updated = await updateResponse.Content.ReadFromJsonAsync<ProductResponse>();

            Assert.Equal(HttpStatusCode.OK, updateResponse.StatusCode);
            Assert.NotNull(updated);
            Assert.Equal("Standing Desk", updated.Name);
            Assert.Equal(399.99m, updated.Price);
            Assert.True(updated.LastUpdated >= created.LastUpdated);

            HttpResponseMessage deleteResponse = await httpClient.DeleteAsync($"/api/products/{created.Id}");
            HttpResponseMessage readDeletedResponse = await httpClient.GetAsync($"/api/products/{created.Id}");

            Assert.Equal(HttpStatusCode.NoContent, deleteResponse.StatusCode);
            Assert.Equal(HttpStatusCode.NotFound, readDeletedResponse.StatusCode);
        }

        [Fact]
        public async Task ProductApiRejectsMissingRequiredFields()
        {
            await using WebApplicationFactory<ProductRequest> factory = CreateFactory();
            using HttpClient httpClient = factory.CreateClient();

            HttpResponseMessage response = await httpClient.PostAsJsonAsync("/api/products", new ProductRequest(
                null,
                "SKU-001",
                "Active",
                10,
                "Office"));
            string body = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
            Assert.Contains("Name", body);
            Assert.Equal("[]", await httpClient.GetStringAsync("/api/products"));
        }

        [Fact]
        public async Task ProductApiRejectsInvalidValuesAndDuplicateSku()
        {
            await using WebApplicationFactory<ProductRequest> factory = CreateFactory();
            using HttpClient httpClient = factory.CreateClient();

            HttpResponseMessage invalidResponse = await httpClient.PostAsJsonAsync("/api/products", new ProductRequest(
                "Desk",
                "@@",
                "Pending",
                -1,
                "Office"));
            string invalidBody = await invalidResponse.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.BadRequest, invalidResponse.StatusCode);
            Assert.Contains("Sku", invalidBody);
            Assert.Contains("Status", invalidBody);
            Assert.Contains("Price", invalidBody);

            HttpResponseMessage createdResponse = await httpClient.PostAsJsonAsync("/api/products", ValidRequest(name: "Desk", sku: "desk-001"));
            ProductResponse? created = await createdResponse.Content.ReadFromJsonAsync<ProductResponse>();
            Assert.Equal(HttpStatusCode.Created, createdResponse.StatusCode);
            Assert.NotNull(created);

            HttpResponseMessage duplicateResponse = await httpClient.PostAsJsonAsync("/api/products", ValidRequest(name: "Desk 2", sku: "DESK-001"));
            string duplicateBody = await duplicateResponse.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.BadRequest, duplicateResponse.StatusCode);
            Assert.Contains("SKU must be unique.", duplicateBody);

            HttpResponseMessage otherResponse = await httpClient.PostAsJsonAsync("/api/products", ValidRequest(name: "Lamp", sku: "lamp-001"));
            ProductResponse? other = await otherResponse.Content.ReadFromJsonAsync<ProductResponse>();
            Assert.Equal(HttpStatusCode.Created, otherResponse.StatusCode);
            Assert.NotNull(other);

            HttpResponseMessage duplicateUpdateResponse = await httpClient.PutAsJsonAsync($"/api/products/{other.Id}", ValidRequest(name: "Lamp", sku: "desk-001"));
            string duplicateUpdateBody = await duplicateUpdateResponse.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.BadRequest, duplicateUpdateResponse.StatusCode);
            Assert.Contains("SKU must be unique.", duplicateUpdateBody);
        }

        [Fact]
        public async Task ProductApiReturnsNotFoundForUnknownProduct()
        {
            await using WebApplicationFactory<ProductRequest> factory = CreateFactory();
            using HttpClient httpClient = factory.CreateClient();

            HttpResponseMessage getResponse = await httpClient.GetAsync("/api/products/404");
            HttpResponseMessage putResponse = await httpClient.PutAsJsonAsync("/api/products/404", ValidRequest());
            HttpResponseMessage deleteResponse = await httpClient.DeleteAsync("/api/products/404");

            Assert.Equal(HttpStatusCode.NotFound, getResponse.StatusCode);
            Assert.Equal(HttpStatusCode.NotFound, putResponse.StatusCode);
            Assert.Equal(HttpStatusCode.NotFound, deleteResponse.StatusCode);
        }

        private static WebApplicationFactory<ProductRequest> CreateFactory()
        {
            string databasePath = Path.Combine(Path.GetTempPath(), $"sddtemplate-products-{Guid.NewGuid():N}.db");

            return new WebApplicationFactory<ProductRequest>()
                .WithWebHostBuilder(builder =>
                {
                    _ = builder.UseSetting("ConnectionStrings:ClientsDb", $"Data Source={databasePath}");
                    _ = builder.ConfigureAppConfiguration((context, config) =>
                    {
                        _ = context;
                        Dictionary<string, string?> values = new()
                        {
                            ["ConnectionStrings:ClientsDb"] = $"Data Source={databasePath}",
                        };

                        _ = config.AddInMemoryCollection(values);
                    });
                });
        }

        private static ProductRequest ValidRequest(
            string name = "Desk",
            string sku = "DESK-001",
            decimal price = 199.99m)
        {
            return new ProductRequest(name, sku, "Active", price, "Office");
        }
    }
}
