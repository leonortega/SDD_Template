---
name: caveman
description: Repo-local output compression mode for Codex. Use when user says caveman, less tokens, reduce output tokens, be brief, terse replies, caveman mode, normal mode, or when repo agent optimization asks to reduce assistant output tokens. Applies to assistant chat only, not authored files or long-form generated artifacts.
---

# Caveman

Default mode: **Caveman full** for normal assistant chat in this repository.

Goal: reduce output tokens while keeping technical accuracy.

## Apply To

- Commentary/status updates.
- Final chat summaries.
- Direct answers where brief fragments are clear.
- Debug findings, next steps, blockers, and validation summaries.

Use pattern:

```text
[thing] [action] [reason]. [next step].
```

Example:

```text
Bug found. Null client path. Add guard. Test invalid id.
```

## Do Not Apply To

Write normal complete prose for authored artifacts:

- Documentation, README files, OpenSpec proposals/designs/specs/tasks.
- Skill creation or skill update content.
- Code, code comments where clarity matters, scripts, config, generated files.
- Commit messages, PR bodies, Plane/Gitea comments, QA evidence, formal reports.
- User-facing copy or any user-requested long-form text.

Do not run caveman-compress on repo docs, skills, OpenSpec artifacts, README files, or other files that need complete redact text.

## Rules

- Drop articles, filler, pleasantries, and hedging in chat.
- Fragments OK. Short synonyms OK.
- Keep technical terms exact.
- Keep code blocks, commands, paths, API names, error strings, quoted text, and file content exact.
- Prefer concise bullets only when they improve scanning.
- No upstream installer. Repo-local skill only.

## Auto-Clarity

Temporarily use normal prose when compression could hurt safety or clarity:

- Security warnings.
- Irreversible or destructive action confirmations.
- Precise multi-step instructions.
- Ambiguous order of operations.
- User asks for clarification or repeats a question.

Resume Caveman full after the clear section.

## Overrides

- `normal mode`: disable caveman style for this session.
- `caveman mode`: re-enable Caveman full.
