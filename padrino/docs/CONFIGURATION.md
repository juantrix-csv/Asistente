# Configuración — Padrino Digital

Todas las opciones de configuración de Padrino Digital, con sus valores por defecto
y explicaciones.

## Archivos de Configuración

| Archivo | Ubicación | Propósito |
|---------|-----------|-----------|
| `.env` | `~/.hermes/.env` | Variables de entorno (tokens, keys) |
| `config.yaml` | `~/.hermes/config.yaml` | Configuración de Hermes Agent |
| `command-allowlist.txt` | `padrino/config/` | Comandos shell permitidos |
| `repo-allowlist.txt` | `padrino/config/` | Repos autorizados para auditoría |
| `sensitive-paths.txt` | `padrino/config/` | Paths bloqueados para escritura |
| `retention.conf` | `padrino/config/` | Política de retención de backups |
| `padrino-gateway.service` | `padrino/config/` | Systemd unit para el gateway |
| `padrino-crons.txt` | `padrino/cron/` | Cron jobs programados |

## Variables de Entorno (.env)

### Requeridas

| Variable | Descripción | Ejemplo |
|----------|------------|---------|
| `HERMES_TELEGRAM_TOKEN` | Token del bot de Telegram (de @BotFather) | `123456:ABC-DEF...` |
| `PADRINO_BACKUP_KEY` | Frase de encriptación GPG para backups | `frase-larga-segura-123` |
| `TZ` | Zona horaria | `America/Argentina/Buenos_Aires` |

### APIs de Modelos (al menos una requerida)

| Variable | Descripción |
|----------|------------|
| `OPENAI_API_KEY` | API key de OpenAI |
| `ANTHROPIC_API_KEY` | API key de Anthropic |
| `GROQ_API_KEY` | API key de Groq |
| `TOGETHER_API_KEY` | API key de Together.ai |

### Opcionales

| Variable | Default | Descripción |
|----------|---------|-------------|
| `HERMES_GATEWAY_PORT` | `8443` | Puerto del gateway Telegram |
| `HERMES_MODEL` | `gpt-4o` | Modelo por defecto |
| `HERMES_LOG_LEVEL` | `info` | Nivel de logging |
| `AUDIT_MAX_FINDINGS` | `50` | Máximo de hallazgos por auditoría |
| `BACKUP_RETENTION_DAYS` | `30` | Días de retención de backups |

### Archivo de Secrets (separado)

Para secretos adicionales que NO deben incluirse en backups:

```bash
# ~/.hermes/secrets.env (chmod 600)
# Este archivo NUNCA se incluye en backups
PADRINO_BACKUP_KEY=...
```

## Configuración de Hermes (config.yaml)

```yaml
# ~/.hermes/config.yaml
agent:
  name: "Padrino Digital"
  model: "gpt-4o"
  temperature: 0.7
  max_tokens: 4096

gateway:
  port: 8443
  webhook_path: "/telegram"
  webhook_url: "https://tu-vps.com:8443/telegram"

skills:
  directory: "~/.hermes/skills/"
  autoload: true

database:
  path: "/srv/padrino/data/padrino.db"

memory:
  path: "~/.hermes/memory/"
  fts5_enabled: true

logging:
  level: "info"
  file: "~/.hermes/logs/hermes.log"

cron:
  enabled: true
  timezone: "America/Argentina/Buenos_Aires"
```

## Command Allowlist

Archivo: `padrino/config/command-allowlist.txt`

Formato: un comando por línea. La primera palabra es el comando permitido.
Tokens adicionales especifican argumentos aceptados. `*` es wildcard.

```
git clone --depth 1 *     # Clonado superficial read-only
git log *                  # Historial
git diff *                 # Diffs
sqlite3 *                  # Consultas SQLite
tar czf *                  # Crear archivos
tar xzf *                  # Extraer archivos
sha256sum *                # Checksums
gpg --symmetric --batch *  # Encriptar
gpg --decrypt *            # Desencriptar
```

Los comandos NO listados son rechazados automáticamente y se registra un
evento de seguridad en `audit_log`.

## Repo Allowlist

Archivo: `padrino/config/repo-allowlist.txt`

Formato: una URL HTTPS de repositorio por línea.

```
# Repos autorizados para code auditor
https://github.com/juantrix-csv/nexios-backend
https://github.com/juantrix-csv/nexios-frontend
```

El auditor RECHAZA cualquier repo no listado.

## Sensitive Paths

Archivo: `padrino/config/sensitive-paths.txt`

Formato: un path por línea, con operaciones permitidas.

```
# Paths donde Padrino PUEDE escribir
/srv/padrino/data/padrino.db            modify
/srv/padrino/backups/                   create
~/.hermes/memory/                        create, modify, append, delete

# Paths BLOQUEADOS (nunca escribir)
/etc/
/root/
~/.ssh/
~/.hermes/.env
```

## Retención de Backups

Archivo: `padrino/config/retention.conf`

```
# Política de retención
# Formato: <tier> <count>
daily   7      # Últimos 7 backups diarios
weekly  4      # 1 por semana, últimas 4 semanas
monthly 12     # 1 por mes, últimos 12 meses
```

## Cron Jobs

Archivo: `padrino/cron/padrino-crons.txt`

| Job | Horario (ART) | Propósito |
|-----|:------------:|-----------|
| Morning summary | 08:00 | Prioridades, compromisos, recordatorios |
| Evening review | 21:30 | Tareas completadas, obstáculos, gastos |
| Weekly review | Dom 19:00 | Síntesis semanal completa |
| Monthly review | Día 1 10:00 | Síntesis mensual, comparativa |
| Daily backup | 03:00 | Backup encriptado diario |

Para modificar horarios, editá el archivo y reinstalá:
```bash
crontab -u padrino padrino/cron/padrino-crons.txt
```

## Systemd Service

Archivo: `padrino/config/padrino-gateway.service`

```ini
[Unit]
Description=Hermes Gateway for Padrino Digital
After=network.target

[Service]
Type=simple
User=padrino
WorkingDirectory=/home/padrino/hermes-agent
ExecStart=/home/padrino/hermes-agent/hermes gateway start
Restart=on-failure
RestartSec=10
EnvironmentFile=/home/padrino/.hermes/.env
Environment=TZ=America/Argentina/Buenos_Aires

[Install]
WantedBy=multi-user.target
```

## Auditor Profile (.env)

Archivo separado: `~/.hermes_auditor/.env`

```bash
# Solo tokens read-only — el auditor NUNCA modifica repos
GIT_READONLY_TOKEN=github_pat_...
```

## Verificación de Configuración

```bash
# Verificar que .env tiene permisos correctos
stat -c '%a %n' ~/.hermes/.env  # Debe mostrar: 600

# Verificar allowlists
cat padrino/config/command-allowlist.txt
cat padrino/config/repo-allowlist.txt

# Verificar cron instalado
crontab -u padrino -l

# Verificar systemd
systemctl status hermes-gateway
```
