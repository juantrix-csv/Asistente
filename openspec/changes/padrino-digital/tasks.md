# Tasks: Padrino Digital

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 1800–2000 |
| 800-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (F0+F1) → PR 2 (F2) → PR 3 (F3+F4) → PR 4 (F5+F6) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
800-line budget risk: High

### Suggested Work Units

| Unit | Goal | PR | Lines | Base |
|------|------|-----|-------|------|
| 1 | Foundation: structure, security config, Hermes install + Telegram gateway | PR 1 | ~305 | main |
| 2 | Core: SOUL.md, DB schema, inbox classifier, memory, tasks | PR 2 | ~550 | main |
| 3 | Life: daily planning, accountability coach, reviews, finance | PR 3 | ~470 | main |
| 4 | Hardening: code auditor, backup, security, cron jobs, docs | PR 4 | ~580 | main |

## Phase 0: Audit + Protection + Structure

- [x] 0.1 Create project tree: `skills/`, `scripts/config/`, `docs/`, `systemd/`, `sql/`, `memory/`, `auditor-profile/`, `cron/` with `.gitkeep` placeholders
- [x] 0.2 Write `scripts/setup.sh` — useradd padrino, umask 077, `/srv/padrino/data/`, dep checks (Python 3.11+ SQLite 3.35+), UFW enable, hermes install
- [x] 0.3 Write `scripts/config/path-allowlist.txt` and `scripts/config/command-allowlist.txt` with format documentation
- [x] 0.4 Write `scripts/config/repo-allowlist.txt` — empty template with format docs and column headers
- [x] 0.5 Create `docs/security-audit.md` skeleton: user, permissions, network, secrets, paths sections with placeholder findings

## Phase 1: Hermes + Telegram Integration

- [x] 1.1 Write `skills/padrino-hermes/SKILL.md` — YAML frontmatter, Hermes v0.18 install guide, `hermes gateway install/setup`, model routing, Telegram token config from `.env`
- [x] 1.2 Write `scripts/start.sh`, `stop.sh`, `restart.sh`, `status.sh` — systemctl wrappers for `hermes-gateway` with colored output
- [x] 1.3 Write `scripts/healthcheck.sh` — verify gateway HTTP 200, DB readable, memory dir writable; exit 0 on all-green, non-zero on failure
- [x] 1.4 Create `systemd/hermes-gateway.service` — User=padrino, Restart=on-failure, RestartSec=10, WantedBy=multi-user.target
- [x] 1.5 Create `.env.example` — `HERMES_TELEGRAM_TOKEN`, model API keys, `TZ=America/Argentina/Buenos_Aires`; reference chmod 600 requirement

## Phase 2: Core Personal

- [x] 2.1 Write `skills/padrino-soul/SKILL.md` — identity, 5 modes (normal/firme/crisis/enfoque/finanzas), approval gate rules, tone (voseo, no guilt, fact-vs-inference)
- [x] 2.2 Write `sql/001_initial_schema.sql` and `scripts/migrate.sh` — 17 tables (tasks, projects, goals, habits, habit_entries, transactions, budgets, savings_goals, debts, memories, memories_fts, decisions, daily_checkins, reminders, audit_runs, audit_findings, audit_log), indexes, triggers, schema_version
- [x] 2.3 Write `skills/padrino-inbox/SKILL.md` — LLM classifier for 13 types, confidence ≥80% auto-route, <80% ask user, `/inbox` command handler
- [x] 2.4 Write `skills/padrino-memory/SKILL.md` — capture with metadata (source/confidence/type/validity), FTS5 recall, journal append-only with timestamp, corrections via confirmation, `/recordar` command
- [x] 2.5 Write `skills/padrino-tasks/SKILL.md` — 8-status lifecycle with valid transitions, project CRUD, goal tracking with progress, reminders, `/tareas` `/proyecto` `/meta` commands
- [x] 2.6 Create memory templates — USER.md, MEMORY.md, preferences.md, goals.md, current_context.md + 5 area files + 5 project files

## Phase 3: Planning & Discipline

- [ ] 3.1 Write `skills/padrino-plan/SKILL.md` — multi-criteria ranking (due/priority/impact/snooze/energy), cap 3 priorities, overload detection, provisional plan when availability unknown, minimum-mode cap 2, `/plan` `/hoy` commands
- [ ] 3.2 Write `skills/padrino-coach/SKILL.md` — habit tracking with weekly compliance %, 3x-snooze escalation, 7-day stall detection, load-reduction recommend at <40%, minimum mode activation, `/habito` `/modo minimo` commands
- [ ] 3.3 Write `skills/padrino-review/SKILL.md` — daily checkin (energy, available_hours), evening aggregation (completed/pending/obstacle/expenses prompt), weekly/monthly synthesis across all data skills

## Phase 4: Finances

- [ ] 4.1 Write `skills/padrino-finance/SKILL.md` — transaction recording (expense/income/transfer/adjustment) with approval gate, budget tracking with % warnings, savings goals, debt monitoring, 7 finance rules enforcement, currency conversion with metadata, correction audit trail via reversal entries, ARS export, `/finanzas` `/gasto` `/presupuesto` commands

## Phase 5: Code Auditor

- [ ] 5.1 Write `skills/padrino-audit/SKILL.md` — `/auditar` command: allowlist check, `git clone --depth 1` read-only, detect lang/framework, diff from last `audit_runs.commit_hash`, analyze changed files, generate findings (severity/confidence/evidence/impact/reproduction), write `OpenCode_TASKS.md`
- [ ] 5.2 Create `auditor-profile/` skeleton — `SOUL.md` (minimal auditor persona, no Telegram), `.env` (read-only git tokens, 600 ref), `config.yaml`
- [ ] 5.3 Write `scripts/audit-repo.sh` — CLI wrapper: `hermes -p auditor chat -q "audit repo $1"`, validates URL against allowlist before invoking Hermes

## Phase 6: Robustness

- [ ] 6.1 Write `skills/padrino-backup/SKILL.md` — daily backup: tar.gz → sha256sum → gpg encrypt (AES-256, `PADRINO_BACKUP_KEY`), restore: checksum verify → decrypt → `integrity_check`, healthcheck (size anomaly, recovery alert), `/backup` `/restaurar` commands
- [ ] 6.2 Write `skills/padrino-security/SKILL.md` — path write enforcement via allowlist, command execution allowlist, `audit_log` append-only mutations, rate limiting on sensitive ops
- [ ] 6.3 Write `scripts/backup.sh`, `restore.sh`, `export.sh` — backup/restore workflow wrappers with confirmation prompts, finance CSV export
- [ ] 6.4 Create `cron/padrino-crons.txt` — 5 jobs: morning summary (0 8 * * *), evening review (30 21 * * *), weekly (0 19 * * 0), monthly (0 10 1 * *), daily backup (0 3 * * *); all self-contained prompts per design
- [ ] 6.5 Write `scripts/test.sh` — integration smoke tests: DB schema applied, SKILL.md files parse (all 11), healthcheck passes, backup round-trip (create + restore + verify)
- [ ] 6.6 Write `docs/` suite — `README.md`, `ARCHITECTURE.md`, `INSTALL.md`, `SECURITY.md`, `USER_GUIDE.md`, `SKILL_CATALOG.md`
