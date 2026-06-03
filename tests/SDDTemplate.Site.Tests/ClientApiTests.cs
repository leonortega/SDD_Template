using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using SDDTemplate.Api;
using SDDTemplate.Api.Clients;

namespace SDDTemplate.Site.Tests
{
    public sealed class ClientApiTests
    {
        [Fact]
        public async Task ClientApiCreatesListsUpdatesAndDeletesClient()
        {
            await using WebApplicationFactory<ApiAssemblyMarker> factory = CreateFactory();
            using HttpClient httpClient = factory.CreateClient();
            ClientRequest createRequest = ValidRequest(name: "Ana", lastName: "Lopez");

            HttpResponseMessage createResponse = await httpClient.PostAsJsonAsync("/api/clients", createRequest);
            ClientResponse? created = await createResponse.Content.ReadFromJsonAsync<ClientResponse>();

            Assert.Equal(HttpStatusCode.Created, createResponse.StatusCode);
            Assert.NotNull(created);
            Assert.Equal("Ana", created.Name);

            ClientResponse[]? clients = await httpClient.GetFromJsonAsync<ClientResponse[]>("/api/clients");
            Assert.NotNull(clients);
            ClientResponse client = Assert.Single(clients);
            Assert.Equal(created.Id, client.Id);

            ClientRequest updateRequest = ValidRequest(name: "Ana Maria", lastName: "Lopez");
            HttpResponseMessage updateResponse = await httpClient.PutAsJsonAsync($"/api/clients/{created.Id}", updateRequest);
            ClientResponse? updated = await updateResponse.Content.ReadFromJsonAsync<ClientResponse>();

            Assert.Equal(HttpStatusCode.OK, updateResponse.StatusCode);
            Assert.NotNull(updated);
            Assert.Equal("Ana Maria", updated.Name);

            HttpResponseMessage deleteResponse = await httpClient.DeleteAsync($"/api/clients/{created.Id}");
            HttpResponseMessage readDeletedResponse = await httpClient.GetAsync($"/api/clients/{created.Id}");

            Assert.Equal(HttpStatusCode.NoContent, deleteResponse.StatusCode);
            Assert.Equal(HttpStatusCode.NotFound, readDeletedResponse.StatusCode);
        }

        [Fact]
        public async Task ClientApiRejectsMissingRequiredFields()
        {
            await using WebApplicationFactory<ApiAssemblyMarker> factory = CreateFactory();
            using HttpClient httpClient = factory.CreateClient();

            HttpResponseMessage response = await httpClient.PostAsJsonAsync("/api/clients", new ClientRequest(
                null,
                "Lopez",
                "123 Main St",
                new DateOnly(1990, 1, 1),
                "Cordoba",
                "Argentina",
                "5000"));
            string body = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
            Assert.Contains("Name", body);
            Assert.DoesNotContain("123 Main St", await httpClient.GetStringAsync("/api/clients"));
        }

        [Fact]
        public async Task ClientApiRejectsInvalidBornDateAndZipCode()
        {
            await using WebApplicationFactory<ApiAssemblyMarker> factory = CreateFactory();
            using HttpClient httpClient = factory.CreateClient();

            HttpResponseMessage response = await httpClient.PostAsJsonAsync("/api/clients", new ClientRequest(
                "Ana",
                "Lopez",
                "123 Main St",
                DateOnly.FromDateTime(DateTime.UtcNow.AddDays(1)),
                "Cordoba",
                "Argentina",
                "@@"));
            string body = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
            Assert.Contains("BornDate", body);
            Assert.Contains("ZipCode", body);
        }

        [Fact]
        public async Task ClientApiReturnsNotFoundForUnknownClient()
        {
            await using WebApplicationFactory<ApiAssemblyMarker> factory = CreateFactory();
            using HttpClient httpClient = factory.CreateClient();

            HttpResponseMessage getResponse = await httpClient.GetAsync("/api/clients/404");
            HttpResponseMessage putResponse = await httpClient.PutAsJsonAsync("/api/clients/404", ValidRequest());
            HttpResponseMessage deleteResponse = await httpClient.DeleteAsync("/api/clients/404");

            Assert.Equal(HttpStatusCode.NotFound, getResponse.StatusCode);
            Assert.Equal(HttpStatusCode.NotFound, putResponse.StatusCode);
            Assert.Equal(HttpStatusCode.NotFound, deleteResponse.StatusCode);
        }

        private static WebApplicationFactory<ApiAssemblyMarker> CreateFactory()
        {
            string databasePath = Path.Combine(Path.GetTempPath(), $"sddtemplate-clients-{Guid.NewGuid():N}.db");

            return new WebApplicationFactory<ApiAssemblyMarker>()
                .WithWebHostBuilder(builder =>
                {
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

        private static ClientRequest ValidRequest(string name = "Julia", string lastName = "Ramos")
        {
            return new ClientRequest(
                name,
                lastName,
                "123 Main St",
                new DateOnly(1990, 1, 1),
                "Cordoba",
                "Argentina",
                "5000");
        }
    }
}
