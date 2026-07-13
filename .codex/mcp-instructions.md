# MCP Routing Instructions — Mandatory

This file defines the **mandatory** MCP server routing for all agent prompts. Every agent **must** follow this routing whenever the task requires reading or searching repository content.

## Routing Contract

### Rule 1: Documentation/Markdown Content → `monorepo-docs-search`

When the task requires reading, searching, or understanding documentation, Markdown (`.md`, `.mdx`) files, Codex skills, provider adapters, or model-integration notes:

1. **Always** invoke `monorepo-docs-search` as the first source, using `search_documentation` with a concrete query.
2. This MCP uses BM25 ranking + FlashRank cross-encoder reranking — it returns the most relevant results with token-efficient snippets, reducing context waste compared to raw grep or glob.
3. If `monorepo-docs-search` is unavailable or returns zero results, fall back to `search_files` / regex grep with a narrow `file_pattern` (e.g. `*.md`), but only after confirming with the user.

### Rule 2: Code Files → `codebase-memory-mcp`

When the task requires navigating, searching, or understanding **source code** (any file that is not `.md`/`.mdx`):

| Need | Tool | Why |
|------|------|-----|
| Find a function, class, route, or variable by name or natural-language description | `search_graph` with `query` or `name_pattern` | BM25 ranking + structural boosting — definitions rank first, noise is filtered |
| Understand architectural overview (packages, services, dependencies) | `get_architecture` | Leiden community detection over call/import graph |
| Trace callers, callees, or data flow through a function | `trace_path` with `mode=calls` or `mode=data_flow` | Shows exact hop-by-hop paths with argument expressions |
| Cross-service HTTP/async call tracing | `trace_path` with `mode=cross_service` | Follows Route→Route edges across API boundaries |
| Read source code for a known symbol | `get_code_snippet` | Returns the exact source with optional neighbor relationships |
| Complex multi-hop analysis (find hot-path functions, deep loop nests, unguarded recursion) | `query_graph` with Cypher | Direct Neo4j access for aggregations and pattern matching |
| Pattern-based grep enriched with structural context | `search_code` | Grep + graph deduplication into containing functions, sorted by importance |

**When to use `search_graph` over `search_code`:**
- Natural-language discovery ("find the function that sends notifications") → `search_graph` with `query`
- Pattern-based lookup with exact name fragments → `search_graph` with `name_pattern`
- Need BM25-ranked, structurally-boosted results with pagination → `search_graph`

**When to use `search_code` over `search_graph`:**
- Need raw regex/text pattern matching across files (e.g. find all occurrences of a literal string)
- Need file-path-based filtering with `path_filter`

**Fallback:** If `codebase-memory-mcp` is unavailable, use `search_files` (regex grep) or `list_code_definition_names`, but flag the unavailability in the handoff summary.

### Rule 3: Mixed Tasks

When a task spans both documentation and code (e.g. "find the API route handler and read its OpenAPI spec"):

1. Use `codebase-memory-mcp` for the **code** portion.
2. Use `monorepo-docs-search` for the **documentation** portion.
3. Do not use one MCP to search for the other's domain.

### Rule 4: Never

- Do not use raw `search_files` (regex grep) as the **first** approach for documentation — route to `monorepo-docs-search` first.
- Do not use `monorepo-docs-search` for code files — it indexes only `.md`/`.mdx`.
- Do not fall back to generic grep/Boyer-Moore when a structured MCP tool exists for the domain — the MCP always provides better ranking and less context waste.
- Do not skip this routing "because the file is small" or "because I already know the answer" — always verify through the correct MCP channel.

## Authority

This routing contract sits at authority level 5 in `docs/context-management.md` — alongside `.codex/skills/_shared/delivery-contract.md` — and overrides ad hoc search decisions.
