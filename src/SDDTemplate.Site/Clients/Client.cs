namespace SDDTemplate.Site.Clients
{
    public sealed class Client
    {
        public int Id { get; set; }

        public required string Name { get; set; }

        public required string LastName { get; set; }

        public required string Address { get; set; }

        public DateOnly BornDate { get; set; }

        public required string City { get; set; }

        public required string Country { get; set; }

        public required string ZipCode { get; set; }
    }
}
