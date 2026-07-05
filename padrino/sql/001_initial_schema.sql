-- =============================================================================
-- Padrino Digital — Initial Database Schema
-- Version: 001
-- Database: /srv/padrino/data/padrino.db
-- SQLite 3.35+ required (for DROP COLUMN, RETURNING, STRICT tables)
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

-- ---------------------------------------------------------------------------
-- Schema version tracking
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    description TEXT,
    checksum    TEXT
);

INSERT OR IGNORE INTO schema_version (version, description) VALUES (1, 'Initial schema — all core tables');

-- ===========================================================================
-- CORE ENTITIES
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- tasks — Universal task management with full lifecycle
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT    NOT NULL,
    description       TEXT,
    status            TEXT    NOT NULL DEFAULT 'inbox'
        CHECK (status IN ('inbox','todo','scheduled','in_progress','blocked','waiting','done','cancelled')),
    priority          INTEGER NOT NULL DEFAULT 0
        CHECK (priority BETWEEN 0 AND 5),
    project_id        INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    goal_id           INTEGER REFERENCES goals(id) ON DELETE SET NULL,
    due_at            TEXT,
    scheduled_at      TEXT,
    completed_at      TEXT,
    estimated_minutes INTEGER,
    actual_minutes    INTEGER,
    snooze_count      INTEGER NOT NULL DEFAULT 0,
    last_snoozed_at   TEXT,
    source            TEXT,
    tags              TEXT,          -- JSON array stored as text: '["tag1","tag2"]'
    blocked_by        TEXT,          -- Comma-separated task IDs or description
    energy_required   TEXT CHECK (energy_required IN ('high','medium','low','any')),
    archived_at       TEXT,
    deleted_at        TEXT,          -- Soft delete
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_status      ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_project     ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_due         ON tasks(due_at);
CREATE INDEX IF NOT EXISTS idx_tasks_scheduled   ON tasks(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_tasks_priority    ON tasks(priority DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_deleted     ON tasks(deleted_at);
CREATE INDEX IF NOT EXISTS idx_tasks_goal        ON tasks(goal_id);

-- ---------------------------------------------------------------------------
-- projects — Group tasks and goals under projects
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT    NOT NULL UNIQUE,
    description       TEXT,
    status            TEXT    NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','paused','completed','archived')),
    area              TEXT,
    review_frequency  TEXT    DEFAULT 'weekly'
        CHECK (review_frequency IN ('daily','weekly','biweekly','monthly','quarterly','none')),
    last_reviewed_at  TEXT,
    archived_at       TEXT,
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_area   ON projects(area);
CREATE INDEX IF NOT EXISTS idx_projects_deleted ON projects(deleted_at);

-- ---------------------------------------------------------------------------
-- goals — Trackable goals with progress measurement
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS goals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    description       TEXT    NOT NULL,
    project_id        INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    target_value      REAL,
    current_value     REAL    NOT NULL DEFAULT 0,
    measurement_unit  TEXT,          -- e.g., 'ARS', 'USD', 'kg', 'pages', 'hours'
    deadline          TEXT,
    status            TEXT    NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','paused','completed','abandoned')),
    priority          INTEGER NOT NULL DEFAULT 0
        CHECK (priority BETWEEN 0 AND 5),
    notes             TEXT,
    completed_at      TEXT,
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_goals_project  ON goals(project_id);
CREATE INDEX IF NOT EXISTS idx_goals_status   ON goals(status);
CREATE INDEX IF NOT EXISTS idx_goals_deadline ON goals(deadline);
CREATE INDEX IF NOT EXISTS idx_goals_deleted  ON goals(deleted_at);

-- ---------------------------------------------------------------------------
-- habits — Recurring habit definitions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS habits (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT    NOT NULL UNIQUE,
    description       TEXT,
    frequency         TEXT    NOT NULL
        CHECK (frequency IN ('daily','weekly','monthly')),
    expected_count    INTEGER NOT NULL DEFAULT 1,   -- e.g., 3 times per week
    minimum_count     INTEGER,                      -- Minimum acceptable (for accountability)
    unit              TEXT,                          -- e.g., 'minutes', 'reps', 'km'
    area              TEXT,
    archived_at       TEXT,
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_habits_frequency ON habits(frequency);
CREATE INDEX IF NOT EXISTS idx_habits_area      ON habits(area);
CREATE INDEX IF NOT EXISTS idx_habits_deleted   ON habits(deleted_at);

-- ---------------------------------------------------------------------------
-- habit_entries — Daily/weekly habit completion records
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS habit_entries (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id          INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    date              TEXT    NOT NULL,      -- YYYY-MM-DD
    completed         INTEGER NOT NULL DEFAULT 0,
    value             REAL,                   -- For measured habits (e.g., 30 minutes)
    notes             TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(habit_id, date)
);

CREATE INDEX IF NOT EXISTS idx_habit_entries_date   ON habit_entries(date);
CREATE INDEX IF NOT EXISTS idx_habit_entries_habit  ON habit_entries(habit_id);

-- ===========================================================================
-- FINANCE TABLES
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- transactions — All financial movements
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    type              TEXT    NOT NULL
        CHECK (type IN ('income','expense','transfer','adjustment')),
    amount            REAL    NOT NULL,
    currency          TEXT    NOT NULL DEFAULT 'ARS',
    category          TEXT,
    account           TEXT,
    business_area     TEXT
        CHECK (business_area IN ('personal','Ascend','fletes','Nexios','Rastrojero','home-gym','otros')),
    payment_method    TEXT,
    date              TEXT    NOT NULL,      -- YYYY-MM-DD
    description       TEXT,
    recurring         INTEGER NOT NULL DEFAULT 0,
    correction_id     INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
    original_currency TEXT,
    original_amount   REAL,
    conversion_rate   REAL,
    conversion_source TEXT,
    conversion_date   TEXT,
    approved_by       TEXT    DEFAULT 'pending',   -- 'pending', 'user', 'auto'
    approved_at       TEXT,
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_date      ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category  ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_correction ON transactions(correction_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type      ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_transactions_area      ON transactions(business_area);
CREATE INDEX IF NOT EXISTS idx_transactions_deleted   ON transactions(deleted_at);

-- ---------------------------------------------------------------------------
-- budgets — Category-based spending limits
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS budgets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    category          TEXT    NOT NULL,
    period            TEXT    NOT NULL
        CHECK (period IN ('monthly','weekly','annual')),
    limit_amount      REAL    NOT NULL,
    currency          TEXT    NOT NULL DEFAULT 'ARS',
    warning_percent   REAL    NOT NULL DEFAULT 80,
    business_area     TEXT
        CHECK (business_area IN ('personal','Ascend','fletes','Nexios','Rastrojero','home-gym','otros')),
    active            INTEGER NOT NULL DEFAULT 1,
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_budgets_category ON budgets(category, period);
CREATE INDEX IF NOT EXISTS idx_budgets_deleted  ON budgets(deleted_at);

-- ---------------------------------------------------------------------------
-- savings_goals — Named savings targets
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS savings_goals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT    NOT NULL,
    description       TEXT,
    target_amount     REAL    NOT NULL,
    current_amount    REAL    NOT NULL DEFAULT 0,
    currency          TEXT    NOT NULL DEFAULT 'ARS',
    deadline          TEXT,
    status            TEXT    NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','completed','paused','abandoned')),
    monthly_contribution REAL,
    notes             TEXT,
    completed_at      TEXT,
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_savings_goals_status   ON savings_goals(status);
CREATE INDEX IF NOT EXISTS idx_savings_goals_deadline ON savings_goals(deadline);
CREATE INDEX IF NOT EXISTS idx_savings_goals_deleted  ON savings_goals(deleted_at);

-- ---------------------------------------------------------------------------
-- debts — Tracked liabilities
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS debts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT    NOT NULL,
    description       TEXT,
    total_amount      REAL    NOT NULL,
    remaining_amount  REAL    NOT NULL,
    currency          TEXT    NOT NULL DEFAULT 'ARS',
    creditor          TEXT,
    interest_rate     REAL,
    interest_type     TEXT    DEFAULT 'annual'
        CHECK (interest_type IN ('annual','monthly','fixed')),
    due_date          TEXT,
    status            TEXT    NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','paid','defaulted','negotiating')),
    category          TEXT,
    notes             TEXT,
    paid_at           TEXT,
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_debts_status  ON debts(status);
CREATE INDEX IF NOT EXISTS idx_debts_due     ON debts(due_date);
CREATE INDEX IF NOT EXISTS idx_debts_deleted ON debts(deleted_at);

-- ===========================================================================
-- MEMORY / KNOWLEDGE TABLES
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- memories — Personal knowledge base with provenance metadata
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memories (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    content           TEXT    NOT NULL,
    source            TEXT    NOT NULL
        CHECK (source IN ('user_statement','observation','inference','import')),
    confidence        TEXT    NOT NULL
        CHECK (confidence IN ('confirmed','high','medium','low','speculative')),
    type              TEXT    NOT NULL
        CHECK (type IN ('fact','preference','decision','hypothesis','temporal_info','replaced')),
    area              TEXT,
    project           TEXT,
    tags              TEXT,                   -- JSON array as text
    event_date        TEXT,                   -- When the remembered event occurred (YYYY-MM-DD)
    validity_until    TEXT,                   -- Expiration (YYYY-MM-DD or 'permanent')
    superseded_by     INTEGER REFERENCES memories(id) ON DELETE SET NULL,
    source_message    TEXT,                   -- Original message text (for audit)
    relations         TEXT,                   -- JSON: [{"type":"relates_to","id":123},...]
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_memories_area      ON memories(area);
CREATE INDEX IF NOT EXISTS idx_memories_project   ON memories(project);
CREATE INDEX IF NOT EXISTS idx_memories_type      ON memories(type);
CREATE INDEX IF NOT EXISTS idx_memories_confidence ON memories(confidence);
CREATE INDEX IF NOT EXISTS idx_memories_validity  ON memories(validity_until);
CREATE INDEX IF NOT EXISTS idx_memories_deleted   ON memories(deleted_at);

-- FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    area,
    project,
    source,
    tags,
    content = 'memories',
    content_rowid = 'id'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, area, project, source, tags)
    VALUES (new.id, new.content, new.area, new.project, new.source, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, area, project, source, tags)
    VALUES ('delete', old.id, old.content, old.area, old.project, old.source, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, area, project, source, tags)
    VALUES ('delete', old.id, old.content, old.area, old.project, old.source, old.tags);
    INSERT INTO memories_fts(rowid, content, area, project, source, tags)
    VALUES (new.id, new.content, new.area, new.project, new.source, new.tags);
END;

-- ---------------------------------------------------------------------------
-- decisions — Tracked decisions with context and rationale
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decisions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT    NOT NULL,
    context           TEXT,
    options           TEXT,           -- JSON: [{"option":"A","pros":[],"cons":[]},...]
    chosen            TEXT,
    rationale         TEXT,
    status            TEXT    NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','revised','reversed','archived')),
    impact_area       TEXT,
    decided_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    revised_at        TEXT,
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_area   ON decisions(impact_area);
CREATE INDEX IF NOT EXISTS idx_decisions_deleted ON decisions(deleted_at);

-- ===========================================================================
-- PLANNING & REVIEW TABLES
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- daily_checkins — Morning/evening check-in records
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_checkins (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                TEXT    NOT NULL UNIQUE,     -- YYYY-MM-DD
    available_hours     REAL,
    energy_level        TEXT    CHECK (energy_level IN ('high','medium','low')),
    minimum_mode        INTEGER NOT NULL DEFAULT 0,
    morning_delivered   INTEGER NOT NULL DEFAULT 0,
    evening_delivered   INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    completed_tasks     INTEGER DEFAULT 0,
    pending_tasks       INTEGER DEFAULT 0,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_checkins_date ON daily_checkins(date);

-- ---------------------------------------------------------------------------
-- reminders — Scheduled notifications
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reminders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT    NOT NULL,
    description       TEXT,
    remind_at         TEXT    NOT NULL,
    recurrence        TEXT,          -- 'daily','weekly','monthly','custom:cron_expr'
    delivered         INTEGER NOT NULL DEFAULT 0,
    delivered_at      TEXT,
    task_id           INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    snoozed_until     TEXT,
    deleted_at        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reminders_deliver ON reminders(remind_at, delivered);
CREATE INDEX IF NOT EXISTS idx_reminders_task    ON reminders(task_id);
CREATE INDEX IF NOT EXISTS idx_reminders_deleted ON reminders(deleted_at);

-- ===========================================================================
-- AUDIT TABLES
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- audit_runs — Code audit execution records
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_url          TEXT    NOT NULL,
    commit_hash       TEXT,
    previous_commit   TEXT,
    language          TEXT,
    framework         TEXT,
    findings_count    INTEGER NOT NULL DEFAULT 0,
    status            TEXT    NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','completed','failed')),
    error_message     TEXT,
    started_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_runs_repo   ON audit_runs(repo_url);
CREATE INDEX IF NOT EXISTS idx_audit_runs_status ON audit_runs(status);

-- ---------------------------------------------------------------------------
-- audit_findings — Individual findings from a code audit
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_findings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_run_id        INTEGER NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
    severity            TEXT    NOT NULL
        CHECK (severity IN ('critical','high','medium','low','info')),
    confidence          INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    category            TEXT    NOT NULL,
    summary             TEXT    NOT NULL,
    evidence            TEXT,
    impact              TEXT,
    reproduction        TEXT,
    file_path           TEXT,
    line_number         INTEGER,
    acceptance_criteria TEXT,
    required_tests      TEXT,
    restrictions        TEXT,
    possible_false_positive INTEGER NOT NULL DEFAULT 0,
    status              TEXT    NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','acknowledged','fixed','false_positive','wont_fix')),
    resolved_at         TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_findings_run      ON audit_findings(audit_run_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_severity ON audit_findings(severity);
CREATE INDEX IF NOT EXISTS idx_audit_findings_status   ON audit_findings(status);

-- ---------------------------------------------------------------------------
-- audit_log — Security audit trail (append-only)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL DEFAULT (datetime('now')),
    action            TEXT    NOT NULL,
    actor             TEXT    NOT NULL DEFAULT 'padrino',
    target            TEXT,
    result            TEXT,
    details           TEXT,
    ip_address        TEXT,
    session_id        TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_action    ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor     ON audit_log(actor);

-- ===========================================================================
-- TRIGGERS — Auto-update updated_at on all eligible tables
-- ===========================================================================

-- Helper: create a trigger if it doesn't exist
-- SQLite doesn't support CREATE OR REPLACE TRIGGER, so we drop first

-- tasks
DROP TRIGGER IF EXISTS trg_tasks_updated;
CREATE TRIGGER trg_tasks_updated AFTER UPDATE ON tasks
BEGIN
    UPDATE tasks SET updated_at = datetime('now') WHERE id = NEW.id AND updated_at = OLD.updated_at;
END;

-- projects
DROP TRIGGER IF EXISTS trg_projects_updated;
CREATE TRIGGER trg_projects_updated AFTER UPDATE ON projects
BEGIN
    UPDATE projects SET updated_at = datetime('now') WHERE id = NEW.id AND updated_at = OLD.updated_at;
END;

-- goals
DROP TRIGGER IF EXISTS trg_goals_updated;
CREATE TRIGGER trg_goals_updated AFTER UPDATE ON goals
BEGIN
    UPDATE goals SET updated_at = datetime('now') WHERE id = NEW.id AND updated_at = OLD.updated_at;
END;

-- transactions
DROP TRIGGER IF EXISTS trg_transactions_updated;
CREATE TRIGGER trg_transactions_updated AFTER UPDATE ON transactions
BEGIN
    UPDATE transactions SET updated_at = datetime('now') WHERE id = NEW.id AND updated_at = OLD.updated_at;
END;

-- budgets
DROP TRIGGER IF EXISTS trg_budgets_updated;
CREATE TRIGGER trg_budgets_updated AFTER UPDATE ON budgets
BEGIN
    UPDATE budgets SET updated_at = datetime('now') WHERE id = NEW.id AND updated_at = OLD.updated_at;
END;

-- savings_goals
DROP TRIGGER IF EXISTS trg_savings_goals_updated;
CREATE TRIGGER trg_savings_goals_updated AFTER UPDATE ON savings_goals
BEGIN
    UPDATE savings_goals SET updated_at = datetime('now') WHERE id = NEW.id AND updated_at = OLD.updated_at;
END;

-- debts
DROP TRIGGER IF EXISTS trg_debts_updated;
CREATE TRIGGER trg_debts_updated AFTER UPDATE ON debts
BEGIN
    UPDATE debts SET updated_at = datetime('now') WHERE id = NEW.id AND updated_at = OLD.updated_at;
END;

-- decisions
DROP TRIGGER IF EXISTS trg_decisions_updated;
CREATE TRIGGER trg_decisions_updated AFTER UPDATE ON decisions
BEGIN
    UPDATE decisions SET updated_at = datetime('now') WHERE id = NEW.id AND updated_at = OLD.updated_at;
END;

-- ===========================================================================
-- AUDIT LOG TRIGGERS — Automatically log sensitive mutations
-- ===========================================================================

-- Log INSERTs on transactions table
DROP TRIGGER IF EXISTS trg_audit_transactions_insert;
CREATE TRIGGER trg_audit_transactions_insert AFTER INSERT ON transactions
BEGIN
    INSERT INTO audit_log (action, target, result, details)
    VALUES (
        'INSERT',
        'transactions',
        'success',
        json_object(
            'transaction_id', NEW.id,
            'type', NEW.type,
            'amount', NEW.amount,
            'currency', NEW.currency,
            'category', NEW.category,
            'date', NEW.date
        )
    );
END;

-- Log UPDATEs on transactions table (corrections)
DROP TRIGGER IF EXISTS trg_audit_transactions_update;
CREATE TRIGGER trg_audit_transactions_update AFTER UPDATE ON transactions
BEGIN
    INSERT INTO audit_log (action, target, result, details)
    VALUES (
        'UPDATE',
        'transactions',
        'success',
        json_object(
            'transaction_id', NEW.id,
            'old_amount', OLD.amount,
            'new_amount', NEW.amount,
            'old_category', OLD.category,
            'new_category', NEW.category
        )
    );
END;
