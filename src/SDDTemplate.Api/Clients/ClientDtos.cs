using System.Text.RegularExpressions;
using SDDTemplate.Data.Clients;

namespace SDDTemplate.Api.Clients
{
    public sealed record ClientResponse(
        int Id,
        string Name,
        string LastName,
        string Address,
        DateOnly BornDate,
        string City,
        string Country,
        string ZipCode);

    public sealed record ClientRequest(
        string? Name,
        string? LastName,
        string? Address,
        DateOnly? BornDate,
        string? City,
        string? Country,
        string? ZipCode)
    {
        private static readonly Regex ZipCodePattern = new("^[A-Za-z0-9][A-Za-z0-9 -]{2,11}$", RegexOptions.Compiled);

        public Dictionary<string, string[]> Validate(TimeProvider? timeProvider = null)
        {
            timeProvider ??= TimeProvider.System;
            Dictionary<string, string[]> errors = [];

            RequireText(errors, nameof(Name), Name, 100);
            RequireText(errors, nameof(LastName), LastName, 100);
            RequireText(errors, nameof(Address), Address, 200);
            RequireText(errors, nameof(City), City, 100);
            RequireText(errors, nameof(Country), Country, 100);
            RequireText(errors, nameof(ZipCode), ZipCode, 12);

            if (BornDate is null)
            {
                errors[nameof(BornDate)] = ["Born date is required."];
            }
            else if (BornDate > DateOnly.FromDateTime(timeProvider.GetUtcNow().UtcDateTime))
            {
                errors[nameof(BornDate)] = ["Born date cannot be in the future."];
            }

            if (!string.IsNullOrWhiteSpace(ZipCode) && !ZipCodePattern.IsMatch(ZipCode.Trim()))
            {
                errors[nameof(ZipCode)] = ["ZIP code must be 3 to 12 letters, digits, spaces, or hyphens."];
            }

            return errors;
        }

        public Client ToClient()
        {
            return new Client
            {
                Name = Name!.Trim(),
                LastName = LastName!.Trim(),
                Address = Address!.Trim(),
                BornDate = BornDate!.Value,
                City = City!.Trim(),
                Country = Country!.Trim(),
                ZipCode = ZipCode!.Trim(),
            };
        }

        public void ApplyTo(Client client)
        {
            client.Name = Name!.Trim();
            client.LastName = LastName!.Trim();
            client.Address = Address!.Trim();
            client.BornDate = BornDate!.Value;
            client.City = City!.Trim();
            client.Country = Country!.Trim();
            client.ZipCode = ZipCode!.Trim();
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

    public static class ClientMapping
    {
        public static ClientResponse ToResponse(this Client client)
        {
            return new ClientResponse(
                client.Id,
                client.Name,
                client.LastName,
                client.Address,
                client.BornDate,
                client.City,
                client.Country,
                client.ZipCode);
        }
    }
}
