using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;
using SDDTemplate.Site.Data;

namespace SDDTemplate.Site.Clients
{
    public static class ClientEndpoints
    {
        public static RouteGroupBuilder MapClientEndpoints(this IEndpointRouteBuilder routes)
        {
            RouteGroupBuilder group = routes.MapGroup("/api/clients").WithTags("Clients");

            _ = group.MapGet("/", async (ApplicationDbContext db, CancellationToken cancellationToken) =>
                await db.Clients
                    .AsNoTracking()
                    .OrderBy(client => client.LastName)
                    .ThenBy(client => client.Name)
                    .Select(client => client.ToResponse())
                    .ToListAsync(cancellationToken));

            _ = group.MapGet("/{id}", async Task<Results<Ok<ClientResponse>, NotFound>> (
                int id,
                ApplicationDbContext db,
                CancellationToken cancellationToken) =>
            {
                Client? client = await db.Clients.AsNoTracking().SingleOrDefaultAsync(item => item.Id == id, cancellationToken);

                return client is null ? TypedResults.NotFound() : TypedResults.Ok(client.ToResponse());
            });

            _ = group.MapPost("/", async Task<Results<Created<ClientResponse>, ValidationProblem>> (
                ClientRequest request,
                ApplicationDbContext db,
                CancellationToken cancellationToken) =>
            {
                Dictionary<string, string[]> errors = request.Validate();
                if (errors.Count > 0)
                {
                    return TypedResults.ValidationProblem(errors);
                }

                Client client = request.ToClient();
                _ = db.Clients.Add(client);
                _ = await db.SaveChangesAsync(cancellationToken);

                return TypedResults.Created($"/api/clients/{client.Id}", client.ToResponse());
            }).DisableAntiforgery();

            _ = group.MapMethods("/{id}", [HttpMethods.Put], async Task<Results<Ok<ClientResponse>, NotFound, ValidationProblem>> (
                int id,
                ClientRequest request,
                ApplicationDbContext db,
                CancellationToken cancellationToken) =>
            {
                Dictionary<string, string[]> errors = request.Validate();
                if (errors.Count > 0)
                {
                    return TypedResults.ValidationProblem(errors);
                }

                Client? client = await db.Clients.SingleOrDefaultAsync(item => item.Id == id, cancellationToken);
                if (client is null)
                {
                    return TypedResults.NotFound();
                }

                request.ApplyTo(client);
                _ = await db.SaveChangesAsync(cancellationToken);

                return TypedResults.Ok(client.ToResponse());
            }).DisableAntiforgery();

            _ = group.MapDelete("/{id}", async Task<Results<NoContent, NotFound>> (
                int id,
                ApplicationDbContext db,
                CancellationToken cancellationToken) =>
            {
                Client? client = await db.Clients.SingleOrDefaultAsync(item => item.Id == id, cancellationToken);
                if (client is null)
                {
                    return TypedResults.NotFound();
                }

                _ = db.Clients.Remove(client);
                _ = await db.SaveChangesAsync(cancellationToken);

                return TypedResults.NoContent();
            }).DisableAntiforgery();

            return group;
        }
    }
}
