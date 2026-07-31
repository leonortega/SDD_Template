# Test Requirements

Centralized definition of test levels required by all implementation skills. This is the single source of truth for what types of tests must be written, what they validate, and their scope.

**Relationship to coverage configuration:** The test levels defined here are complementary to the coverage threshold in `.codex/quality.local.json` (`coverage.minimumPercent`, default `80`). Unit and integration tests drive coverage percentage; architecture tests enforce structural rules independently of coverage metrics.

---

## Three Test Levels

Every implementation must cover **three levels** of automated tests, written in TDD order (test first, then code):

| # | Test Level | What It Validates | Examples | Scope |
|---|------------|-------------------|----------|-------|
| 1 | **Unit tests** | Single function, component, or class in isolation (no network, no DB) | Function return value, component render output, state transition, pure logic | **Per component/module** — one test file per component |
| 2 | **Integration tests** | Interaction between units (API + DB, service + repository, middleware pipeline) | HTTP endpoint → service → repository round-trip, auth middleware flow, message broker publish/consume | **Per endpoint/feature** — one test file per endpoint or feature boundary |
| 3 | **Architecture tests** | Structural rules, layering, dependency constraints (no runtime, no external deps) | Layer access rules (presentation → domain ✓, domain → infra ✗), forbidden imports, naming conventions, package cycle prevention | **Project-wide** — one file for the entire change |

### Key Rules

1. **Scope:** The three levels apply **per component/module**, not per AC × task. One unit test file covers multiple ACs and tasks for the same component. One integration test file covers an entire endpoint or feature boundary. Architecture tests are a single project-wide file that validates the entire change.
2. **Order:** Tests MUST be written BEFORE product code (TDD RED phase). No product code is allowed until all three levels are written and confirmed RED.
3. **Folders:** Tests go in a separate `test/` directory (mirroring `src/` structure unless the stack convention dictates otherwise):
   - `test/unit/` — unit tests
   - `test/integration/` — integration tests
   - `test/architecture/` — architecture tests (single file per change)
4. **Framework:** Use the stack's test framework as declared in `project-profile.json → stack.testFrameworks` or detected from the project's build configuration (Vitest, pytest, xUnit, Jest, etc.).
5. **Coverage:** Unit and integration tests collectively must meet the `coverage.minimumPercent` threshold from `.codex/quality.local.json` (default `80`). Architecture tests do not contribute to coverage percentage but are mandatory for structural validation.

---

## Acceptance-to-Test Map

Before writing any code, build an acceptance-to-test map that traces each acceptance criterion (AC) and OpenSpec task to its corresponding test level. The map documents coverage and prevents gaps.

**Example map:**

| AC / Task | Unit Test | Integration Test | Architecture Test |
|-----------|-----------|-----------------|-------------------|
| AC-1: User can register | `test/unit/auth.RegisterUser.test.ts` | `test/integration/auth.register.test.ts` | `test/architecture/layering.test.ts` |
| AC-2: Duplicate email rejected | Same file (same component) | Same file (same endpoint) | Same file |
| Task-3: Add password hashing | `test/unit/auth.passwordHash.test.ts` | — | Same file |

---

## TDD Cycle Integration

Apply the test levels within the standard TDD RED/GREEN/REFACTOR cycle:

| Phase | Action | Test Level Focus |
|-------|--------|-----------------|
| 🟡 **RED** | Write/confirm failing test | Write unit test (per component), integration test (per endpoint), and/or confirm architecture test (project-wide) |
| 🟢 **GREEN** | Write minimal product code | Make the RED tests pass — unit + integration first, then verify architecture test still passes |
| 🔵 **REFACTOR** | Improve while tests stay GREEN | Rerun all three levels after each refactor to confirm nothing broke |

---

## Configuration Alignment

| Config File | Field | Value | Relationship |
|-------------|-------|-------|-------------|
| `.codex/quality.local.json` | `coverage.minimumPercent` | `80` (default) | **❌ HARD GATE (authority level 5).** Unit + integration tests must collectively meet this threshold before PR creation, PR review, or ticket handoff. See `dev-flow-implement-ticket/SKILL.md` Section 4. |
| `.codex/project-profile.json` | `stack.testFrameworks` | `[]` | Must be populated with the stack's test framework(s) before implementation |
| This file | Three test levels | Unit, integration, architecture | Enforced by all implementation skills as authority level 5 |

---

## Related Skills

- **`tdd`** skill (`.codex/skills/tdd/`) — test-first cycles, RED/GREEN/REFACTOR, public-interface testing rules
- **`clean-code`** skill — meaningful test names, arrange-act-act structure, single assertion per test
- **`security-best-practices`** skill — test security boundaries, input validation, error cases
- Coverage gate: `.codex/quality.local.json` → `coverage.minimumPercent`
