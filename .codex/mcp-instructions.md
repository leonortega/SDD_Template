MCP-first documentation search guidance

Purpose
-------
This file documents the recommended behaviour for workspace agents and skills when searching repository documentation, Codex skills, provider adapters, and integration notes.

This is a persistent repo-level rule: documentation-search prompts must use MCP first.

Policy
------
1. Always use the MCP server named `monorepo-docs-search` (invoked via tool `mcp_monorepo-mark_search_documentation`) when resolving any user query that asks to search docs, skills, provider adapters, or model integration guidance. If the MCP is unavailable or returns no results, fall back to local search tools (`file_search`, `grep_search`, `read_file`) only after asking the user for confirmation.
2. Use the repository root as the `workspaceRoot` and pass the user's query as the `query` parameter. Use `subproject` only when the user specifies a subfolder.
3. If MCP returns results, summarize concisely (2-5 bullets), and include file links and line ranges so the user can inspect source files.
4. If MCP is unavailable or returns no results, fall back to local search tools (`file_search`, `grep_search`, `read_file`) but ask the user for confirmation before broad scans.
5. Do not query public web search engines for internal repo docs unless the user explicitly requests external web research.

Examples
--------
- "Search the Codex skills for deployment notes"
- "Find the Copilot/Cline provider adapter docs"
- "Show where MCP servers are registered"

Placement
---------
Place this file under `.codex/` so skills and automation that read `.codex` guidance can locate MCP-first instructions.
