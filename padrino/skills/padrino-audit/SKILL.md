---
name: padrino-audit
description: Code auditor that clones read-only, analyzes diffs, produces structured findings, and generates OpenCode implementation tasks. Runs as a separate Hermes profile with no Telegram gateway.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    role: code-auditor
    profile: auditor
    tags: [padrino, audit, code-review, static-analysis, security]
    isolation: |
      This skill runs under a separate Hermes profile (~/.hermes_auditor/).
      No Telegram gateway. No write access to audited repos. Read-only git tokens only.
      Invoked via CLI: hermes -p auditor chat -q "audit repo {url}"
    related_skills: [padrino-security]
  deploy:
    profile_path: ~/.hermes_auditor/skills/padrino-audit/SKILL.md
    allowlist: ~/.hermes_auditor/config/repo-allowlist.txt
    note: |
      Copy this skill to the auditor profile, NOT to the main padrino profile.
      The auditor profile has its own .env with read-only git tokens.
---

# padrino-audit — Code Auditor

## Purpose

Audit authorized code repositories using read-only access. Produce structured
findings with severity, confidence, evidence, and reproduction steps. Generate
an `OpenCode_TASKS.md` file for implementation by another OpenCode session.

This skill works under the **auditor** Hermes profile (`~/.hermes_auditor/`),
which has no Telegram gateway and uses read-only git credentials.

## When to Use

- User sends `/auditar {repo-url}` via Telegram
- User runs `hermes -p auditor chat -q "audit repo {url}"` on the VPS
- User requests a specific repo audit from the allowlist

## Command

```
/auditar https://github.com/{owner}/{repo}
```

Aliases: `/audit`, `/auditar repo`, `/audit code`

## Invariants (NEVER violate these)

1. **NEVER modify audited code** — no commits, no pushes, no deploys, no file writes to cloned repos
2. **NEVER use write-capable git tokens** — auditor profile `.env` must contain read-only tokens
3. **NEVER access personal data** — no access to padrino.db, finances, diary, private memories, or Telegram conversations
4. **NEVER expose secrets found in code** — redact from logs, mark as CRITICAL with redacted evidence
5. **ALWAYS verify repo is in allowlist** before cloning — reject unauthorized repos immediately
6. **ALWAYS log audit execution** — record start, end, findings count, and status
7. **ALWAYS deduplicate findings** — if the same issue was flagged in a previous audit and is still present, reference the prior finding instead of creating a duplicate

---

## Audit Flow

### Step 1 — Authorization Check

Read `~/.hermes_auditor/config/repo-allowlist.txt` and verify the requested
repo URL is listed. If not listed:

```
Ese repositorio no está en mi lista de autorizados.
Agregalo primero en ~/.hermes_auditor/config/repo-allowlist.txt
```

Log the rejection to `audit_log` and STOP.

### Step 2 — Clone or Update

```bash
REPOS_DIR="$HOME/repositories"
mkdir -p "$REPOS_DIR"

REPO_NAME=$(basename "$REPO_URL" .git)

if [ -d "$REPOS_DIR/$REPO_NAME" ]; then
    cd "$REPOS_DIR/$REPO_NAME"
    git fetch --depth 1 origin
    git checkout FETCH_HEAD
else
    git clone --depth 1 "$REPO_URL" "$REPOS_DIR/$REPO_NAME"
fi
```

Use read-only credentials from `~/.hermes_auditor/.env`:
- `GIT_READONLY_TOKEN` — for GitHub private repos
- Public repos don't need auth

### Step 3 — Detect Language and Tooling

Examine the repo root for known signals:

| Signal | Language | Framework hints |
|--------|----------|----------------|
| `go.mod` | Go | Check for gin, echo, chi, fiber |
| `package.json` | JavaScript/TypeScript | Check dependencies: next, react, express, nest |
| `requirements.txt` / `pyproject.toml` | Python | Check for django, flask, fastapi |
| `Cargo.toml` | Rust | Check for actix, axum, rocket |
| `Gemfile` | Ruby | Check for rails, sinatra |
| `pom.xml` / `build.gradle` | Java/Kotlin | Check for spring, micronaut |
| `composer.json` | PHP | Check for laravel, symfony |
| `CMakeLists.txt` | C/C++ | — |
| `Dockerfile` | Container | Infrastructure |

Record the detected language and framework in `audit_runs`.

### Step 4 — Compute Diff (Incremental Audit)

Query the last audit for this repo:

```sql
SELECT commit_hash FROM audit_runs
WHERE repo_url = :repo_url AND status = 'completed'
ORDER BY id DESC LIMIT 1;
```

If a previous commit exists, compute the diff:

```bash
git diff {previous_commit}..HEAD --name-only
```

Only analyze files that changed. If this is the first audit, analyze the full codebase.

### Step 5 — Safe Static Analysis

Run **read-only, non-modifying** analysis tools based on detected language.

**Never run**: arbitrary scripts, test suites that modify files, build tools that
write to `node_modules/`, linters with `--fix`, or formatters with `--write`.

| Language | Safe tools |
|----------|-----------|
| Go | `go vet ./...`, `staticcheck ./...`, `golangci-lint run --no-fix` |
| TypeScript | `npx eslint . --no-fix`, `npx tsc --noEmit` |
| Python | `ruff check .`, `bandit -r .`, `mypy .` |
| All | `grep` for hardcoded secrets (`TODO`, `FIXME`, `HACK`), `git log --oneline -50` for commit hygiene |

### Step 6 — Analyze and Generate Findings

For each changed file and analysis output, generate structured findings.

---

## Finding Format

Every finding MUST include these fields:

```yaml
id: AUDIT-{YYYYMMDD}-{NNNN}  # e.g. AUDIT-20260705-0001
severity: critical | high | medium | low | info
confidence: 0-100             # 100 = confirmed, <70 = inferred
category: architecture | security | backend | frontend | database |
          api-contract | testing | performance | reliability |
          product-flow | maintainability | observability
summary: One-line description
evidence: |
  File: path/to/file.ext:42
  Code: the actual line(s) that triggered the finding
impact: What breaks if this isn't fixed
reproduction: Steps to reproduce the issue
acceptance_criteria: |
  - [ ] Criterion 1
  - [ ] Criterion 2
required_tests: |
  - Test case that proves the fix
restrictions: BLOCKED: Requires architecture decision | ""
possible_false_positive: true | false
```

### Severity Guide

| Severity | When to use |
|----------|------------|
| **critical** | Hardcoded secrets, SQL injection, auth bypass, data loss risk, RCE |
| **high** | Missing auth, XSS, broken error handling exposing internals, race conditions |
| **medium** | Missing input validation, deprecated APIs, missing error handling, N+1 queries |
| **low** | Code style inconsistency, missing comments on complex logic, unused imports |
| **info** | Suggestions, best practices, patterns that could be improved |

### Categories

| Category | Scope |
|----------|-------|
| `architecture` | Design patterns, layer boundaries, dependency direction, coupling |
| `security` | Auth, secrets, injection, CSRF, CORS, path traversal, permissions |
| `backend` | API design, error handling, async patterns, resource cleanup |
| `frontend` | Accessibility, state management, rendering performance, bundle size |
| `database` | Queries, indexes, migrations, connection pooling, data integrity |
| `api-contract` | Breaking changes, versioning, response shapes, error codes |
| `testing` | Missing tests, flaky tests, test coverage gaps, test isolation |
| `performance` | N+1 queries, unbounded loops, missing caching, memory leaks |
| `reliability` | Error recovery, retry logic, circuit breakers, graceful degradation |
| `product-flow` | UX inconsistencies, dead-end flows, confusing error messages |
| `maintainability` | Code duplication, magic numbers, coupling, documentation gaps |
| `observability` | Missing logging, metrics, tracing, healthchecks |

### Deduplication

Before inserting a finding, check against prior unresolved findings:

```sql
SELECT id, summary FROM audit_findings af
JOIN audit_runs ar ON af.audit_run_id = ar.id
WHERE ar.repo_url = :repo_url
  AND ar.id < :current_run_id
  AND af.summary LIKE '%' || :keyword || '%'
```

If a match exists, add a `reference: AUDIT-{prior_id}` to the new finding and
note "Previously reported as {prior_id} — still present."

---

## Step 7 — Generate OpenCode_TASKS.md

After all findings are collected, generate an implementation task file:

```markdown
# OpenCode Tasks — Audit of {repo_url}
**Date**: {date} | **Commit**: {commit_hash} | **Language**: {lang} | **Framework**: {fw}
**Findings**: {count} ({critical} CRITICAL, {high} HIGH, {medium} MEDIUM, {low} LOW, {info} INFO)

## Critical

### {finding.id}: {finding.summary}
**Category**: {finding.category} | **Confidence**: {finding.confidence}%
**Evidence**: {finding.evidence}
**Impact**: {finding.impact}

- [ ] Implement fix for {finding.id}
  - Acceptance criteria: {finding.acceptance_criteria}
  - Required tests: {finding.required_tests}
  {BLOCKED prefix if applicable}

## High
(…)

## Medium
(…)

## Low
(…)

## Info
(…)
```

If zero findings:
```markdown
# OpenCode Tasks — Audit of {repo_url}
**Date**: {date} | **Commit**: {commit_hash}

No findings to address. Audit completed clean. ✅
```

### Step 8 — Save Results

1. Insert the audit run into `audit_runs` (status = completed)
2. Insert all findings into `audit_findings`
3. Save `OpenCode_TASKS.md` to `reports/code-audits/{repo_name}/{date}/OpenCode_TASKS.md`
4. Log completion to `audit_log`
5. Return summary to user via Telegram (if invoked from main padrino) or stdout

---

## Report Storage

```
~/.hermes_auditor/reports/code-audits/
├── nexios-backend/
│   ├── 2026-07-05/
│   │   ├── OpenCode_TASKS.md
│   │   ├── findings.json
│   │   └── audit.log
│   └── 2026-06-28/
│       └── ...
└── nexios-frontend/
    └── 2026-07-01/
        └── ...
```

---

## Cross-Skill Contract

### Calls (outbound)
- **padrino-security**: Enforces repo allowlist and command allowlist for audit operations

### Called by
- **padrino-soul**: Routes `/auditar` commands here after approval gate check

### Events
- `audit.started` — audit began, emitted with repo_url and commit_hash
- `audit.completed` — audit finished, emitted with findings_count and report path
- `audit.rejected` — repo not in allowlist, emitted with repo_url and reason

### Database Tables
- **Writes to**: `audit_runs`, `audit_findings`, `audit_log` (via padrino-security)
- **Never reads from**: `transactions`, `memories`, `tasks`, `decisions`, or any personal data tables

---

## Privacy Note

This skill operates under the `auditor` Hermes profile, which has NO access to:
- Padrino Digital's SQLite database (`/srv/padrino/data/padrino.db`)
- Markdown memory files under `~/.hermes/memory/`
- Telegram conversations or user messages
- Personal finances, diary entries, or private memories

The auditor profile is a separate identity with its own `.env` file containing
read-only git tokens (never personal API keys). This separation is enforced at
the filesystem level by running under different system users or Hermes profiles.

---

## Error Handling

| Error | Response |
|-------|----------|
| Repo not in allowlist | Reject with explanation. Log security event. |
| Clone fails (network/auth) | Report: "No pude clonar el repo. Verificá que el token de solo-lectura esté configurado y el repo exista." |
| No language detected | Report: "No pude detectar el lenguaje del proyecto. ¿Es un repo de código?" |
| Analysis tool not installed | Skip that tool, note in report: "herramienta X no disponible — análisis parcial" |
| Zero changed files (incremental) | Report: "Sin cambios desde la última auditoría ({previous_commit}). Todo al día." |
| Audit produces >50 findings | Cap report at top 50 (by severity), note: "Hay {total} hallazgos. Mostrando los 50 más graves." |

---

## Examples

### Successful audit

```
Usuario: /auditar https://github.com/juantrix-csv/nexios-backend
Padrino: Iniciando auditoría de nexios-backend...
         ✓ Repo autorizado
         ✓ Clonado (Go + Chi router)
         ✓ Diff desde abc123 → def456: 12 archivos cambiados
         ✓ Análisis completado: 3 CRITICAL, 5 HIGH, 8 MEDIUM, 2 LOW
         
         Reporte guardado en reports/code-audits/nexios-backend/2026-07-05/
         OpenCode_TASKS.md listo para implementación.
```

### Unauthorized repo

```
Usuario: /auditar https://github.com/unknown/repo
Padrino: Ese repositorio no está en mi lista de autorizados.
         Agregalo primero en ~/.hermes_auditor/config/repo-allowlist.txt
```
