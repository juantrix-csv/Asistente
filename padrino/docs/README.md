# Padrino Digital

Tu asistente personal que vive en tu VPS, funciona por Telegram, y te ayuda
a organizar tareas, finanzas, disciplina, y proyectos.

## ¿Qué es Padrino Digital?

Padrino Digital es un asistente personal basado en [Hermes Agent](https://github.com/NousResearch/Hermes-Function-Calling)
que corre en tu propio servidor. No es un SaaS, no es una app con suscripción,
no comparte tus datos con terceros. Es **tu** asistente, en **tu** infraestructura,
con **tu** control total.

## ¿Qué puede hacer?

| Dominio | Capacidades |
|---------|------------|
| 📋 **Tareas** | CRUD, 8 estados, proyectos, metas, priorización, snooze |
| 💰 **Finanzas** | Gastos, ingresos, transferencias, presupuestos, ahorros, deudas |
| 🎯 **Disciplina** | Hábitos diarios/semanales/mensuales, accountability, modo mínimo |
| 📅 **Planificación** | Ranking multi-criterio, plan diario, detección de sobrecarga |
| 📊 **Revisiones** | Check-in diario, revisión nocturna, semanal, mensual |
| 🧠 **Memoria** | Captura de datos, FTS5 search, decisiones, journal |
| 🔒 **Backup** | Backup diario encriptado GPG AES-256, restore con verificación |
| 🔐 **Seguridad** | Path allowlist, command allowlist, audit log append-only |
| 🔍 **Auditoría** | Análisis de código de repos autorizados (read-only) |

## Arquitectura

```
Telegram ↔ Hermes Gateway ↔ Padrino Digital (11 skills)
                                │
                        /srv/padrino/data/padrino.db (SQLite)
                                │
                        Cron jobs (daily/weekly/monthly)
```

## Requisitos

- **VPS**: Debian 12+ o Ubuntu 22.04+ (1 GB RAM mínimo, 10 GB disco)
- **Python**: 3.11+
- **SQLite**: 3.35+ con FTS5
- **Hermes Agent**: v0.18.0
- **Telegram Bot Token**: de @BotFather

## Instalación rápida

```bash
# 1. Clonar el repo
git clone https://github.com/juantrix-csv/padrino-digital.git
cd padrino-digital

# 2. Ejecutar setup (como root)
sudo bash padrino/scripts/setup.sh

# 3. Configurar variables de entorno
cp padrino/config/.env.template ~/.hermes/.env
chmod 600 ~/.hermes/.env
nano ~/.hermes/.env   # Completar HERMES_TELEGRAM_TOKEN y PADRINO_BACKUP_KEY

# 4. Iniciar
sudo -u padrino bash padrino/scripts/start.sh
```

Ver [INSTALLATION.md](INSTALLATION.md) para instrucciones detalladas.

## Comandos de Telegram

| Comando | Acción |
|---------|--------|
| `/hoy` | Plan del día |
| `/plan` | Planificación completa |
| `/tareas` | Lista de tareas |
| `/inbox` | Clasificar mensaje en inbox |
| `/gasto {monto} {descripción}` | Registrar gasto |
| `/finanzas` | Resumen financiero |
| `/presupuesto` | Estado de presupuestos |
| `/habito {nombre}` | Registrar hábito |
| `/modo minimo` | Activar modo mínimo |
| `/checkin` | Check-in diario |
| `/resumen` | Revisión del día |
| `/recordar {contenido}` | Guardar en memoria |
| `/backup` | Backup manual |
| `/auditar {repo}` | Auditar repositorio |

También podés hablar en lenguaje natural: "Agregá comprar verduras a las 18hs",
"¿Cuánto gasté este mes en supermercado?", "¿Qué prioridades tengo mañana?"

## Documentación

- [Arquitectura](ARCHITECTURE.md) — diseño completo, capas, flujo de datos
- [Instalación](INSTALLATION.md) — guía paso a paso para VPS
- [Configuración](CONFIGURATION.md) — todas las opciones
- [Telegram Setup](TELEGRAM_SETUP.md) — crear bot, obtener token
- [Guía de Usuario](USER_GUIDE.md) — comandos, ejemplos, flujos de trabajo
- [Seguridad](SECURITY.md) — modelo de seguridad, permisos, firewall
- [Backup & Restore](BACKUP_AND_RESTORE.md) — estrategia de backup
- [Operaciones](OPERATIONS.md) — scripts, cron, healthcheck
- [Troubleshooting](TROUBLESHOOTING.md) — problemas comunes
- [Próximos Pasos](NEXT_STEPS.md) — roadmap, mejoras planeadas
- [Catálogo de Skills](SKILL_CATALOG.md) — lista de los 12 skills

## Licencia

MIT — hacé lo que quieras, es tu asistente.
