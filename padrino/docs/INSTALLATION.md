# Instalación — Padrino Digital

Guía paso a paso para instalar Padrino Digital en un VPS Debian/Ubuntu.

## Requisitos del VPS

| Componente | Mínimo | Recomendado |
|-----------|--------|-------------|
| RAM | 1 GB | 2 GB |
| Disco | 10 GB | 20 GB |
| OS | Debian 12 | Ubuntu 22.04+ |
| Python | 3.11 | 3.12+ |
| SQLite | 3.35 | 3.40+ |

## Paso 1 — Preparar el VPS

```bash
# Conectarse al VPS
ssh root@tu-vps-ip

# Actualizar el sistema
apt update && apt upgrade -y

# Instalar dependencias del sistema
apt install -y python3 python3-pip python3-venv sqlite3 git curl ufw gnupg tar
```

## Paso 2 — Clonar Padrino Digital

```bash
# Clonar en /opt (o donde prefieras)
cd /opt
git clone https://github.com/juantrix-csv/padrino-digital.git
cd padrino-digital
```

## Paso 3 — Ejecutar setup.sh

```bash
# Ejecutar como root (crea usuario padrino, directorios, firewall)
sudo bash padrino/scripts/setup.sh
```

El script hace lo siguiente (idempotente, seguro correr múltiples veces):
1. Crea el usuario `padrino` (sin sudo, SSH key-only)
2. Configura umask 077
3. Crea `/srv/padrino/data/` y `/srv/padrino/backups/` con permisos correctos
4. Verifica dependencias (Python 3.11+, SQLite 3.35+)
5. Instala Hermes Agent v0.18.0
6. Configura y habilita el servicio systemd `hermes-gateway`
7. Habilita UFW (solo SSH + puerto gateway)

## Paso 4 — Configurar variables de entorno

```bash
# Copiar template
sudo -u padrino cp /opt/padrino-digital/padrino/config/.env.template ~/.hermes/.env

# Asegurar permisos
sudo chmod 600 ~/.hermes/.env

# Editar
sudo -u padrino nano ~/.hermes/.env
```

Variables requeridas:
```bash
HERMES_TELEGRAM_TOKEN=123456:ABC-DEF1234ghijklmno  # De @BotFather
PADRINO_BACKUP_KEY=una-frase-secreta-larga-y-segura  # Para GPG
TZ=America/Argentina/Buenos_Aires
```

Opcionales (model APIs):
```bash
OPENAI_API_KEY=sk-...        # Si usás OpenAI
ANTHROPIC_API_KEY=sk-ant-... # Si usás Anthropic
```

## Paso 5 — Crear el bot de Telegram

1. Abrí Telegram y buscá `@BotFather`
2. Enviá `/newbot` y seguí las instrucciones
3. Guardá el token que te da (ej. `123456:ABC-DEF1234ghijklmno`)
4. Enviá `/setprivacy` → seleccioná tu bot → **Enable**
5. Enviá `/setcommands` → seleccioná tu bot → pegá:

```
hoy - Plan del día
plan - Planificación completa
tareas - Lista de tareas
inbox - Clasificar mensaje
gasto - Registrar un gasto
finanzas - Resumen financiero
presupuesto - Estado de presupuestos
habito - Registrar hábito
modo - Cambiar modo (normal, firme, crisis, enfoque, finanzas)
checkin - Check-in diario
resumen - Revisión del día
recordar - Guardar en memoria
backup - Backup manual
auditar - Auditar repositorio
```

## Paso 6 — Inicializar la base de datos

```bash
# Aplicar schema inicial
sudo -u padrino bash padrino/scripts/migrate.sh
```

Verifica que las tablas se crearon:
```bash
sudo -u padrino sqlite3 /srv/padrino/data/padrino.db ".tables"
```

## Paso 7 — Copiar skills y archivos

```bash
# Copiar skills a ~/.hermes/skills/
sudo -u padrino cp -r /opt/padrino-digital/padrino/skills/padrino-* ~/.hermes/skills/

# Crear symlink del SOUL
sudo -u padrino ln -sf ~/.hermes/skills/padrino-soul/SKILL.md ~/.hermes/SOUL.md

# Copiar templates de memoria
sudo -u padrino cp -r /opt/padrino-digital/padrino/memory/* ~/.hermes/memory/ 2>/dev/null || true
```

## Paso 8 — Instalar cron jobs

```bash
# Instalar crontab para el usuario padrino
sudo crontab -u padrino /opt/padrino-digital/padrino/cron/padrino-crons.txt

# Verificar
sudo crontab -u padrino -l
```

## Paso 9 — Configurar webhook de Telegram

```bash
# Reemplazá <TOKEN> y <VPS_IP_OR_DOMAIN>
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<VPS_IP_OR_DOMAIN>:8443/telegram"
```

## Paso 10 — Iniciar el servicio

```bash
# Iniciar Hermes Gateway
sudo -u padrino bash /opt/padrino-digital/padrino/scripts/start.sh

# Verificar estado
sudo -u padrino bash /opt/padrino-digital/padrino/scripts/status.sh

# Healthcheck
sudo -u padrino bash /opt/padrino-digital/padrino/scripts/healthcheck.sh
```

## Paso 11 — Verificar

Enviá un mensaje a tu bot de Telegram:
```
Hola Padrino
```

Deberías recibir una respuesta. Si no, revisá [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Paso 12 — Configurar auditor de código (opcional)

```bash
# Crear perfil auditor
sudo -u padrino /opt/padrino-digital/padrino/auditor-profile/README.md
```

Seguí las instrucciones en [CODE_AUDITOR.md](CODE_AUDITOR.md).

## Verificación post-instalación

```bash
# Correr tests
sudo -u padrino bash /opt/padrino-digital/padrino/scripts/test.sh

# Verificar backup
sudo -u padrino bash /opt/padrino-digital/padrino/scripts/backup.sh --dry-run
```

## Estructura resultante

```
/home/padrino/
├── .hermes/
│   ├── SOUL.md → skills/padrino-soul/SKILL.md
│   ├── .env (600)
│   ├── config.yaml
│   ├── skills/
│   │   ├── padrino-soul/SKILL.md
│   │   ├── padrino-hermes/SKILL.md
│   │   ├── padrino-inbox/SKILL.md
│   │   ├── padrino-memory/SKILL.md
│   │   ├── padrino-tasks/SKILL.md
│   │   ├── padrino-plan/SKILL.md
│   │   ├── padrino-coach/SKILL.md
│   │   ├── padrino-finance/SKILL.md
│   │   ├── padrino-review/SKILL.md
│   │   ├── padrino-backup/SKILL.md
│   │   └── padrino-security/SKILL.md
│   ├── memory/
│   ├── sessions/
│   └── logs/
├── .hermes_auditor/    # Perfil separado (opcional)
│   ├── SOUL.md
│   ├── .env
│   └── skills/padrino-audit/SKILL.md
└── padrino/scripts/    # Scripts operativos
    ├── start.sh, stop.sh, restart.sh, status.sh
    ├── healthcheck.sh, backup.sh, restore.sh, export.sh
    └── test.sh, audit-repo.sh

/srv/padrino/
├── data/padrino.db
├── backups/
└── logs/
```

## Siguientes pasos

- Leé [USER_GUIDE.md](USER_GUIDE.md) para aprender los comandos
- Configurá tus áreas y proyectos en [MEMORY_MODEL.md](MEMORY_MODEL.md)
- Revisá [SECURITY.md](SECURITY.md) para hardening adicional
- Programá el primer backup: `/backup`
