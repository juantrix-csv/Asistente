# Arquitectura — Padrino Digital

## Visión General

Padrino Digital es una extensión de capas sobre Hermes Agent v0.18.0 — no un fork.
Cada dominio de negocio es un archivo `SKILL.md` independiente bajo
`~/.hermes/skills/padrino-*/`. Los datos estructurados viven en SQLite en
`/srv/padrino/data/padrino.db`. La memoria en Markdown se guarda en
`~/.hermes/memory/`. Telegram es la interfaz primaria vía Hermes Gateway.

## Capas

```
┌──────────────────────────────────────────────────────────────────┐
│                     CAPA DE INTERFAZ                              │
│  Telegram Bot API → Hermes Gateway → systemd service             │
│  (padrino-hermes gestina instalación, gateway, healthcheck)      │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                     CAPA DE PERSONA                               │
│  padrino-soul (SOUL.md)                                          │
│  - Identidad, 5 modos, approval gates, reglas de tono            │
│  - Toda interacción pasa por acá primero                          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                     CAPA DE CLASIFICACIÓN                         │
│  padrino-inbox                                                    │
│  - Clasificador LLM de 13 tipos                                  │
│  - confianza ≥80% → auto-route                                   │
│  - confianza <80% → pregunta al usuario                           │
└───────┬───────┬───────┬───────┬───────┬───────┬──────────────────┘
        │       │       │       │       │       │
┌───────▼─┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐ ┌──▼───┐ ┌▼──────────────┐
│ CAPA DE DOMINIO (Skills de Negocio)                               │
│                                                                   │
│ padrino-    padrino-  padrino-  padrino-  padrino-  padrino-     │
│ memory      tasks     plan      coach     finance   review        │
│                                                                   │
│ Captura     CRUD      Ranking    Hábitos   Transacc. Síntesis     │
│ Recall      Proyectos Prioridad  Stall     Budgets   Diaria       │
│ Journal     Goals     Overload   Min-Mode  Savings   Semanal      │
│ FTS5                  Check-in             Debts     Mensual      │
└───────┬───────┬───────┬───────┬───────┬───────┬──────────────────┘
        │       │       │       │       │       │
┌───────▼───────▼───────▼───────▼───────▼───────▼──────────────────┐
│                     CAPA DE DATOS                                 │
│  /srv/padrino/data/padrino.db (SQLite, 17+ tablas)               │
│  ~/.hermes/memory/ (Markdown, FTS5 indexado)                      │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                     CAPA DE INFRAESTRUCTURA                       │
│  padrino-backup    padrino-security    padrino-audit              │
│                                                                   │
│  GPG encrypt       Path allowlist      Read-only clone            │
│  SHA-256 verify    Command allowlist   Diff analysis              │
│  Retention rotate  Audit log (append)  OpenCode_TASKS.md          │
│  Restore test      Rate limiting       Profile isolation          │
└──────────────────────────────────────────────────────────────────┘
```

## Flujo de Datos — Mensaje de Telegram

```
Usuario → Telegram API
    → Hermes Gateway (recibe webhook)
    → padrino-soul: detecta modo (normal/firme/crisis/enfoque/finanzas)
    → padrino-soul: verifica approval gate (es write? necesita confirmación?)
    → padrino-inbox: clasifica intención (task/expense/memory/habit/...)
    → Skill de dominio: procesa (ej. padrino-finance para un gasto)
    → padrino-security: verifica path allowlist + command allowlist
    → SQLite: INSERT/UPDATE/DELETE (si aplica)
    → padrino-soul: formatea respuesta
    → Hermes Gateway → Telegram API → Usuario
```

## Flujo de Datos — Cron Job

```
Cron (systemd timer o crontab)
    → Hermes cron create "prompt autocontenido"
    → padrino-soul: modo normal, sin approval gate (cron pre-aprobado)
    → Skill correspondiente (plan/review/backup)
    → Consulta DB (SELECTs, nunca INSERTs sin gate)
    → Formatea mensaje
    → Hermes Gateway → Telegram API → Usuario (--deliver telegram)
```

## Base de Datos

Ubicación: `/srv/padrino/data/padrino.db`
Motor: SQLite 3.35+ con FTS5

### Tablas (17)

| Tabla | Propósito | Skill dueño |
|-------|-----------|-------------|
| `schema_version` | Control de migraciones | setup.sh |
| `tasks` | Tareas con 8 estados | padrino-tasks |
| `projects` | Proyectos con áreas | padrino-tasks |
| `goals` | Metas con tracking | padrino-tasks |
| `habits` | Definición de hábitos | padrino-coach |
| `habit_entries` | Registro diario de hábitos | padrino-coach |
| `transactions` | Finanzas (4 tipos) | padrino-finance |
| `budgets` | Presupuestos por categoría | padrino-finance |
| `savings_goals` | Metas de ahorro | padrino-finance |
| `debts` | Deudas y pagos | padrino-finance |
| `memories` | Datos y hechos | padrino-memory |
| `memories_fts` | Índice FTS5 de memories | padrino-memory |
| `decisions` | Decisiones documentadas | padrino-memory |
| `daily_checkins` | Check-in diario | padrino-plan |
| `reminders` | Recordatorios | padrino-tasks |
| `audit_runs` | Ejecuciones de auditoría | padrino-audit |
| `audit_findings` | Hallazgos de auditoría | padrino-audit |
| `audit_log` | Registro de seguridad (append-only) | padrino-security |

### Relaciones clave

```
tasks.project_id  → projects.id
tasks.snooze_count → padrino-coach (escalation detection)
habit_entries.habit_id → habits.id
transactions.correction_id → transactions.id (reversal entries)
memories_fts.content_rowid → memories.id (FTS5 external content)
audit_findings.audit_run_id → audit_runs.id
```

## Skills (12)

| # | Skill | Rol | Fase |
|---|-------|-----|------|
| 1 | `padrino-soul` | Persona, modos, approval gates | 2 |
| 2 | `padrino-hermes` | Instalación, gateway, systemd | 1 |
| 3 | `padrino-inbox` | Clasificador universal | 2 |
| 4 | `padrino-memory` | Captura, recall, journal, FTS5 | 2 |
| 5 | `padrino-tasks` | CRUD tareas, proyectos, metas | 2 |
| 6 | `padrino-plan` | Planificación diaria, ranking | 3 |
| 7 | `padrino-coach` | Hábitos, accountability, modo mínimo | 3 |
| 8 | `padrino-finance` | Transacciones, presupuestos, deudas | 4 |
| 9 | `padrino-review` | Síntesis diaria/semanal/mensual | 3 |
| 10 | `padrino-audit` | Auditoría de código (read-only) | 5 |
| 11 | `padrino-backup` | Backup encriptado, restore | 6 |
| 12 | `padrino-security` | Path/command allowlist, audit log | 6 |

## Cross-Skill Contracts

Cada skill define explícitamente:
- **Calls (outbound)**: qué otros skills consume
- **Called by**: qué skills lo invocan
- **Events**: eventos que emite para coordinación
- **Database Tables**: qué tablas lee y escribe

Los skills NUNCA escriben directamente en el dominio de otro skill — toda
comunicación entre dominios pasa por tablas compartidas de la base de datos.

## Modos de Operación

| Modo | Trigger | Comportamiento |
|------|---------|---------------|
| `normal` | Default | Balanceado, cálido, voseo rioplatense |
| `firme` | `/modo firme` o 3+ snoozes | Directo, accountability, sin suavizar |
| `crisis` | Keywords de emergencia | Calmo, estructurado, mínimas palabras |
| `enfoque` | `/modo enfoque` o deep-work | Silencioso salvo crítico |
| `finanzas` | Query financiera detectada | Analítico, disclaimer obligatorio |

## Approval Gates

Operaciones que requieren confirmación explícita del usuario:
- Escritura en base de datos (INSERT, UPDATE, DELETE)
- Ejecución de comandos shell
- Exportación de datos
- Restauración de backup
- Cualquier operación que exponga datos personales

Las lecturas (SELECT, FTS5 search) y consultas de estado nunca requieren gate.

## Aislamiento del Auditor

El code auditor (`padrino-audit`) corre bajo un perfil Hermes separado:
- **Perfil**: `~/.hermes_auditor/`
- **Sin Telegram**: invocado solo por CLI
- **Tokens read-only**: no puede modificar repos
- **Sin acceso a datos personales**: no lee padrino.db ni memory/
- **Isolation**: filesystem-level, perfil Hermes diferente
