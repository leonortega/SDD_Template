---
name: "security-best-practices"
description: "Perform language and framework specific security best-practice reviews and suggest improvements. Trigger only when the user explicitly requests security best practices guidance, a security review/report, or secure-by-default coding help. Trigger only for supported languages (python, javascript/typescript, go). Do not trigger for general code review, debugging, or non-security tasks."
---

# Security Best Practices

## Overview

This skill provides a description of how to identify the language and frameworks used by the current context, and then to load information from this skill's references directory about the security best practices for this language and or frameworks.

This information, if present, can be used to write new secure by default code, or to passively detect major issues within existing code, or (if requested by the user) provide a vulnerability report and suggest fixes.

## Workflow

The initial step for this skill is to identify ALL languages and ALL frameworks in the project scope. Focus on the primary core frameworks, including both frontend and backend.

Then read `references/general-principles.md` — this covers cross-cutting security guidance for any framework.

If a product stack is selected and framework-specific rules are needed, load matching files from `references/_framework-specific/`. The filename format is `<language>-<framework>-<stack>-security.md`.

If working on a web application with both frontend and backend, read guidance for both sides when framework-specific files are available. For web apps with an unspecified frontend framework, check `references/_framework-specific/javascript-general-web-frontend-security.md`.

If no matching framework-specific guidance exists, use general security knowledge and OWASP Top 10 principles.

From there it can operate in a few ways:

1. **Generation mode (default)**: Use security best practices while writing new code.
2. **Passive review mode**: Detect major vulnerabilities while editing — flag critical/high issues inline.
3. **Active audit mode**: Produce a full prioritized security report when the user explicitly requests one.

## Workflow Decision Tree

- If the language/framework is unclear, inspect the repo to determine it and list your evidence.
- First load `references/general-principles.md` for cross-cutting guidance.
- If a product stack is selected and matching framework-specific guidance exists in `references/_framework-specific/`, load only the relevant files and follow their instructions.
- If no matching guidance exists, use general security best practices. If asked for a report, let the user know if concrete framework-specific guidance is unavailable.

# Overrides

While these references contain the security best practices for languages and frameworks, customers may have cases where they need to bypass or override these practices. Pay attention to specific rules and instructions in the project's documentation and prompt files which may require you to override certain best practices. When overriding a best practice, you MAY report it to the user, but do not fight with them. If a security best practice needs to be bypassed / ignored for some project specific reason, you can also suggest to add documentation about this to the project so it is clear why the best practice is not being followed and to follow that bypass in the future.

# Report Format

When producing a report, you should write the report as a markdown file in `security_best_practices_report.md` or some other location if provided by the user. You can ask the user where they would like the report to be written to.

The report should have a short executive summary at the top.

The report should be clearly delineated into multiple sections based on severity of the vulnerability. The report should focus on the most critical findings as these have the highest impact for the user. All findings should be noted with an numeric ID to make them easier to reference.

For critical findings include a one sentence impact statement.

Once the report is written, also report it to the user directly, although you may be less verbose. You can offer to explain any of the findings or the reasons behind the security best practices guidance if the user wants more info on any findings.

Important: When referencing code in the report, make sure to find and include line numbers for the code you are referencing.

After you write the report file, summarize the findings to the user.

Also tell the user where the final report was written to

# Fixes

If you produced a report, let the user read the report and ask to begin performing fixes.

If you passively found a critical finding, notify the user and ask if they would like you to fix this finding.

When producing fixes, focus on fixing a single finding at a time. The fixes should have concise clear comments explaining that the new code is based on the specific security best practice, and perhaps a very short reason why it would be dangerous to not do it in this way.

Always consider if the changes you want to make will impact the functionality of the user's code. Consider if the changes may cause regressions with how the project works currently. It is often the case that insecure code is relied on for other reasons (and this is why insecure code lives on for so long). Avoid breaking the user's project as this may make them not want to apply security fixes in the future. It is better to write a well thought out, well informed by the rest of the project, fix, then a quick slapdash change.

Always follow any normal change or commit flow the user has configured. If making git commits, provide clear commit messages explaining this is to align with security best practices. Try to avoid bunching a number of unrelated findings into a single commit.

Always follow any normal testing flows the user has configured (if any) to confirm that your changes are not introducing regressions. Consider the second order impacts the changes may have and inform the user before making them if there are any.

# General Security Advice

Below is a few bits of secure coding advice that applies to almost any language or framework.

### Avoid Using Incrementing IDs for Public IDs of Resources

When assigning an ID for some resource, which will then be used by exposed to the internet, avoid using small auto-incrementing IDs. Use longer, random UUID4 or random hex string instead. This will prevent users from learning the quantity of a resource and being able to guess resource IDs.

### A note on TLS

While TLS is important for production deployments, most development work will be with TLS disabled or provided by some out-of-scope TLS proxy. Due to this, be very careful about not reporting lack of TLS as a security issue. Also be very careful around use of "secure" cookies. They should only be set if the application will actually be over TLS. If they are set on non-TLS applications (such as when deployed for local dev or testing), it will break the application. You can provide a env or other flag to override setting secure as a way to keep it off until on a TLS production deployment. Additionally avoid recommending HSTS. It is dangerous to use without full understanding of the lasting impacts (can cause major outages and user lockout) and it is not generally recommended for the scope of projects being reviewed by codex.

## Shared Context

Source: https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices

Before using this repo-local copy for ticketed delivery, read `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md`. Apply the active ticket scope, repository validation gates, secret-handling rules, and handoff expectations before changing code, tests, local config, QA evidence, deployment behavior, or security documentation.

Pair this skill with the selected future stack guidance when a product stack exists.

## Output

For a security review, report findings with file and line references, severity, validation performed, and ticket or handoff notes. For secure-by-default implementation, report the security guidance applied and the validation commands run.

## Failure Rules

Stop and report a blocker when a security fix would change user-visible behavior, weaken repository secret rules, require unsupported framework assumptions, or cannot be validated safely within the active ticket scope.
