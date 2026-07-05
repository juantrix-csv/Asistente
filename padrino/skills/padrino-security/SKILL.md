---
name: padrino-security
description: Security hardening for Padrino Digital — path write enforcement, command allowlist, audit logging, rate limiting, and sensitive operation protection.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    role: security-enforcer
    tags: [padrino, security, hardening, audit-log, allowlist, rate-limiting]
    related_skills: [padrino-soul, padrino-hermes, padrino-backup, padrino-audit]
  deploy:
    allowlist_root: padrino/config/
    note: |
      This skill enforces security policies at the application level.
      OS-level hardening (user, permissions, UFW) is handled by setup.sh.
---

# padrino-security — Security Hardening

## Purpose

Enforce security policies that protect Padrino Digital from unauthorized
file writes, dangerous command execution, and data exposure. Maintain an
append-only audit trail of all sensitive operations.

## When to Use

This skill is loaded automatically on every Padrino Digital session. It
intercepts write operations and command executions BEFORE they happen and
validates them against allowlists. It does NOT respond to user commands
directly — it is a security middleware, not a conversational skill.

---

## Core Policies

### Policy 1 — Path Write Enforcement

**Every file write operation MUST be validated against the path allowlist.**

Before writing to any file, check:
1. Is the target path in the allowlist?
2. Is the operation explicitly allowed (create, modify, append, delete)?
3. Is the path within an allowed root directory?

**Path allowlist** (`padrino/config/sensitive-paths.txt`):

```
# Allowed write paths for Padrino Digital
# Format: <path> <allowed_operations>
# Operations: create, modify, append, delete

/srv/padrino/data/padrino.db            modify
/srv/padrino/data/padrino.db-wal        modify
/srv/padrino/data/padrino.db-shm        modify
/srv/padrino/backups/                   create
/srv/padrino/logs/                       create, append
~/.hermes/memory/                        create, modify, append, delete
~/.hermes/skills/                        create, modify, delete
~/.hermes/config.yaml                    modify
~/.hermes/sessions/                      create, modify, delete
~/.hermes_auditor/reports/               create, modify
padrino/config/                          modify
padrino/cron/                            create, modify, delete
/tmp/padrino-*                           create, modify, delete
```

**Sensitive paths — NEVER write to these:**
```
/etc/
/boot/
/root/
/var/log/  (except /srv/padrino/logs/)
~/.ssh/
~/.hermes/.env
~/.hermes/secrets.env
~/.hermes_auditor/.env
```

**Enforcement logic:**
```
if target_path NOT in allowed_paths:
    log_security_event("WRITE_DENIED", target_path)
    respond: "No tengo permisos para escribir en {target_path}."
    ABORT
```

### Policy 2 — Command Execution Allowlist

**Every shell command execution MUST be validated against the command allowlist.**

Before executing any shell command, check:
1. Is the command (argv[0]) in the allowlist?
2. Do the arguments match the allowed pattern?
3. Is this a read-only operation or a write operation? (write ops need approval gate)

**Command allowlist** (`padrino/config/command-allowlist.txt`):

```
# Format: <command> [allowed_args_pattern]

git clone --depth 1 *
git log *
git diff *
git show *
git status
git fetch *
sqlite3 *
cat *
ls *
stat *
find *
wc *
grep *
tar czf *
tar xzf *
sha256sum *
sha256sum -c *
gpg --symmetric --batch *
gpg --decrypt *
gpg --verify *
date
uptime
free
df
hermes gateway *
hermes -p *
hermes --version
python3 *
```

**Enforcement logic:**
```
if command NOT in allowlist:
    log_security_event("COMMAND_DENIED", command)
    respond: "No tengo autorización para ejecutar '{command}'."
    ABORT
```

### Policy 3 — Audit Trail (Append-Only)

**Every sensitive action MUST be recorded in the `audit_log` table.**

The `audit_log` table is **append-only** — rows are never updated or deleted.

```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'padrino',
    target TEXT,
    result TEXT,
    details TEXT
);
```

**Actions that MUST be logged:**

| Action | Example target | When |
|--------|---------------|------|
| `INSERT transaction` | `transactions(id=42)` | Every finance mutation |
| `UPDATE task` | `tasks(id=7, status=done)` | Task status changes |
| `DELETE` | `memories(id=15)` | Any row deletion |
| `backup` | `/srv/padrino/backups/2026-07-05` | Backup creation |
| `restore` | `/srv/padrino/backups/2026-07-04` | Restore operation |
| `WRITE_DENIED` | `/etc/cron.d/padrino` | Blocked write attempt |
| `COMMAND_DENIED` | `rm -rf /` | Blocked command |
| `RATE_LIMITED` | `transactions.insert` | Rate limit hit |
| `export` | `finance_export.csv` | Data export |
| `APPROVAL_OVERRIDE` | `transactions(id=42)` | Override of approval gate |

**Audit log query examples:**

```sql
-- Last 24h of security events
SELECT * FROM audit_log WHERE timestamp > datetime('now', '-1 day') ORDER BY id DESC;

-- All denied operations this week
SELECT * FROM audit_log WHERE result = 'denied' AND timestamp > datetime('now', '-7 days');

-- Backup history
SELECT timestamp, target, details FROM audit_log WHERE action = 'backup' ORDER BY id DESC LIMIT 10;
```

**Never log**: API keys, tokens, passwords, PADRINO_BACKUP_KEY, or full `.env` contents. Redact secrets in `details` with `[REDACTED]`.

### Policy 4 — Rate Limiting

**Rate-limit sensitive operations to prevent abuse or accidents.**

| Operation | Max frequency | Window |
|-----------|:------------:|--------|
| Transaction insert | 30 | per hour |
| Task creation | 20 | per hour |
| Backup | 1 | per hour |
| Restore | 1 | per day |
| Export | 5 | per day |
| Audit request | 10 | per day |

**Enforcement logic:**
```
count = SELECT COUNT(*) FROM audit_log
        WHERE action = :action AND timestamp > datetime('now', :window)

if count >= :max:
    log_security_event("RATE_LIMITED", action)
    respond: "Operación limitada. Ya hiciste {count} {action} en {window}. Esperá un rato."
    ABORT
```

### Policy 5 — Sensitive Operation Approval Gates

**Operations that modify data, execute commands, or expose information MUST pass through an approval gate.**

| Operation | Gate type | Message |
|-----------|-----------|---------|
| Write to DB | `approval_required` | "¿Confirmás {operation}?" |
| Execute command | `approval_required` | "Voy a ejecutar: `{command}`. ¿Autorizás?" |
| Export data | `approval_required` | "Voy a exportar {data_type}. ¿Confirmás?" |
| Restore backup | `approval_required` | "⚠️ Esto SOBRESCRIBE tus datos actuales. ¿Confirmás?" |
| Delete data | `approval_required` | "¿Confirmás que querés eliminar {item}?" |

**Reads (SELECT, FTS5 search, file reads) skip gates.**

### Policy 6 — Sensitive Path Blocking

**Padrino Digital MUST refuse to read from or write to blocked paths.**

Blocked paths:
- `~/.ssh/` — SSH keys
- `~/.gnupg/` — GPG private keys
- `/etc/shadow` — Password hashes
- `~/.hermes/.env` — API tokens (read at invocation time only, never exposed)
- `~/.hermes/secrets.env` — Secrets file
- Any path containing `.env` with API keys in it

If a skill or user request tries to access any of these:
```
log_security_event("PATH_BLOCKED", path)
respond: "No tengo acceso a {path} — y no debería tenerlo."
ABORT
```

---

## Security Event Categories

| Category | Severity | Response |
|----------|----------|----------|
| `WRITE_DENIED` | HIGH | Log + alert if repeated |
| `COMMAND_DENIED` | HIGH | Log + alert if repeated |
| `PATH_BLOCKED` | MEDIUM | Log |
| `RATE_LIMITED` | LOW | Log + inform user |
| `SECRETS_SCAN` | CRITICAL | Log + immediate alert |
| `APPROVAL_BYPASS_ATTEMPT` | CRITICAL | Log + immediate alert |

**Immediate alerts** are sent via Telegram to the user. **Log-only** events
are recorded in `audit_log` and reviewed during weekly security summaries.

---

## Security Audit Review

### Daily (automated, part of healthcheck)

- Check `audit_log` for DENIED events in the last 24h
- If >3 denied events → alert: "⚠️ {n} intentos de acceso bloqueados hoy."
- Verify `.env` file permissions are 600
- Verify backup was created and checksum matches

### Weekly (part of weekly review)

- Summarize all security events for the week
- Check for patterns: repeated denied attempts from the same source
- Verify allowlists haven't been modified unexpectedly
- Check `audit_log` row count (should only grow, never shrink)

---

## Cross-Skill Contract

### Called by (interception layer)
- **padrino-soul**: Before executing any write or command
- **padrino-finance**: Before inserting/updating transactions
- **padrino-tasks**: Before modifying task state
- **padrino-backup**: Before backup/restore operations
- **padrino-audit**: Before cloning repos (allowlist check)

### Events
- `security.policy_violation` — blocked operation attempt
- `security.rate_limited` — rate limit triggered
- `security.audit_anomaly` — unexpected pattern in audit log

### Database Tables
- **Writes to**: `audit_log` (append-only)
- **Reads from**: `audit_log` (for rate limiting and anomaly detection)

---

## Setup Verification

After deployment, verify security hardening:

```bash
# 1. Verify padrino user exists and has no sudo
id padrino
sudo -l -U padrino  # Should say "not allowed"

# 2. Verify umask
sudo -u padrino umask  # Should output: 0077

# 3. Verify .env permissions
stat -c '%a %n' ~/.hermes/.env  # Should output: 600

# 4. Verify UFW is active
sudo ufw status  # Should show "active" with only 22 and gateway port allowed

# 5. Verify command allowlist exists
cat padrino/config/command-allowlist.txt

# 6. Verify sensitive paths config exists
cat padrino/config/sensitive-paths.txt

# 7. Verify audit_log table exists and is append-only
sqlite3 /srv/padrino/data/padrino.db "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log';"
```

---

## Privacy Note

Padrino Digital security policies are designed to protect YOUR data. All
security events are logged locally — nothing is sent to external services.
The `audit_log` is included in encrypted backups but never exported or shared.

If you suspect a security incident, review the audit log immediately:
```sql
SELECT * FROM audit_log WHERE result = 'denied' ORDER BY id DESC;
```
