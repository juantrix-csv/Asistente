# code-auditor Specification

## Purpose

Audit authorized code repositories using a separate Hermes profile with restricted access. Produce structured findings and OpenCode-formatted implementation tasks. Never modify, commit, push, or deploy audited code.

## Requirements

### Requirement: Read-Only Repository Audit

The system MUST clone or update authorized repositories using read-only credentials. The audit SHALL detect the repository's language and tooling, analyze the diff from the last audit, run tests and safe static analysis, and produce structured findings. The system MUST NOT modify audited code, commit, push, or deploy under any circumstance.

#### Scenario: First audit of an authorized repo

- GIVEN repo "nexios-frontend" is in the authorized allowlist
- AND no prior audit exists for this repo
- WHEN the code auditor runs
- THEN it SHALL clone the repo with read-only credentials
- AND SHALL detect the language and framework (e.g., TypeScript, React, Next.js)
- AND SHALL analyze the full codebase (no prior diff available)
- AND SHALL produce findings organized by category

#### Scenario: Incremental audit from last run

- GIVEN a prior audit exists for repo "nexios-backend" at commit abc123
- AND the repo is now at commit def456
- WHEN the code auditor runs
- THEN it SHALL compute the diff between abc123 and def456
- AND SHALL only analyze changed files for new issues
- AND SHALL include prior unresolved findings in the report with status

#### Scenario: Unauthorized repo rejected

- GIVEN the user requests an audit of repo "some-random-repo" not in the allowlist
- WHEN the code auditor processes this request
- THEN it SHALL refuse: "Ese repositorio no está en mi lista de autorizados. Agregalo primero a la configuración."
- AND SHALL NOT clone or access the repository

### Requirement: Structured Findings with Severity

Every finding MUST include: ID, severity (critical, high, medium, low, info), confidence (0-100), category (architecture, security, backend, frontend, database, api-contract, testing, performance, reliability, product-flow, maintainability, observability), summary, evidence (file:line), impact, reproduction steps, acceptance criteria, required tests, restrictions, and possible false positives.

#### Scenario: Security finding

- GIVEN the audit detects an API key hardcoded in source code
- WHEN the finding is generated
- THEN severity SHALL be "critical"
- AND category SHALL be "security"
- AND evidence SHALL include the exact file and line number
- AND the finding SHALL include: "Possible false positive: confirm this is not a placeholder/mock value before taking action"

#### Scenario: Low-severity style finding

- GIVEN the audit detects inconsistent import ordering across 15 files
- WHEN the finding is generated
- THEN severity SHALL be "low"
- AND category SHALL be "maintainability"
- AND the finding SHALL NOT block the audit or require immediate action

#### Scenario: Finding with reproduction steps

- GIVEN the audit detects a potential race condition in an async handler
- WHEN the finding is generated
- THEN it SHALL include reproduction steps: specific actions to trigger the condition
- AND SHALL include required tests: what test cases would prove the fix
- AND confidence SHALL reflect whether it was confirmed or inferred

### Requirement: OpenCode Task Generation

After completing the audit, the system MUST generate an `OpenCode_TASKS.md` file containing implementation tasks derived from the findings. Tasks SHALL be organized by severity and SHALL reference the finding ID they address. Each task SHALL include acceptance criteria from the finding.

#### Scenario: Generate tasks from audit findings

- GIVEN an audit produced 3 critical, 5 high, and 12 medium findings
- WHEN OpenCode_TASKS.md is generated
- THEN tasks SHALL be grouped by severity (critical first)
- AND each task SHALL reference its finding ID
- AND each task SHALL include the finding's acceptance criteria

#### Scenario: Audit with no findings

- GIVEN an audit produces zero findings
- WHEN OpenCode_TASKS.md is generated
- THEN the file SHALL contain: "No findings to address. Audit completed clean."
- AND SHALL include the audit timestamp and repo commit reference

#### Scenario: Task marks itself as not for auto-implementation

- GIVEN a finding has restrictions (e.g., "Requires architecture decision before implementing")
- WHEN the corresponding task is generated
- THEN the task SHALL include a "BLOCKED:" prefix with the restriction
- AND SHALL NOT be presented as ready for implementation
