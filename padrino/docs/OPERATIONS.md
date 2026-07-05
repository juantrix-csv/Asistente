# Operaciones — Padrino Digital

Guía de operaciones día a día: scripts, cron, healthcheck, y mantenimiento.

## Scripts Disponibles

Todos en `padrino/scripts/`:

| Script | Uso | Requiere root? |
|--------|-----|:---:|
| `setup.sh` | Instalación inicial del sistema | ✅ |
| `start.sh` | Iniciar Hermes Gateway | ❌ |
| `stop.sh` | Detener Hermes Gateway | ❌ |
| `restart.sh` | Reiniciar Hermes Gateway | ❌ |
| `status.sh` | Estado del Hermes Gateway | ❌ |
| `healthcheck.sh` | Verificación completa de salud | ❌ |
| `backup.sh` | Backup encriptado | ❌ |
| `restore.sh` | Restaurar desde backup | ❌ |
| `export.sh` | Exportar datos (CSV/JSON/MD) | ❌ |
| `migrate.sh` | Aplicar migraciones de DB | ❌ |
| `test.sh` | Suite de tests de integración | ❌ |
| `audit-repo.sh` | Auditar repositorio de código | ❌ |
| `security-audit.sh` | Auditoría de seguridad del sistema | ❌ |

Todos los scripts usan `set -Eeuo pipefail` y validan entradas.

## Comandos Diarios

```bash
# Verificar que el gateway está corriendo
sudo -u padrino bash padrino/scripts/status.sh

# Healthcheck rápido
sudo -u padrino bash padrino/scripts/healthcheck.sh

# Backup manual (el automático corre a las 03:00 ART)
sudo -u padrino bash padrino/scripts/backup.sh
```

## Cron Jobs

Instalados en el crontab del usuario `padrino`:

```bash
# Ver cron jobs instalados
crontab -u padrino -l

# Reinstalar después de cambios
crontab -u padrino padrino/cron/padrino-crons.txt
```

| Hora (ART) | Job | Propósito |
|:----------:|-----|-----------|
| 08:00 | padrino-morning | Resumen matutino — prioridades, compromisos |
| 21:30 | padrino-evening | Revisión nocturna — completadas, pendientes, gastos |
| Dom 19:00 | padrino-weekly | Revisión semanal completa |
| Día 1 10:00 | padrino-monthly | Revisión mensual — financiera, metas, tendencias |
| 03:00 | backup.sh | Backup encriptado diario |

### Logs de Cron

```bash
# Logs generales de cron
sudo grep CRON /var/log/syslog | tail -20

# Logs específicos de Padrino
tail -f /srv/padrino/logs/backup.log
tail -f /srv/padrino/logs/restore.log
```

## Healthcheck

```bash
sudo -u padrino bash padrino/scripts/healthcheck.sh
```

Verifica:
1. **Gateway process**: ¿systemd dice que está active?
2. **Telegram connectivity**: ¿el bot responde a getMe?
3. **Disk space**: ¿hay espacio suficiente?
4. **Data directories**: ¿accesibles y escribibles?

Salida esperada (todo verde):
```
[1/4] Hermes Gateway Process
  ✓ PASS — hermes-gateway is active

[2/4] Telegram Connectivity
  ✓ PASS — Bot @PadrinoDigitalBot is reachable

[3/4] Disk Space
  ✓ PASS — 15.2GB free (85%)

[4/4] Data Directories
  ✓ PASS — /srv/padrino/data is writable
  ✓ PASS — /srv/padrino/backups is writable
```

## Mantenimiento Periódico

### Semanal

```bash
# Verificar logs de seguridad
sudo -u padrino sqlite3 /srv/padrino/data/padrino.db \
  "SELECT * FROM audit_log WHERE result='denied' AND timestamp > datetime('now','-7 days');"

# Verificar backups
ls -lh /srv/padrino/backups/ | tail -7

# Verificar espacio en disco
df -h /srv/padrino/
```

### Mensual

```bash
# Vacuum database (reclama espacio)
sudo -u padrino sqlite3 /srv/padrino/data/padrino.db "VACUUM;"

# Rotar logs viejos
find /srv/padrino/logs/ -name "*.log" -mtime +90 -delete

# Verificar integridad de la DB
sudo -u padrino sqlite3 /srv/padrino/data/padrino.db "PRAGMA integrity_check;"

# Actualizar el sistema
sudo apt update && sudo apt upgrade -y
sudo systemctl restart hermes-gateway
```

### Ante una caída

```bash
# 1. Ver qué pasó
sudo journalctl -u hermes-gateway -n 50 --no-pager
tail -100 ~/.hermes/logs/hermes.log

# 2. Reiniciar
sudo -u padrino bash padrino/scripts/restart.sh

# 3. Verificar
sudo -u padrino bash padrino/scripts/healthcheck.sh

# 4. Si no revive, verificar:
#    - ¿Token de Telegram sigue válido?
#    - ¿Puerto 8443 está abierto? (sudo ufw status)
#    - ¿Disco lleno? (df -h)
#    - ¿Proceso zombie? (ps aux | grep hermes)
```

## Monitoreo

### Logs importantes

```bash
# Gateway
tail -f ~/.hermes/logs/hermes.log

# Systemd
sudo journalctl -u hermes-gateway -f

# Backup
tail -f /srv/padrino/logs/backup.log

# Auditoría de código
tail -f ~/.hermes_auditor/logs/audit-repo.log
```

### Métricas clave (vía Telegram)

Preguntale a Padrino:
- `/status` — Estado general
- `/backup status` — Último backup
- `/finanzas` — Resumen del mes

## Actualización de Skills

Cuando edites un SKILL.md:

```bash
# 1. Editar el archivo
nano ~/.hermes/skills/padrino-plan/SKILL.md

# 2. Reiniciar el gateway para que recargue
sudo -u padrino bash padrino/scripts/restart.sh

# 3. Verificar que cargó sin errores
sudo journalctl -u hermes-gateway -n 10 --no-pager
```

## Migraciones de Base de Datos

```bash
# 1. Hacer backup antes de migrar
sudo -u padrino bash padrino/scripts/backup.sh

# 2. Aplicar migración
sudo -u padrino bash padrino/scripts/migrate.sh

# 3. Verificar schema
sudo -u padrino sqlite3 /srv/padrino/data/padrino.db ".schema"
```
