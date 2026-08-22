# Angular 20 Hydration Default

## Symptoms

NG0908 hydration mismatch error on page load. The error persists even after:
- Adding `provideClientHydration()` to app config
- Setting `"ssr": false` in angular.json

## Root Cause

Angular 20's `@angular-devkit/build-angular:application` builder includes hydration in the client bundle by default. The `ssr: false` flag only controls server bundle generation, not client-side hydration code.

## Fix

Switch from `application` builder to the legacy `browser` builder:

```json
{
  "builder": "@angular-devkit/build-angular:browser",
  "options": {
    "main": "src/main.ts",
    "polyfills": ["zone.js"],
    "ssr": false
  }
}
```

The `browser` builder does not include hydration in the client bundle.

## Additional Notes

- The `application` builder outputs to `dist/browser/`, the `browser` builder outputs to `dist/`
- Dockerfile COPY path must match the builder output
- 39/39 tests pass with the browser builder

## Related

- PR #20, #21, #22 — three attempts to fix before finding the root cause
- `apps/tkp-web/angular.json` — build configuration
