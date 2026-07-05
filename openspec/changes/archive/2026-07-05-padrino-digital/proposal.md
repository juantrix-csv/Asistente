# Proposal: Padrino Digital — Personal Assistant on Hermes Agent

## Intent

Build "Padrino Digital" — a comprehensive personal assistant system that captures, organizes,
and retrieves personal information, manages tasks/projects/finances, plans days without overload,
tracks discipline, audits code repos, and communicates through Telegram. Built ON TOP of Hermes
Agent v0.18.0 (Nous Research, MIT), NOT from scratch. Hermes already provides the gateway
(Telegram), memory (FTS5 + LightRAG), skills, cron, subagents, and model routing — Padrino
Digital extends it with domain-specific skills, structured data, and a personality definition.

## Scope

### In Scope
- SOUL.md personality definition (Padrino Digital identity, tone, approval gates)
- 11 custom Hermes skills (capture, recall, daily-plan, accountability, finance, reviews, code-audit, backup, etc.)
- SQLite DB schema: tasks, projects, goals, habits, transactions, budgets, debts, savings, memories, decisions, checkins, reminders, audit runs, audit findings
- Memory Markdown files: USER.md, MEMORY.md, preferences, goals, context, areas, projects, journal
- 11 operational scripts (setup, start, stop, restart, status, healthcheck, backup, restore, export, test, audit-repo)
- Full docs suite (README, architecture, installation, configuration, security, user guide, skill catalog)
- Security hardening (dedicated user, minimal permissions, encrypted backups, firewall, approval gates)
- Windows-local development → Debian/Ubuntu VPS deployment

### Out of Scope
- Custom LLM fine-tuning
- Mobile app, web UI, or custom frontend (Telegram is primary interface)
- Multi-user or team support
- Payment gateway integration (manual finance tracking only)

## Capabilities

### New Capabilities
All capabilities are new — no existing specs to modify.

- `padrino-soul`: Personality definition (SOUL.md), identity, tone, interaction rules, approval gates
- `hermes-integration`: Hermes v0.18.0 installation, Telegram gateway config, model routing, CLI setup
- `personal-memory`: Capture/recall of personal data, USER.md, MEMORY.md, context files, FTS5 search
- `task-management`: Tasks, projects, goals, commitments, inbox capture, priority system
- `daily-planning`: Daily plans (max 3 priorities), checkins, overload detection, postponed-task flagging
- `accountability-coach`: Habit tracking, minimum plans, discipline metrics, streak detection
- `finance-manager`: Transactions, budgets, debts, savings goals, income/expense reports
- `code-auditor`: Repository analysis via separate Hermes profile, audit reports as OpenCode markdown
- `scheduled-jobs`: Cron-based daily/weekly/monthly summaries, reminders, alerts
- `backup-manager`: Encrypted SQLite + Markdown backups, restore, export
- `security-hardening`: Dedicated system user, minimal permissions, UFW firewall, encrypted backups, sensitive-action approval

### Modified Capabilities
None — greenfield project.

## Approach

**Layered extension over Hermes Agent, not a fork.** Each Padrino Digital capability is a
Hermes `SKILL.md` file deployed to `~/.hermes/skills/`. The SQLite database and Markdown memory
files live alongside Hermes' own state. Scripts wrap `hermes` CLI commands for lifecycle management.
All sensitive actions (file writes, external commands, financial mutations) require explicit user
approval via Hermes' built-in approval system. Phased delivery: Fase 0 (audit/structure) through
Fase 6 (robustness). Each phase produces independently testable deliverables.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `~/.hermes/skills/` | New | 11 custom SKILL.md files |
| `~/.hermes/soul/SOUL.md` | New | Padrino Digital persona |
| `~/.hermes/memory/` | New | USER.md, MEMORY.md, context files |
| `padrino.db` | New | SQLite DB (14+ tables) |
| `scripts/` | New | 11 bash operational scripts |
| `docs/` | New | Full documentation suite |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Hermes Agent API changes break custom skills | Med | Pin to v0.18.x; test after each Hermes update; maintain skill compatibility table |
| SQLite schema migrations during active use | Low | Versioned schema; backup-before-migrate script; forward-compatible design |
| Telegram rate limiting on scheduled summaries | Low | Batch delivery; backpressure in cron jobs; configurable send windows |
| Sensitive data exposure via LLM context | Med | Approval gates on all mutations; exclude secrets from context; encrypted backups |

## Rollback Plan

Each phase is independently deployable. Rollback per phase:
1. Remove phase-specific SKILL.md files from `~/.hermes/skills/`
2. Restore SQLite DB from pre-phase backup (`scripts/backup.sh`)
3. Restart Hermes gateway (`scripts/restart.sh`)
4. Verify Telegram connectivity and basic commands

Full system rollback: restore from latest encrypted backup + re-run `scripts/setup.sh` from prior
version.

## Dependencies

- Hermes Agent v0.18.0 (MIT, github.com/NousResearch/hermes-agent)
- Python 3.11+ (Hermes runtime)
- SQLite 3.35+ (FTS5 for memory)
- Telegram Bot API token
- Debian/Ubuntu VPS for deployment (Windows for local dev)

## Success Criteria

- [ ] Telegram messages are received and responded to within 5 seconds
- [ ] All 11 skills load and execute without errors in Hermes
- [ ] SQLite DB created with correct schema; CRUD operations work from skills
- [ ] Daily plan generated with ≤3 priorities; overload detection triggers warning
- [ ] Transaction recorded, budget tracked, and monthly finance report generated
- [ ] Code audit produces valid OpenCode-formatted markdown report for a test repo
- [ ] Encrypted backup created, restored, and verified (round-trip)
- [ ] Cron-based daily summary delivered to Telegram without manual intervention
- [ ] All sensitive actions require explicit approval before execution
