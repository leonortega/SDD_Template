## Why

Plane ticket `E2EPROJECT-8` asks for the home page to become a polished landing page for a stock and inventory management company. The current home page should better explain the service, show credible operational visuals, preserve existing app navigation, and give visitors a clear next action.

## What Changes

- Replace the home page experience with a responsive branded landing page for inventory management.
- Add a logo or placeholder-ready logo, relevant license-safe visual assets, hero content, services/features, benefits, and contact or final CTA sections.
- Update the header or page navigation so it includes existing routes (`/`, `/clients`, `/products`) plus section links (`#services`, `#benefits`, `#contact`).
- Add polished animation or transition behavior that improves presentation without blocking keyboard or pointer use.
- Preserve the existing Clients and Products routes and their accessibility from the menu.
- Add or update automated tests for the landing page behavior that can be verified without depending on fragile visual implementation details.

## Capabilities

### New Capabilities
- `landing-page`: Branded responsive landing page content, navigation, visuals, animation expectations, and route compatibility for the stock management site.

### Modified Capabilities
- None.

## Impact

- `src/SDDTemplate.Site/Components/Pages/Home.razor`
- `src/SDDTemplate.Site/Components/Layout/*` if shared navigation needs adjustment
- `src/SDDTemplate.Site/wwwroot/*` for styling and local visual assets
- `tests/SDDTemplate.Site.Tests/*` for route, markup, or rendered-content coverage
- No API, data model, deployment topology, or persistence changes are expected.
