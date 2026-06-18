using System.Text.RegularExpressions;
using SDDTemplate.Data.Products;

namespace SDDTemplate.Api.Products
{
    public sealed record ProductResponse(
        int Id,
        string Name,
        string Sku,
        string Status,
        decimal Price,
        string Category,
        DateTimeOffset LastUpdated);

    public sealed record ProductRequest(
        string? Name,
        string? Sku,
        string? Status,
        decimal? Price,
        string? Category)
    {
        private static readonly Regex SkuPattern = new("^[A-Za-z0-9][A-Za-z0-9._-]{2,39}$", RegexOptions.Compiled);
        private static readonly HashSet<string> ValidStatuses = new(StringComparer.OrdinalIgnoreCase)
        {
            "Active",
            "Inactive",
            "Archived",
        };

        public Dictionary<string, string[]> Validate()
        {
            Dictionary<string, string[]> errors = [];

            RequireText(errors, nameof(Name), Name, 100);
            RequireText(errors, nameof(Sku), Sku, 40);
            RequireText(errors, nameof(Status), Status, 40);
            RequireText(errors, nameof(Category), Category, 100);

            if (Price is null)
            {
                errors[nameof(Price)] = ["Price is required."];
            }
            else if (Price < 0)
            {
                errors[nameof(Price)] = ["Price cannot be negative."];
            }

            if (!string.IsNullOrWhiteSpace(Sku) && !SkuPattern.IsMatch(Sku.Trim()))
            {
                errors[nameof(Sku)] = ["SKU must be 3 to 40 letters, digits, dots, underscores, or hyphens."];
            }

            if (!string.IsNullOrWhiteSpace(Status) && !ValidStatuses.Contains(Status.Trim()))
            {
                errors[nameof(Status)] = ["Status must be Active, Inactive, or Archived."];
            }

            return errors;
        }

        public Product ToProduct(DateTimeOffset lastUpdated)
        {
            return new Product
            {
                Name = Name!.Trim(),
                Sku = Sku!.Trim().ToUpperInvariant(),
                Status = Status!.Trim(),
                Price = Price!.Value,
                Category = Category!.Trim(),
                LastUpdated = lastUpdated,
            };
        }

        public void ApplyTo(Product product, DateTimeOffset lastUpdated)
        {
            product.Name = Name!.Trim();
            product.Sku = Sku!.Trim().ToUpperInvariant();
            product.Status = Status!.Trim();
            product.Price = Price!.Value;
            product.Category = Category!.Trim();
            product.LastUpdated = lastUpdated;
        }

        public string NormalizedSku()
        {
            return Sku!.Trim().ToUpperInvariant();
        }

        private static void RequireText(Dictionary<string, string[]> errors, string field, string? value, int maxLength)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                errors[field] = [$"{field} is required."];
                return;
            }

            if (value.Trim().Length > maxLength)
            {
                errors[field] = [$"{field} must be {maxLength} characters or fewer."];
            }
        }
    }

    public static class ProductMapping
    {
        public static ProductResponse ToResponse(this Product product)
        {
            return new ProductResponse(
                product.Id,
                product.Name,
                product.Sku,
                product.Status,
                product.Price,
                product.Category,
                product.LastUpdated);
        }
    }
}
