---
name: padrino-backup
description: Daily encrypted backups of SQLite database, Markdown memory, configs, skills, cron tasks, and metadata. GPG symmetric encryption with checksum verification and configurable retention.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    role: backup-manager
    tags: [padrino, backup, encryption, gpg, restore, disaster-recovery]
    related_skills: [padrino-security, padrino-hermes]
  deploy:
    data_path: /srv/padrino/backups
    retention_conf: padrino/config/retention.conf
    note: |
      Requires PADRINO_BACKUP_KEY environment variable (GPG passphrase).
      Never log the passphrase. Never include secrets in backups.
---

# padrino-backup — Backup Manager

## Purpose

Perform daily encrypted backups of all Padrino Digital data. Support restore
with integrity verification. Alert on failures and anomalies via Telegram.
Rotate old backups according to retention policy.

## When to Use

- User sends `/backup` to trigger a manual backup
- User sends `/restaurar {date}` to restore from a backup
- Cron job triggers daily backup at 03:00 ART
- Backup failure or anomaly triggers an alert

## Commands

| Command | Action |
|---------|--------|
| `/backup` | Trigger manual backup (requires approval) |
| `/backup status` | Show last backup date, size, status |
| `/restaurar YYYY-MM-DD` | Restore from a specific backup date |
| `/restaurar list` | List available backups |

## Invariants

1. **NEVER include unencrypted secrets** — `.env`, `secrets.env`, tokens excluded
2. **NEVER log the encryption passphrase** — `PADRINO_BACKUP_KEY` stays in env
3. **ALWAYS verify checksum before restore** — abort on mismatch
4. **ALWAYS require user confirmation before restore** — restoring overwrites current data
5. **ALWAYS alert on failure** — Telegram message with error details
6. **ALWAYS alert on size anomaly** — deviation >50% from 7-day average triggers alert

---

## What Gets Backed Up

| Path | Content | Encrypted |
|------|---------|:---------:|
| `/srv/padrino/data/padrino.db` | SQLite database (`.dump` SQL) | ✅ |
| `~/.hermes/memory/` | Markdown memory files | ✅ |
| `padrino/config/*.txt` | Allowlists, retention conf | ✅ |
| `padrino/config/*.service` | Systemd unit | ✅ |
| `padrino/skills/` | All skill files | ✅ |
| `padrino/cron/` | Cron job definitions | ✅ |
| `padrino/reports/` | Audit reports | ✅ |
| `padrino/docs/` | Documentation | ✅ |
| `~/.hermes/config.yaml` | Hermes config | ✅ |

## What Is EXCLUDED

| Path | Reason |
|------|--------|
| `~/.hermes/.env` | Contains API tokens |
| `~/.hermes/secrets.env` | Contains secrets |
| `padrino/config/.env.template` | Template only (redundant) |
| `~/.hermes_auditor/.env` | Auditor read-only tokens |
| `~/.hermes_auditor/repositories/` | Cloned repos (re-clone on restore) |
| `~/.hermes/logs/` | Hermes runtime logs |
| `/srv/padrino/backups/` | Backup archives (don't back up backups) |

---

## Backup Flow

### Step 1 — Create Working Directory

```bash
BACKUP_DATE=$(date '+%Y-%m-%d')
BACKUP_TMP="/tmp/padrino-backup-${BACKUP_DATE}"
rm -rf "$BACKUP_TMP"
mkdir -p "$BACKUP_TMP"
```

### Step 2 — Collect Data

```bash
# SQLite dump
sqlite3 /srv/padrino/data/padrino.db ".dump" > "$BACKUP_TMP/padrino.sql"

# Memory files
cp -r ~/.hermes/memory/ "$BACKUP_TMP/memory/"

# Configs (excluding .env and secrets)
cp padrino/config/command-allowlist.txt "$BACKUP_TMP/config/"
cp padrino/config/repo-allowlist.txt "$BACKUP_TMP/config/"
cp padrino/config/sensitive-paths.txt "$BACKUP_TMP/config/"
cp padrino/config/retention.conf "$BACKUP_TMP/config/" 2>/dev/null || true
cp padrino/config/padrino-gateway.service "$BACKUP_TMP/config/" 2>/dev/null || true

# Skills
cp -r padrino/skills/ "$BACKUP_TMP/skills/"
rm -f "$BACKUP_TMP/skills/.gitkeep"

# Cron
cp -r padrino/cron/ "$BACKUP_TMP/cron/"

# Reports
if [ -d padrino/reports/ ]; then
    cp -r padrino/reports/ "$BACKUP_TMP/reports/"
fi

# Docs
cp -r padrino/docs/ "$BACKUP_TMP/docs/"
rm -f "$BACKUP_TMP/docs/.gitkeep"

# Hermes config
cp ~/.hermes/config.yaml "$BACKUP_TMP/hermes-config.yaml" 2>/dev/null || true
```

### Step 3 — Verify Exclusions

```bash
# Ensure no .env or secrets made it in
if grep -r "HERMES_TELEGRAM_TOKEN\|PADRINO_BACKUP_KEY\|GIT_READONLY_TOKEN" "$BACKUP_TMP/" 2>/dev/null; then
    echo "ERROR: Secret found in backup staging area. Aborting."
    rm -rf "$BACKUP_TMP"
    exit 1
fi
```

### Step 4 — Compress

```bash
tar czf "/tmp/padrino-${BACKUP_DATE}.tar.gz" -C "$BACKUP_TMP" .
```

### Step 5 — Checksum

```bash
sha256sum "/tmp/padrino-${BACKUP_DATE}.tar.gz" > "/tmp/padrino-${BACKUP_DATE}.tar.gz.sha256"
```

### Step 6 — Encrypt

```bash
gpg --symmetric --batch --passphrase "$PADRINO_BACKUP_KEY" \
    --cipher-algo AES256 \
    -o "/srv/padrino/backups/${BACKUP_DATE}.tar.gz.gpg" \
    "/tmp/padrino-${BACKUP_DATE}.tar.gz"
```

### Step 7 — Store Checksum

```bash
cp "/tmp/padrino-${BACKUP_DATE}.tar.gz.sha256" "/srv/padrino/backups/${BACKUP_DATE}.tar.gz.sha256"
```

### Step 8 — Clean Up

```bash
rm -rf "$BACKUP_TMP" "/tmp/padrino-${BACKUP_DATE}.tar.gz" "/tmp/padrino-${BACKUP_DATE}.tar.gz.sha256"
```

### Step 9 — Rotate Old Backups

```bash
# Retention: daily × 7, weekly × 4, monthly × 12 (configurable)
find /srv/padrino/backups/ -name "*.tar.gz.gpg" -mtime +30 -delete
```

### Step 10 — Log

Record to `audit_log`:
```sql
INSERT INTO audit_log (action, actor, target, result, details)
VALUES ('backup', 'padrino', '/srv/padrino/backups/{date}.tar.gz.gpg',
        'success', 'Size: {size}MB, Checksum: {sha256:0:16}');
```

---

## Restore Flow

### Step 1 — List Available Backups (if requested)

```sql
-- Query: extract dates from backup filenames
```

Show formatted list to user with dates and sizes.

### Step 2 — Verify Backup Exists

```bash
BACKUP_FILE="/srv/padrino/backups/${RESTORE_DATE}.tar.gz.gpg"
if [[ ! -f "${BACKUP_FILE}" ]]; then
    echo "No hay backup para la fecha ${RESTORE_DATE}."
    exit 1
fi
```

### Step 3 — Verify Checksum

```bash
# Decrypt to verify
gpg --decrypt --batch --passphrase "$PADRINO_BACKUP_KEY" \
    -o "/tmp/restore-${RESTORE_DATE}.tar.gz" \
    "${BACKUP_FILE}"

# Verify checksum
if ! sha256sum -c "/srv/padrino/backups/${RESTORE_DATE}.tar.gz.sha256" 2>/dev/null; then
    echo "⚠️ Checksum no coincide. El backup puede estar corrupto. No se restauró nada."
    rm -f "/tmp/restore-${RESTORE_DATE}.tar.gz"
    exit 1
fi
```

### Step 4 — Request User Confirmation

```
⚠️ ATENCIÓN: Esto va a SOBRESCRIBIR tu base de datos actual,
archivos de memoria, y configuraciones con los datos del {RESTORE_DATE}.

¿Confirmás la restauración? (sí / no)
```

Wait for explicit confirmation. On "no" or timeout, abort.

### Step 5 — Extract and Restore

```bash
RESTORE_TMP="/tmp/padrino-restore-${RESTORE_DATE}"
mkdir -p "$RESTORE_TMP"
tar xzf "/tmp/restore-${RESTORE_DATE}.tar.gz" -C "$RESTORE_TMP"

# Restore SQLite
sqlite3 /srv/padrino/data/padrino.db < "$RESTORE_TMP/padrino.sql"

# Restore memory
rsync -a "$RESTORE_TMP/memory/" ~/.hermes/memory/

# Restore configs
cp "$RESTORE_TMP/config/"* padrino/config/

# Restore skills
rsync -a "$RESTORE_TMP/skills/" ~/.hermes/skills/

# Restore cron
cp "$RESTORE_TMP/cron/"* padrino/cron/

# Restore hermes config
cp "$RESTORE_TMP/hermes-config.yaml" ~/.hermes/config.yaml 2>/dev/null || true
```

### Step 6 — Verify Integrity

```bash
sqlite3 /srv/padrino/data/padrino.db "PRAGMA integrity_check;"
# Expected: "ok"
```

### Step 7 — Report

```
✅ Restauración completa.
   Backup del {RESTORE_DATE} restaurado exitosamente.
   Base de datos: íntegra.
```

---

## Healthcheck and Monitoring

### Nightly Verification (runs after backup cron)

```bash
# 1. Check last backup exists
LAST_BACKUP=$(ls -t /srv/padrino/backups/*.tar.gz.gpg 2>/dev/null | head -1)

# 2. Check size anomaly
CURRENT_SIZE=$(stat -f%z "$LAST_BACKUP" 2>/dev/null || stat -c%s "$LAST_BACKUP" 2>/dev/null)
AVG_SIZE=$(calculate_7day_average)  # from audit_log or file stats

if (( CURRENT_SIZE < AVG_SIZE / 2 )); then
    ALERT "⚠️ Backup de hoy: $((CURRENT_SIZE/1048576)) MB (promedio 7 días: $((AVG_SIZE/1048576)) MB). ¿Falta algo?"
fi

# 3. Check checksum
sha256sum -c "${LAST_BACKUP%.gpg}.sha256"
```

### Failure Alerting

| Event | Alert | Recovery alert |
|-------|-------|:---:|
| Backup fails (any reason) | `⚠️ Backup diario falló: {reason}` | ✅ |
| Checksum mismatch | `⚠️ Backup {date}: checksum no coincide` | ✅ |
| Size anomaly (>50% deviation) | `⚠️ Backup {date}: tamaño anómalo ({size} vs avg {avg})` | — |
| Restore test fails | `⚠️ Restauración de prueba falló en backup {date}` | ✅ |
| First successful backup after failure | `✅ Backup diario restablecido` | N/A |

---

## Retention Policy

Default (`padrino/config/retention.conf`):
```
# Retention policy for Padrino Digital backups
# Format: <tier> <count>
daily   7
weekly  4
monthly 12
```

Implementation:
- Keep last 7 daily backups
- Keep 1 per week for the last 4 weeks (Sundays)
- Keep 1 per month for the last 12 months (1st of month)
- Delete everything else

---

## Cross-Skill Contract

### Calls (outbound)
- **padrino-security**: Logs backup/restore actions to `audit_log`

### Called by
- **padrino-soul**: Routes `/backup` and `/restaurar` commands here
- **Cron**: Daily backup job at 03:00 ART

### Events
- `backup.started` — backup job began
- `backup.completed` — backup succeeded, includes size and checksum
- `backup.failed` — backup failed, includes error details
- `backup.size_anomaly` — size deviation detected
- `restore.started` — restore job began
- `restore.completed` — restore succeeded
- `restore.failed` — restore failed, includes error details

### Database Tables
- **Writes to**: `audit_log` (via padrino-security)
- **Reads from**: `audit_log` (for backup history and anomaly detection)

---

## Error Handling

| Error | Response |
|-------|----------|
| `PADRINO_BACKUP_KEY` not set | "No puedo hacer el backup sin la clave de encriptación. Configurá PADRINO_BACKUP_KEY en el .env." |
| Disk space < 2x estimated backup size | "Espacio insuficiente. Necesito {need}MB, hay {free}MB libres." |
| GPG not installed | "GPG no está instalado. Instalalo con: sudo apt install gnupg" |
| sqlite3 not found | "SQLite3 no está disponible. Verificá la instalación." |
| Checksum mismatch on restore | "⚠️ Checksum no coincide. El backup puede estar corrupto. No se restauró nada." |
| `PRAGMA integrity_check` fails after restore | "⚠️ La base de datos restaurada no pasó la verificación de integridad." |
| Network error during Telegram alert | Log locally, retry on next cron tick |

---

## Privacy Note

Backups are encrypted with GPG AES-256 using a symmetric passphrase stored in
`PADRINO_BACKUP_KEY`. Without this key, backup archives are unreadable.

**The passphrase is never**: logged, stored in the database, included in LLM
context, sent via Telegram, or included in backup archives.

**If the passphrase is lost, ALL backups become permanently unrecoverable.**
Store it in a password manager and/or a physical backup.
