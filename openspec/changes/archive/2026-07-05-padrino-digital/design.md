# Design: Padrino Digital

## Technical Approach

Layered extension of Hermes Agent v0.18.0 — NOT a fork. Each Padrino Digital domain is a `SKILL.md` file under `~/.hermes/skills/padrino-*/`. Structured data in SQLite at `/srv/padrino/data/padrino.db`. Markdown memory in `~/.hermes/memory/`. Telegram is the primary interface via Hermes Gateway. Cron jobs use Hermes' built-in scheduler. Code auditor runs as a separate Hermes profile (`~/.hermes/auditor/`) with read-only access. Encryption via GPG symmetric (AES-256). All sensitive mutations require explicit approval gates.

## Architecture Decisions

| # | Decision | Option A vs B | Chosen | Why |
|---|----------|---------------|--------|-----|
| 1 | DB location | `~/.hermes/data/` vs `/srv/padrino/data/` | `/srv/padrino/data/padrino.db` | FHS-compliant, separates Hermes internals from app data, survives Hermes reinstall |
| 2 | Skill granularity | Monolithic vs 11 focused skills | 11 composable skills | One domain per skill; clear boundaries; independent testability per phase |
| 3 | Auditor isolation | Same profile vs separate profile | Separate `~/.hermes/auditor/` profile | Read-only git clones, no write paths, no Telegram gateway — prevents accidental mutation |
| 4 | Backup encryption | openssl vs gpg | GPG symmetric (AES-256) | Simpler CLI, key from `PADRINO_BACKUP_KEY` env var, no cert management |
| 5 | Markdown memory | Flat files vs Hermes-native memory | `~/.hermes/memory/` (Hermes-native) | Hermes already provides FTS5 indexing; avoid duplicating search infra |
| 6 | Cron timezone | UTC vs ART | ART (America/Argentina/Buenos_Aires) | User lives in ART; morning 08:00 ART = 11:00 UTC; system TZ set in `.env` |
| 7 | Inbox classifier | Rule-based vs LLM-only | LLM with confidence thresholds | Rules can't handle Rioplatense Spanish ambiguity; LLM classifies, low-confidence → asks user |
| 8 | Approval gates | Hermes-native vs custom | Hermes-native `approval_required` | Already built into Hermes skill execution model; no reinvention needed |

## Directory Layout

```
/home/padrino/                          # Dedicated user home
├── .hermes/
│   ├── SOUL.md -> padrino-soul/SOUL.md  # Symlink to Padrino persona
│   ├── .env                             # HERMES_TELEGRAM_TOKEN, API keys (600)
│   ├── config.yaml                      # Hermes config
│   ├── skills/
│   │   ├── padrino-soul/SKILL.md       # Persona, modes, approval gates
│   │   ├── padrino-inbox/SKILL.md      # Universal inbox classifier
│   │   ├── padrino-memory/SKILL.md     # Capture, recall, journal
│   │   ├── padrino-tasks/SKILL.md      # Tasks, projects, goals
│   │   ├── padrino-plan/SKILL.md       # Daily planning, overload detection
│   │   ├── padrino-coach/SKILL.md      # Habits, accountability, minimum mode
│   │   ├── padrino-finance/SKILL.md    # Transactions, budgets, savings, debts
│   │   ├── padrino-review/SKILL.md     # Daily/weekly/monthly reviews
│   │   ├── padrino-backup/SKILL.md     # Encrypted backup, restore, healthcheck
│   │   └── padrino-security/SKILL.md   # Audit log, allowlist enforcement
│   ├── memory/                          # USER.md, MEMORY.md, areas/, journal/
│   ├── sessions/                        # Hermes-managed
│   ├── data/                            # Hermes-managed
│   └── logs/                            # Hermes logs
├── .hermes_auditor/                     # Separate profile for code-auditor
│   ├── SOUL.md                          # Minimal auditor persona
│   ├── .env                             # Read-only git tokens
│   ├── skills/
│   │   └── padrino-audit/SKILL.md      # Clone, diff, analyze, report
│   └── memory/                          # Audit findings cache
└── padrino/scripts/                     # Operational scripts
    ├── setup.sh, start.sh, stop.sh, restart.sh, status.sh
    ├── healthcheck.sh, backup.sh, restore.sh, export.sh
    ├── test.sh, audit-repo.sh
    └── config/                          # allowlists, retention policy
/srv/padrino/data/
├── padrino.db                           # SQLite database (14+ tables)
└── backups/                             # Encrypted .tar.gz.gpg archives
```

## SOUL.md Design

The Padrino Digital persona extends Hermes' global SOUL.md mechanism. It defines:

**Identity**: "Soy Padrino Digital, tu asistente personal. Te ayudo a organizar tareas, finanzas, disciplina, y proyectos. Hablo con evidencia, no con opiniones."

**Five Modes** (activated by `/modo {name}` or context auto-detection):

| Mode | Trigger | Behavior |
|------|---------|----------|
| `normal` | Default | Balanced, warm, Rioplatense voseo |
| `firme` | `/modo firme` or 3+ snoozes detected | Direct, accountability-focused, no softening |
| `crisis` | Emergency keywords in user message | Calm, structured, minimal words, no questions |
| `enfoque` | `/modo enfoque` or deep-work hours | Silent unless critical; defers non-urgent |
| `finanzas` | Finance query detected | Analytical, disclaimers on every projection |

**Approval Gates**: Any operation that writes files, mutates DB rows, executes shell commands, or exposes personal data MUST call `approval_required` with description + rationale. Reads and FTS5 searches skip gates.

**Tone Rules**: Never guilt/shame. Always differentiate fact ("Registrado: $X") from inference ("Basado en eso, estimo..."). Warm but direct. Voseo (vos, tenés, hacés).

## SQLite Schema

Database: `/srv/padrino/data/padrino.db`. All tables use `sqlite-utils` conventions (integer PK `id`, `created_at`/`updated_at` triggers). Version stored in `schema_version` table.

```sql
-- Schema version tracking
CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')));

-- WARNING: Do NOT apply schema changes loaded via this 'Layered skills
-- extending Hermes v0.18.0' approach without bumping the version and
-- running the migration script. The design phase covers forward-compatible
-- schema design, explicit migration scripts, and backup-before-migrate.

-- Core entities
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, description TEXT,
    status TEXT NOT NULL DEFAULT 'inbox'
        CHECK(status IN ('inbox','todo','scheduled','in_progress','blocked','waiting','done','cancelled')),
    priority INTEGER DEFAULT 0, project_id INTEGER REFERENCES projects(id),
    due_at TEXT, scheduled_at TEXT, estimated_minutes INTEGER, actual_minutes INTEGER,
    snooze_count INTEGER DEFAULT 0, last_snoozed_at TEXT,
    source TEXT, tags TEXT, blocked_by TEXT,
    archived_at TEXT, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_due ON tasks(due_at);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE, description TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','paused','completed','archived')),
    area TEXT, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL, target_value REAL, current_value REAL DEFAULT 0,
    unit TEXT, project_id INTEGER REFERENCES projects(id),
    deadline TEXT, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_goals_project ON goals(project_id);

CREATE TABLE habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE, description TEXT,
    frequency TEXT NOT NULL CHECK(frequency IN ('daily','weekly','monthly')),
    expected_count INTEGER NOT NULL, minimum_count INTEGER,
    unit TEXT, area TEXT, created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE habit_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL REFERENCES habits(id),
    date TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
    value REAL, notes TEXT, created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(habit_id, date)
);
CREATE INDEX idx_habit_entries_date ON habit_entries(date);

CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('income','expense','transfer','adjustment')),
    amount REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'ARS',
    category TEXT, account TEXT,
    business_area TEXT CHECK(business_area IN ('personal','Ascend','fletes','Nexios','Rastrojero','home-gym','otros')),
    payment_method TEXT, date TEXT NOT NULL, description TEXT,
    recurring INTEGER DEFAULT 0, correction_id INTEGER,
    original_currency TEXT, original_amount REAL,
    conversion_rate REAL, conversion_source TEXT, conversion_date TEXT,
    created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_correction ON transactions(correction_id);

CREATE TABLE budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL, period TEXT NOT NULL CHECK(period IN ('monthly','weekly','annual')),
    limit_amount REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'ARS',
    warning_percent REAL DEFAULT 80, created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE savings_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, target_amount REAL NOT NULL,
    current_amount REAL DEFAULT 0, currency TEXT NOT NULL DEFAULT 'ARS',
    deadline TEXT, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, description TEXT,
    total_amount REAL NOT NULL, remaining_amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'ARS', creditor TEXT,
    interest_rate REAL, due_date TEXT, status TEXT DEFAULT 'active'
        CHECK(status IN ('active','paid','defaulted')),
    created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL, source TEXT NOT NULL
        CHECK(source IN ('user_statement','observation','inference','import')),
    confidence TEXT NOT NULL
        CHECK(confidence IN ('confirmed','high','medium','low','speculative')),
    type TEXT NOT NULL CHECK(type IN ('fact','preference','decision','hypothesis')),
    area TEXT, project TEXT, tags TEXT,
    validity_until TEXT, created_at TEXT DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE memories_fts USING fts5(content, source, area, project, tags, content=memories, content_rowid=id);
CREATE INDEX idx_memories_area ON memories(area);
CREATE INDEX idx_memories_validity ON memories(validity_until);

CREATE TABLE decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, context TEXT, options TEXT, chosen TEXT,
    rationale TEXT, status TEXT DEFAULT 'active', created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE daily_checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE, available_hours REAL,
    energy_level TEXT CHECK(energy_level IN ('high','medium','low')),
    minimum_mode INTEGER DEFAULT 0, notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, description TEXT,
    remind_at TEXT NOT NULL, recurrence TEXT, delivered INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_reminders_deliver ON reminders(remind_at, delivered);

CREATE TABLE audit_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_url TEXT NOT NULL, commit_hash TEXT, previous_commit TEXT,
    language TEXT, framework TEXT, findings_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running' CHECK(status IN ('running','completed','failed')),
    started_at TEXT DEFAULT (datetime('now')), completed_at TEXT
);

CREATE TABLE audit_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_run_id INTEGER NOT NULL REFERENCES audit_runs(id),
    severity TEXT NOT NULL CHECK(severity IN ('critical','high','medium','low','info')),
    confidence INTEGER NOT NULL CHECK(confidence BETWEEN 0 AND 100),
    category TEXT NOT NULL, summary TEXT NOT NULL,
    evidence TEXT, impact TEXT, reproduction TEXT,
    acceptance_criteria TEXT, required_tests TEXT,
    restrictions TEXT, possible_false_positive INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_audit_findings_run ON audit_findings(audit_run_id);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    action TEXT NOT NULL, actor TEXT NOT NULL DEFAULT 'padrino',
    target TEXT, result TEXT, details TEXT
);

-- Trigger: auto-update updated_at
CREATE TRIGGER trg_tasks_updated AFTER UPDATE ON tasks
BEGIN UPDATE tasks SET updated_at = datetime('now') WHERE id = NEW.id; END;
CREATE TRIGGER trg_transactions_updated AFTER UPDATE ON transactions
BEGIN UPDATE transactions SET updated_at = datetime('now') WHERE id = NEW.id; END;
-- (similar triggers for projects, goals, savings_goals, debts)
```

## Skill Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     HERMES GATEWAY (Telegram)                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ incoming message
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  padrino-soul (SOUL.md)                                         │
│  ┌─ Mode detection ──┐  ┌─ Approval gate check ──┐             │
│  │ /modo firme, etc  │  │ writes? commands?       │             │
│  └───────────────────┘  │ files? → gate if yes    │             │
│                         └─────────────────────────┘             │
└──────────────────────────────┬──────────────────────────────────┘
                               │ classified intent
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  padrino-inbox (Universal Classifier)                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ LLM classifies → task|idea|memory|decision|expense|       │   │
│  │ income|goal|habit|reminder|project_update|                │   │
│  │ code_audit_request|journal_entry|unknown                  │   │
│  │                                                           │   │
│  │ confidence > 0.8 → auto-route                             │   │
│  │ confidence < 0.8 → ask user: "¿Es X, Y, o Z?"            │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────┬───────┬───────┬───────┬───────┬───────┬────────────────┘
        │       │       │       │       │       │
        ▼       ▼       ▼       ▼       ▼       ▼
   ┌────────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────────┐
   │memory  ││tasks ││plan  ││coach ││finance││audit     │
   │capture ││CRUD  ││daily ││habits││track  ││read-only │
   │recall  ││inbox ││check ││detect││budget ││diff scan │
   │journal ││proj  ││overld││min-mo││saving ││report    │
   └───┬────┘└──┬───┘└──┬───┘└──┬───┘└──┬────┘└────┬─────┘
       │        │       │       │       │         │
       └────────┴───────┴───────┴───────┴─────────┘
                          │
                          ▼
              /srv/padrino/data/padrino.db
```

**Cross-skill dependencies**: `padrino-plan` reads from `padrino-tasks` and `padrino-coach`. `padrino-review` aggregates across all data skills. `padrino-coach` triggers `padrino-plan` to cap priorities when minimum mode activates. Skills NEVER write to another skill's domain directly — only through shared DB tables.

## Telegram Message Flow

```
User → Telegram API → Hermes Gateway → padrino-soul (mode+gate)
    → padrino-inbox (classify)
    → Domain Skill (process)
    → padrino-soul (format response)
    → Hermes Gateway → Telegram API → User
```

Commands vs NL: `/inbox`, `/hoy`, `/plan`, `/finanzas`, `/auditar`, `/modo`, `/backup`, `/recordar` are explicit commands that skip the classifier. Natural language messages always route through the inbox classifier.

## Cron Job Design (ART timezone, self-contained prompts)

| Job | Cron | Hermes prompt (self-contained) | Dedup |
|-----|------|--------------------------------|-------|
| Morning summary | `0 8 * * *` | "Generá el resumen matutino para hoy. Consultá padrino.db para prioridades, compromisos, vencimientos. No uses contexto de conversación." | `SELECT 1 FROM daily_checkins WHERE date=today() AND morning_delivered=1` |
| Evening review | `30 21 * * *` | "Generá la revisión nocturna. Listá tareas completadas, pendientes, y preguntá por gastos no registrados." | `daily_checkins.evening_delivered` flag |
| Weekly review | `0 19 * * 0` | "Generá revisión semanal completa: logros, hábitos, finanzas, proyectos estancados." | `weekly_reviews` table with `(year, week)` unique constraint |
| Monthly review | `0 10 1 * *` | "Generá revisión mensual: evolución financiera, metas, comparación mes anterior." | `monthly_reviews` table with `(year, month)` unique constraint |
| Daily backup | `0 3 * * *` | "Ejecutá backup diario: empaquetar, checksum SHA-256, encriptar con GPG, rotar." | Timestamp log in `audit_log` |

Timezone: `TZ=America/Argentina/Buenos_Aires` in `.env`. Hermes cron runs in system timezone.

## Code Auditor Subsystem

Separate Hermes profile at `~/.hermes_auditor/`. Key constraints:
- **No Telegram gateway** — invoked only via CLI: `hermes -p auditor chat -q "audit repo X"`
- **Read-only git tokens** in `~/.hermes_auditor/.env` (600)
- **Repo allowlist** at `~/padrino/scripts/config/repo-allowlist.txt`
- **Diff-based incremental**: stores `audit_runs.commit_hash`, computes `git diff {prev}..{current}`, only analyzes changed files
- **Output**: `OpenCode_TASKS.md` per audit in `~/.hermes_auditor/memory/audits/{repo}/{date}/`
- **Never**: commits, pushes, deploys, or modifies audited code. No write path to source repos.

## Backup Architecture

**What**: `padrino.db` (`.dump` SQL), `~/.hermes/memory/` tree, skill files, cron definitions, config (excluding `secrets.env`), audit reports.

**How**: `tar czf {date}.tar.gz {paths}` → `sha256sum` → `gpg --symmetric --batch --passphrase "$PADRINO_BACKUP_KEY"` → `/srv/padrino/data/backups/{date}.tar.gz.gpg`.

**Retention**: Daily × 7, weekly × 4, monthly × 12. Configurable in `~/padrino/scripts/config/retention.conf`.

**Restore**: Verify checksum → `gpg --decrypt` → `tar xzf` → `sqlite3 padrino.db "PRAGMA integrity_check"`.

**Healthcheck**: nightly cron verifies last backup exists, size within 50% of 7-day average, checksum matches.

## Security Model

- **User**: `padrino` (uid≥1000), `/bin/bash`, umask 077, no sudo/wheel, SSH key-only, no password
- **Paths**: Only `~/.hermes/`, `/srv/padrino/`, `/tmp/` accessible; write allowlist enforced in `padrino-security/SKILL.md`
- **Secrets**: `~/.hermes/.env` (600), excluded from backups, never in LLM context, read at invocation-time only
- **Firewall**: UFW allow 22/tcp (SSH), allow {gateway_port}/tcp, deny all inbound
- **Command allowlist**: `~/padrino/scripts/config/command-allowlist.txt` — only `git clone --depth 1`, `sqlite3`, `gpg`, `tar`, `sha256sum`
- **Audit trail**: `audit_log` table records all sensitive actions (timestamp, action, actor, target, result) — append-only

## Deployment Model

```
Windows (dev)                    Debian 12 VPS (prod)
─────────────                    ───────────────────
Write SKILL.md files  ──git push──▶  Clone to ~/.hermes/skills/
Test schema locally   ──scp─────▶  sqlite3 padrino.db < schema.sql
Develop scripts       ──git push──▶  ~/padrino/scripts/
                                       │
                              setup.sh (run ONCE as root):
                                1. useradd padrino + umask 077
                                2. mkdir -p /srv/padrino/data /srv/padrino/backups
                                3. chown -R padrino:padrino /srv/padrino
                                4. curl install Hermes, pip install deps
                                5. systemctl enable hermes-gateway
                                6. ufw enable, allow ports
```

## Data Flow Diagrams

**Message Ingestion**:
```
Telegram → Gateway → Soul (mode+gate) → Inbox (classify)
  → if write: [Approval Gate → User confirms] → DB write → Response
  → if read:  DB query → Response
```

**Daily Planning**:
```
Cron 00:30 ART → padrino-plan: SELECT tasks WHERE status!='done'
  → rank by (due_date, priority, impact, snooze_count, energy)
  → SELECT daily_checkins WHERE date=today (available_hours)
  → if available_hours unknown → provisional plan
  → top 3 tasks, total_estimate ≤ available_hours
  → if estimate > available → overload warning
  → deliver via Telegram
```

**Finance Recording**:
```
User: "Gasté $5000 en verdulería" → Inbox classifies as expense
  → padrino-finance: parse amount, category, date
  → if missing fields → ask user
  → Approval Gate: "¿Registro $5000 en Verdulería/Alimentos?"
  → INSERT into transactions → check budget threshold → warn if applicable
```

**Code Audit**:
```
User: "/auditar nexios-backend"
  → Verify repo in allowlist
  → padrino-audit: git clone --depth 1 (read-only)
  → detect lang (go mod? package.json?) 
  → compute diff from last audit_run.commit_hash
  → analyze changed files only (or full scan if first run)
  → INSERT findings into audit_findings
  → generate OpenCode_TASKS.md
  → report summary via Telegram
```
