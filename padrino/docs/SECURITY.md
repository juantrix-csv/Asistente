# Seguridad — Padrino Digital

Modelo de seguridad: usuario del sistema, permisos, firewall, allowlists,
gestión de secretos, y auditoría.

## Principios de Seguridad

1. **Principio de mínimo privilegio**: Padrino solo accede a lo que necesita
2. **Defensa en profundidad**: OS + aplicación + auditoría
3. **Secretos nunca en texto plano**: .env con 600, excluidos de backups
4. **Append-only audit log**: toda acción sensible deja traza inmutable
5. **Allowlists, no denylists**: solo se permite lo explícitamente autorizado

## Usuario del Sistema

Padrino Digital corre como un usuario dedicado:

```bash
# Creado por setup.sh
useradd -m -s /bin/bash padrino
```

| Propiedad | Valor |
|-----------|-------|
| Username | `padrino` |
| UID | ≥ 1000 |
| Grupo | `padrino` (grupo propio) |
| Shell | `/bin/bash` |
| Sudo | ❌ NO |
| SSH | Solo key-based, sin password |
| umask | `077` (archivos nuevos solo accesibles por padrino) |

### Verificación

```bash
id padrino                              # uid, gid, groups
sudo -l -U padrino                       # Debe decir "not allowed to run sudo"
sudo -u padrino umask                    # Debe mostrar 0077
```

## Permisos de Archivos

| Archivo/Directorio | Permisos | Dueño | Notas |
|-------------------|:--------:|-------|-------|
| `~/.hermes/.env` | `600` | padrino:padrino | Contiene tokens |
| `~/.hermes/secrets.env` | `600` | padrino:padrino | Secrets adicionales |
| `~/.ssh/` | `700` | padrino:padrino | Llaves SSH |
| `/srv/padrino/data/` | `750` | padrino:padrino | Base de datos |
| `/srv/padrino/backups/` | `750` | padrino:padrino | Backups encriptados |
| `/srv/padrino/logs/` | `750` | padrino:padrino | Logs |

### Verificación

```bash
stat -c '%a %n' ~/.hermes/.env          # Debe mostrar: 600
stat -c '%a %n' ~/.hermes/secrets.env   # Debe mostrar: 600
```

## Firewall (UFW)

Configurado por `setup.sh`:

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp       # SSH
ufw allow 8443/tcp      # Hermes Gateway (Telegram webhook)
ufw enable
```

### Verificación

```bash
sudo ufw status verbose
```

## Path Allowlist

Padrino solo puede escribir en paths autorizados:

**Permitidos**:
```
/srv/padrino/data/padrino.db
/srv/padrino/backups/
/srv/padrino/logs/
~/.hermes/memory/
~/.hermes/skills/
~/.hermes/config.yaml
~/.hermes/sessions/
padrino/config/
padrino/cron/
/tmp/padrino-*
```

**BLOQUEADOS** (cualquier intento de escritura se rechaza y audita):
```
/etc/
/boot/
/root/
~/.ssh/
~/.hermes/.env
~/.hermes/secrets.env
/var/log/ (excepto /srv/padrino/logs/)
```

## Command Allowlist

Solo los comandos en `padrino/config/command-allowlist.txt` pueden ejecutarse.
Cualquier otro comando es rechazado y registrado como evento de seguridad.

Comandos **NUNCA permitidos**:
- `rm` (excepto en `/tmp/padrino-*`)
- `sudo`
- `chmod`
- `chown`
- `kill`
- `shutdown`
- `reboot`

## Gestión de Secretos

| Principio | Implementación |
|-----------|---------------|
| Única fuente | `~/.hermes/.env` (600) |
| Excluidos de backups | `backup.sh` verifica que no haya secrets en el staging |
| Nunca en logs | `audit_log` redacta secrets con `[REDACTED]` |
| Nunca en LLM context | Skills leen el .env al inicio, no lo inyectan en prompts |
| Rotación | Manual — cambiar token en .env y reiniciar gateway |

## Audit Log

Tabla `audit_log` — **append-only**, nunca se modifican ni eliminan filas:

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

### Acciones auditadas

| Acción | Cuándo |
|--------|--------|
| `INSERT transaction` | Cada mutación financiera |
| `UPDATE task` | Cambio de estado de tarea |
| `DELETE` | Cualquier eliminación |
| `backup` | Backup creado |
| `restore` | Restauración ejecutada |
| `WRITE_DENIED` | Intento de escritura bloqueado |
| `COMMAND_DENIED` | Comando no autorizado |
| `RATE_LIMITED` | Rate limit alcanzado |

## Rate Limiting

| Operación | Máximo | Ventana |
|-----------|:------:|--------|
| INSERT transaction | 30 | por hora |
| Crear tarea | 20 | por hora |
| Backup | 1 | por hora |
| Restore | 1 | por día |
| Export | 5 | por día |

## Checklist de Seguridad

### Verificación inicial (post-instalación)

- [ ] Usuario `padrino` existe y NO tiene sudo
- [ ] `umask 077` configurado en `~/.bashrc`
- [ ] `~/.hermes/.env` tiene permisos 600
- [ ] UFW activo, solo puertos 22 y 8443
- [ ] `command-allowlist.txt` no incluye `rm`, `sudo`
- [ ] `sensitive-paths.txt` incluye `/etc/`, `/root/`, `~/.ssh/`
- [ ] `audit_log` es append-only (sin triggers de UPDATE/DELETE)

### Verificación semanal

- [ ] `audit_log` sin eventos `DENIED` en los últimos 7 días
- [ ] `.env` sigue con permisos 600
- [ ] Backups se crean sin errores
- [ ] Sin accesos SSH no autorizados (`last -n 20`)

### Respuesta a incidentes

Si detectás actividad sospechosa:

1. **Revisar audit_log**:
   ```sql
   SELECT * FROM audit_log WHERE result = 'denied' ORDER BY id DESC;
   ```

2. **Revisar accesos SSH**:
   ```bash
   last -n 50
   sudo grep "Failed password" /var/log/auth.log | tail -20
   ```

3. **Rotar secrets**:
   ```bash
   # Cambiar HERMES_TELEGRAM_TOKEN en .env
   # Cambiar PADRINO_BACKUP_KEY en secrets.env
   sudo systemctl restart hermes-gateway
   ```

4. **Restaurar desde backup limpio** (si es necesario):
   ```bash
   bash padrino/scripts/restore.sh --latest
   ```
