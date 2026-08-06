<!-- TIER 3: STAGE-SPECIFIC - TDD test-first cycle pattern, shared across all flow skills -->

# Pipeline — TDD Test-First Cycle

## Usage

Use this pattern before writing any product code in a flow skill. Replace the placeholders:

- `{acSource}` — where to read the acceptance criteria from (e.g. bug ticket description, IA curated block)
- `{taskSource}` — where to read additional tasks from (e.g. `openspec/changes/<change>/tasks.md`)

## Pattern

### Phase A — ⚠️ MANDATORY: Write All Tests First (Zero Product Code)

Tests must be created based on the acceptance criteria (ACs) AND the tasks before any product code is written. This is a
hard gate — no product code without tests.

1. **Load the `tdd` skill** via `skill('tdd')` (or read `.codex/skills/tdd/SKILL.md` directly). Apply its test-first
cycles, RED/GREEN/REFACTOR guidance, and public-interface testing rules throughout.

2. **Read the acceptance criteria** from `{acSource}`. These are the contract. Also read `{taskSource}` for the task
list.

3. **Build the acceptance-to-test map** — map each AC and task to automated tests covering **three levels** (per
component/module, not per AC × task — one test file per component/module). See
`.codex/skills/_shared/test-requirements.md` for the complete level definitions, scope rules, folder structure, and
examples.

4. **Write tests for ALL acceptance criteria and tasks** before writing any product code:
   - **Unit tests** in `test/unit/` (one file per component)
   - **Integration tests** in `test/integration/` (one file per endpoint/feature, covers multiple ACs)
   - **Architecture tests** in `test/architecture/` as a **single project-wide file**

5. **Confirm every test is RED** — run the test suite and verify all new tests fail as expected (no product code yet =
tests cannot pass). If a test passes before product code exists, it's a false
positive — fix the test.

**❌ HARD RULE**: If product code is changed before ALL tests (unit + integration + architecture) are written and
confirmed RED, this is a process violation (authority level 5). Stop, record the gap,
write the missing tests, confirm RED, then continue.

### Phase B — Implement With TDD Cycles

1. **Implement one feature/fix at a time** through vertical TDD cycles:

   **🟡 RED phase — Write/confirm test:**
   - Apply `tdd` skill: test through public interface, one behavior per test
   - Apply stack-specific skills: use the correct test framework per declared stack
   - Apply `clean-code`: meaningful test names, arrange-act-assert structure

   **🟢 GREEN phase — Write minimal product code:**
   - Apply `ponytail full`: smallest working change, prefer standard library, no speculative abstractions
   - Apply stack-specific skills: follow framework conventions
   - Apply `clean-code`: meaningful names, small functions, single responsibility
   - Apply `security-best-practices`: validate inputs, sanitize outputs, avoid secrets in code
   - Apply `solid`: keep interfaces focused, depend on abstractions

   **🔵 REFACTOR phase — Improve while GREEN:**
   - Apply `clean-architecture`: respect Dependency Rule, layer separation
   - Apply `clean-code`: eliminate code smells, improve naming, extract functions
   - Apply `solid`: fix SRP violations, apply OCP where appropriate
   - Apply `design-pattern-review` if applicable

   After refactoring, rerun tests to confirm GREEN.

2. **Commit after each GREEN cycle** when tracked changes exist. Use ticket- or OpenSpec-prefixed messages. Keep code +
tests + docs together.

### Related Files

- `.codex/skills/_shared/test-requirements.md` — Test level definitions and examples
- `.codex/skills/tdd/SKILL.md` — Full TDD skill rules
