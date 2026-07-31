# Security Best Practices — General Principles

Cross-cutting security guidance that applies to any language or framework. For framework-specific rules (Express, FastAPI, Django, Go, etc.), see the `_framework-specific/` subdirectory when a product stack is selected.

---

## 0) Safety, Boundaries, And Anti-Abuse Constraints (Must Follow)

- Never ask for or store actual secrets, tokens, cookies, passwords, connection strings, API keys, or credential-bearing URLs in chat, tickets, comments, logs, or committed files.
- Always report findings with specific file paths, line numbers, and evidence. Do not make vague security claims.
- Never change user-visible behavior, weaken existing security controls, or introduce regressions without explicit user approval.
- When in doubt, prefer the safer default: validate input, escape output, use parameterized queries, set secure cookie flags only over TLS.

## 1) Operating Modes

### 1.1 Generation mode (default)

Use security best practices while writing new code. Apply framework-specific rules from `_framework-specific/` when the product stack is known.

### 1.2 Passive review mode (always on while editing)

Passively detect major vulnerabilities in code being read or modified. Flag only critical/high-severity issues inline. Focus on: injection flaws, broken auth, sensitive data exposure, broken access control, XSS, SSRF, insecure deserialization, known-vulnerable dependencies.

### 1.3 Active audit mode (explicit scan request)

When the user requests a security review or vulnerability report:

1. Determine all languages and frameworks in the project scope (both frontend and backend).
2. Load `general-principles.md` (this file).
3. If a product stack is selected, load matching framework-specific files from `_framework-specific/`.
4. Produce a prioritized report with finding IDs, severity, file/line references, impact statements, and fix guidance.
5. Write the report to `security_best_practices_report.md` (or a user-specified location).

## 2) Definitions And Review Guidance

### 2.1 Untrusted input

Treat as attacker-controlled unless proven otherwise: URL params, query strings, request bodies, HTTP headers, uploaded files, cookies, environment variables consumed from user-facing config, third-party API responses, database values written through user-facing paths.

### 2.2 State-changing requests

POST, PUT, PATCH, DELETE — require authentication, authorization, CSRF protection, input validation, and idempotency where applicable.

### 2.3 Audit finding format

Each finding must include:

- **Finding ID**: `LANG-CATEGORY-NNN`
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW | INFO
- **File**: path and line number
- **Issue**: what is wrong
- **Impact**: one-line consequence
- **Fix**: concrete code change or configuration update
- **Validation**: how to verify the fix (test command, manual check)

## 3) Secure Baseline (All Frameworks)

### 3.1 Toolchain and dependencies

- Keep languages, frameworks, and runtime up to date with latest patch versions.
- Pin dependencies to specific versions or lockfiles. Enable automated vulnerability scanning (Dependabot, Snyk, Trivy).
- Remove unused dependencies. Do not install dev-only packages in production images.
- Verify package signatures or checksums where the package manager supports it.

### 3.2 HTTP server configuration

- Set reasonable timeouts: read timeout, write timeout, idle timeout, header timeout.
- Limit request body size to a sane maximum (e.g., 1-10 MB depending on your use case).
- Set HTTP header limits to prevent header injection attacks.
- Disable server version banners and framework fingerprinting in production.
- Use secure TLS configuration: TLS 1.2 minimum, strong cipher suites, HSTS only after thorough testing.

### 3.3 Secrets and configuration

- Never hardcode secrets. Use environment variables, secret managers, or encrypted config providers.
- Validate that all required configuration keys exist before the application starts.
- Use different secrets per environment (dev, QA, staging, prod).
- Rotate secrets regularly. Revoke compromised secrets immediately.

### 3.4 Authentication and authorization

- Use standard, well-reviewed auth libraries. Do not roll your own crypto or session management.
- Enforce strong password policies (minimum length, complexity) or prefer passwordless/SSO.
- Implement rate limiting on login endpoints to mitigate brute-force attacks.
- Use principle of least privilege for API keys, service accounts, and database credentials.
- For session management: use secure, HTTP-only cookies over TLS; regenerate session IDs after login.

### 3.5 Input validation and output encoding

- Validate all input on the server side: type, length, format, range, and allowed characters.
- Use parameterized queries or ORMs to prevent SQL/NoSQL injection. Never concatenate user input into queries.
- Encode output appropriately for the context: HTML entity encoding for HTML, JS encoding for script contexts, URL encoding for URLs.
- Use CSP headers to mitigate XSS. Set strict `Content-Security-Policy` headers.
- Validate and sanitize file uploads: check MIME type, limit size, scan for malware, store outside web root.

### 3.6 CSRF and CORS

- Use anti-CSRF tokens for all state-changing requests in session-based auth.
- Configure CORS restrictively: allow only known origins, do not use `Access-Control-Allow-Origin: *` with credentials.
- Validate `Origin` and `Referer` headers for sensitive operations.

### 3.7 Error handling and logging

- Return generic error messages to users. Log detailed errors server-side only.
- Never expose stack traces, database errors, or internal paths in production responses.
- Log security-relevant events: failed logins, authorization failures, input validation failures, rate limit triggers.
- Ensure logs do not contain secrets, PII, or session tokens.

### 3.8 Rate limiting and DoS protection

- Implement rate limiting on authentication endpoints, API endpoints, and resource-intensive operations.
- Use reverse proxy or middleware for global rate limiting.
- Set connection and memory limits to prevent resource exhaustion.

### 3.9 Dependency and supply chain

- Regularly audit dependencies for known vulnerabilities.
- Prefer official, maintained packages with active security response processes.
- Pin base Docker images to specific digests, not floating tags.

## 4) Framework-Specific Rules

When a product stack is selected (React, FastAPI, Express, Django, Go, etc.), load the matching file from `_framework-specific/` for precise rules:

- `_framework-specific/javascript-express-web-server-security.md`
- `_framework-specific/javascript-typescript-nextjs-web-server-security.md`
- `_framework-specific/javascript-general-web-frontend-security.md`
- `_framework-specific/javascript-jquery-web-frontend-security.md`
- `_framework-specific/javascript-typescript-react-web-frontend-security.md`
- `_framework-specific/javascript-typescript-vue-web-frontend-security.md`
- `_framework-specific/python-fastapi-web-server-security.md`
- `_framework-specific/python-django-web-server-security.md`
- `_framework-specific/python-flask-web-server-security.md`
- `_framework-specific/golang-general-backend-security.md`

## 5) General Heuristics For Security Review

- Look for injection points: raw SQL queries, OS command execution, eval(), template rendering with user data, file path traversal.
- Check authentication: hardcoded credentials, missing auth on sensitive endpoints, weak password policies, missing MFA.
- Check authorization: IDOR vulnerabilities, missing role checks, insecure direct object references.
- Check data exposure: secrets in configs/committed files, excessive logging, missing encryption at rest/in transit, verbose error messages.
- Check session management: predictable session tokens, missing rotation, missing secure/httpOnly flags, missing expiry.
- Check file handling: unrestricted uploads, path traversal, missing MIME validation, uploads inside web root.
- Check dependencies: outdated libraries, known CVEs, unmaintained packages, unused dependencies.
- Check deployment: debug mode enabled in production, exposed admin panels, missing WAF, missing monitoring.

## 6) Sources

This consolidated guidance is derived from the OWASP Top 10, OWASP ASVS, CWE Top 25, and framework-specific security best practices maintained in the `_framework-specific/` subdirectory.
