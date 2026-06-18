using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;
using Serilog;
using SDDTemplate.Data;
using SDDTemplate.Data.Products;

namespace SDDTemplate.Api.Products
{
    public static class ProductEndpoints
    {
        public static RouteGroupBuilder MapProductEndpoints(this IEndpointRouteBuilder routes)
        {
            Log.Information("Mapping API product endpoints");
            RouteGroupBuilder group = routes.MapGroup("/api/products").WithTags("Products");

            _ = group.MapGet("/", async (ApplicationDbContext db, CancellationToken cancellationToken) =>
                await db.Products
                    .AsNoTracking()
                    .OrderBy(product => product.Name)
                    .ThenBy(product => product.Sku)
                    .Select(product => product.ToResponse())
                    .ToListAsync(cancellationToken));

            _ = group.MapGet("/{id}", async Task<Results<Ok<ProductResponse>, NotFound>> (
                int id,
                ApplicationDbContext db,
                CancellationToken cancellationToken) =>
            {
                Product? product = await db.Products.AsNoTracking().SingleOrDefaultAsync(item => item.Id == id, cancellationToken);

                return product is null ? TypedResults.NotFound() : TypedResults.Ok(product.ToResponse());
            });

            _ = group.MapPost("/", async Task<Results<Created<ProductResponse>, ValidationProblem>> (
                ProductRequest request,
                ApplicationDbContext db,
                CancellationToken cancellationToken) =>
            {
                Dictionary<string, string[]> errors = request.Validate();
                if (errors.Count == 0 && await SkuExists(db, request.NormalizedSku(), null, cancellationToken))
                {
                    errors[nameof(ProductRequest.Sku)] = ["SKU must be unique."];
                }

                if (errors.Count > 0)
                {
                    Log.Debug("Product create validation failed with {ErrorCount} fields", errors.Count);
                    return TypedResults.ValidationProblem(errors);
                }

                Product product = request.ToProduct(DateTimeOffset.UtcNow);
                _ = db.Products.Add(product);
                _ = await db.SaveChangesAsync(cancellationToken);

                Log.Information("Product created with id {ProductId}", product.Id);

                return TypedResults.Created($"/api/products/{product.Id}", product.ToResponse());
            }).DisableAntiforgery();

            _ = group.MapMethods("/{id}", [HttpMethods.Put], async Task<Results<Ok<ProductResponse>, NotFound, ValidationProblem>> (
                int id,
                ProductRequest request,
                ApplicationDbContext db,
                CancellationToken cancellationToken) =>
            {
                Dictionary<string, string[]> errors = request.Validate();
                if (errors.Count > 0)
                {
                    Log.Debug("Product update validation failed for id {ProductId} with {ErrorCount} fields", id, errors.Count);
                    return TypedResults.ValidationProblem(errors);
                }

                Product? product = await db.Products.SingleOrDefaultAsync(item => item.Id == id, cancellationToken);
                if (product is null)
                {
                    Log.Debug("Product update requested for missing id {ProductId}", id);
                    return TypedResults.NotFound();
                }

                if (await SkuExists(db, request.NormalizedSku(), id, cancellationToken))
                {
                    Log.Debug("Product update duplicate SKU rejected for id {ProductId}", id);
                    return TypedResults.ValidationProblem(new Dictionary<string, string[]>
                    {
                        [nameof(ProductRequest.Sku)] = ["SKU must be unique."],
                    });
                }

                request.ApplyTo(product, DateTimeOffset.UtcNow);
                _ = await db.SaveChangesAsync(cancellationToken);

                Log.Information("Product updated with id {ProductId}", id);

                return TypedResults.Ok(product.ToResponse());
            }).DisableAntiforgery();

            _ = group.MapDelete("/{id}", async Task<Results<NoContent, NotFound>> (
                int id,
                ApplicationDbContext db,
                CancellationToken cancellationToken) =>
            {
                Product? product = await db.Products.SingleOrDefaultAsync(item => item.Id == id, cancellationToken);
                if (product is null)
                {
                    Log.Debug("Product delete requested for missing id {ProductId}", id);
                    return TypedResults.NotFound();
                }

                _ = db.Products.Remove(product);
                _ = await db.SaveChangesAsync(cancellationToken);

                Log.Information("Product deleted with id {ProductId}", id);

                return TypedResults.NoContent();
            }).DisableAntiforgery();

            return group;
        }

        private static Task<bool> SkuExists(ApplicationDbContext db, string sku, int? exceptId, CancellationToken cancellationToken)
        {
            return db.Products.AnyAsync(product => product.Sku == sku && product.Id != exceptId, cancellationToken);
        }
    }
}
