# Backup & Restore — Padrino Digital

Estrategia de backup: qué se respalda, cómo se encripta, retención,
restauración, y verificación.

## Estrategia

- **Frecuencia**: Diaria (cron a las 03:00 ART)
- **Encriptación**: GPG simétrico AES-256
- **Checksum**: SHA-256 por archivo
- **Retención**: 7 días (configurable)
- **Alerta**: Solo en fallo o anomalía (Telegram)

## Qué se Respaldó

| Dato | Ubicación | Formato en backup |
|------|-----------|-------------------|
| Base de datos | `/srv/padrino/data/padrino.db` | `.dump` SQL |
| Memoria Markdown | `~/.hermes/memory/` | Archivos `.md` |
| Skills | `~/.hermes/skills/padrino-*/` | `SKILL.md` |
| Configs | `padrino/config/*.txt`, `*.service` | Original |
| Cron jobs | `padrino/cron/padrino-crons.txt` | Original |
| Docs | `padrino/docs/` | Original |
| Reportes | `padrino/reports/` | Original |

## Qué NO se Respaldó

| Dato | Razón |
|------|-------|
| `~/.hermes/.env` | Contiene tokens — se restaura manualmente |
| `~/.hermes/secrets.env` | Contiene `PADRINO_BACKUP_KEY` |
| `~/.hermes_auditor/.env` | Tokens read-only del auditor |
| `~/.hermes_auditor/repositories/` | Se re-clonan en restore |
| `~/.hermes/logs/` | Logs de runtime (no críticos) |
| `/srv/padrino/backups/` | No backupear backups |

## Proceso de Backup

```bash
# Manual
bash padrino/scripts/backup.sh

# Automático (cron)
0 3 * * * /srv/padrino/scripts/backup.sh
```

### Pasos internos

1. Crear directorio temporal `/tmp/padrino-backup-YYYY-MM-DD`
2. Dumpear SQLite: `sqlite3 padrino.db ".dump" > padrino.sql`
3. Copiar memory, skills, configs, cron, docs
4. Verificar que NO haya secrets en el staging (grep de tokens)
5. Comprimir: `tar czf backup.tar.gz`
6. Checksum: `sha256sum backup.tar.gz > backup.tar.gz.sha256`
7. Encriptar: `gpg --symmetric --cipher-algo AES256`
8. Guardar en `/srv/padrino/backups/YYYY-MM-DD.tar.gz.gpg`
9. Rotar backups viejos (>30 días)
10. Verificar anomalía de tamaño (vs promedio 7 días)

## Restauración

```bash
# Listar backups disponibles
bash padrino/scripts/restore.sh --list

# Restaurar desde fecha específica
bash padrino/scripts/restore.sh 2026-07-04

# Restaurar desde el más reciente
bash padrino/scripts/restore.sh --latest
```

### Pasos internos

1. Verificar que el archivo `.tar.gz.gpg` existe para la fecha
2. Desencriptar: `gpg --decrypt`
3. Verificar SHA-256 checksum → **ABORTAR si no coincide**
4. Pedir confirmación: "¿Confirmás restaurar desde {fecha}? (SI-RESTAURAR)"
5. Extraer `tar xzf`
6. Restaurar SQLite: `sqlite3 padrino.db < padrino.sql`
7. Restaurar memory, skills, configs, cron
8. Verificar integridad: `PRAGMA integrity_check` → debe decir "ok"
9. Reportar resultado

## Encriptación

- **Algoritmo**: AES-256 (GPG symmetric)
- **Clave**: `PADRINO_BACKUP_KEY` (frase secreta en `~/.hermes/secrets.env`)
- **Sin clave**: los backups son ilegibles (sin excepción)

### Guardar la clave de backup

⚠️ **CRÍTICO**: Si perdés `PADRINO_BACKUP_KEY`, perdés TODOS los backups.

Guardala en:
- Un password manager (Bitwarden, 1Password)
- Un lugar físico seguro (papel en caja fuerte)
- NO solo en el VPS (si el VPS muere, perdés la clave y los backups)

## Verificación de Salud

El healthcheck del backup verifica:

1. ¿Existe el último backup? (`ls -t /srv/padrino/backups/*.tar.gz.gpg | head -1`)
2. ¿Tamaño dentro del rango normal? (comparado con promedio 7 días)
3. ¿Checksum coincide? (`sha256sum -c`)

### Anomalías que disparan alerta

| Anomalía | Alerta |
|----------|--------|
| Backup falla | `⚠️ Backup diario falló: {razón}` |
| Tamaño < 50% del promedio | `⚠️ Backup anómalo: {size}MB vs {avg}MB` |
| Checksum no coincide | `⚠️ Checksum inválido en backup {fecha}` |
| Primer éxito después de fallo | `✅ Backup restablecido` |

## Retención

Default: 30 días. Configurable en `padrino/config/retention.conf`:

```
daily   7      # Últimos 7 días
weekly  4      # 1 por semana (domingos), 4 semanas
monthly 12     # 1 por mes (día 1), 12 meses
```

## Prueba de Restauración

Para probar que los backups funcionan sin afectar datos reales:

```bash
# 1. Crear un backup de prueba
PADRINO_BACKUP_KEY=test-key bash padrino/scripts/backup.sh

# 2. Restaurar en una ubicación temporal
# (modificar restore.sh para usar un DB temporal)

# 3. Verificar integridad
sqlite3 /tmp/test-restore.db "PRAGMA integrity_check;"
```

## Troubleshooting

| Problema | Causa probable | Solución |
|----------|---------------|----------|
| "PADRINO_BACKUP_KEY no definida" | Falta la variable | Agregar a `~/.hermes/secrets.env` |
| "Espacio insuficiente" | Disco lleno | Liberar espacio o reducir retención |
| "Checksum no coincide" | Backup corrupto | Usar un backup anterior |
| "GPG no instalado" | Falta dependencia | `sudo apt install gnupg` |
| Backup tarda mucho | DB muy grande | Considerar `VACUUM` periódico |
