namespace SDDTemplate.Data.Products
{
    public sealed class Product
    {
        public int Id { get; set; }

        public required string Name { get; set; }

        public required string Sku { get; set; }

        public required string Status { get; set; }

        public decimal Price { get; set; }

        public required string Category { get; set; }

        public DateTimeOffset LastUpdated { get; set; }
    }
}
