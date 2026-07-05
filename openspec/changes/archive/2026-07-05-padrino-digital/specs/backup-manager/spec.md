# backup-manager Specification

## Purpose

Perform daily encrypted backups of the SQLite database, Markdown memory files, non-secret configurations, reports, skills, cron tasks, and metadata. Support restore with verification and alert only on failure or anomaly.

## Requirements

### Requirement: Daily Encrypted Backups

The system MUST perform a daily backup of: padrino.db, ~/.hermes/memory/, non-secret config files, skill files, cron definitions, and metadata. The backup SHALL be compressed, checksummed (SHA-256), and encrypted. The backup MUST NOT include unencrypted secrets. The system SHALL enforce configurable retention policies.

#### Scenario: Successful daily backup

- GIVEN all data sources are intact and the backup job triggers
- WHEN the backup runs
- THEN it SHALL create a compressed tar.gz archive of all target paths
- AND SHALL compute and store a SHA-256 checksum
- AND SHALL encrypt the archive with the configured key
- AND SHALL delete archives older than the retention period
- AND SHALL log: "Backup YYYY-MM-DD completed — size: X MB, checksum: abc123"

#### Scenario: Backup excludes unencrypted secrets

- GIVEN a secrets file exists at ~/.hermes/secrets.env with 600 permissions
- WHEN the backup runs
- THEN the secrets file SHALL NOT be included in the backup archive
- AND the backup log SHALL note: "Secrets file excluded (policy)"
- AND the backup SHALL still complete successfully for all other targets

#### Scenario: Backup fails due to disk space

- GIVEN the backup destination has insufficient disk space
- WHEN the backup attempts to write the archive
- THEN it SHALL detect the write failure
- AND SHALL log the error with available vs required space
- AND SHALL send a Telegram alert: "⚠️ Backup falló: espacio insuficiente en disco"
- AND SHALL NOT leave a partial/corrupt archive

### Requirement: Backup Restore with Verification

The restore process MUST verify the backup checksum before extracting, decrypt the archive, restore files to their original paths, and verify the SQLite database integrity after restore. The system SHALL require explicit user confirmation before overwriting any existing data.

#### Scenario: Successful round-trip restore

- GIVEN a valid encrypted backup from 2026-07-04
- WHEN the user requests restore with that backup
- THEN the system SHALL verify the SHA-256 checksum matches
- AND SHALL request confirmation: "Esto va a sobrescribir tu base de datos actual con los datos del 04/07. ¿Confirmás?"
- AND upon confirmation, SHALL decrypt and extract the archive
- AND SHALL run `PRAGMA integrity_check` on the restored padrino.db
- AND SHALL report: "Restauración completa. Base de datos íntegra."

#### Scenario: Checksum mismatch aborts restore

- GIVEN a backup archive whose SHA-256 does not match the stored checksum
- WHEN the user requests restore
- THEN the system SHALL detect the mismatch
- AND SHALL abort the restore immediately
- AND SHALL report: "⚠️ Checksum no coincide. El backup puede estar corrupto. No se restauró nada."
- AND SHALL alert via Telegram

#### Scenario: Restore with confirmation denied

- GIVEN the user requests restore but then denies confirmation
- WHEN the user responds "No, cancelar"
- THEN the system SHALL abort the restore
- AND SHALL NOT modify any files
- AND SHALL log: "Restore cancelled by user"

### Requirement: Failure Alerting

Backup failures or anomalies (size deviation >50% from average, checksum verification failure, restore test failure) MUST trigger a Telegram alert. Successful backups SHALL only be logged, not alerted — unless the previous backup failed, in which case a recovery alert SHALL be sent.

#### Scenario: Backup failure alert

- GIVEN the backup job fails
- WHEN the failure is detected
- THEN a Telegram alert SHALL be sent immediately: "⚠️ Backup diario falló: [reason]"
- AND the alert SHALL include the error details

#### Scenario: Recovery alert after previous failure

- GIVEN yesterday's backup failed and triggered an alert
- WHEN today's backup succeeds
- THEN a recovery alert SHALL be sent: "✅ Backup diario restablecido. Tamaño: X MB."
- AND subsequent successful backups SHALL NOT trigger additional alerts

#### Scenario: Size anomaly alert

- GIVEN the 7-day average backup size is 10 MB
- AND today's backup is 2 MB (80% below average)
- WHEN the anomaly threshold is crossed
- THEN a Telegram alert SHALL be sent: "⚠️ Backup de hoy: 2 MB (promedio 7 días: 10 MB). ¿Falta algo?"
- AND the backup SHALL NOT be deleted despite the anomaly
