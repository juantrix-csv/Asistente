# Catálogo de Skills — Padrino Digital

Lista completa de los 12 skills que componen Padrino Digital, con descripciones,
dependencias, y comandos expuestos.

---

## 1. padrino-soul
**Rol**: Persona principal
**Fase**: 2 — Core Personal
**Archivo**: `~/.hermes/skills/padrino-soul/SKILL.md` (symlink `~/.hermes/SOUL.md`)

Define la identidad de Padrino Digital: quién es, cómo habla, qué principios sigue.
Gestiona 5 modos de interacción (normal, firme, crisis, enfoque, finanzas) y los
approval gates que requieren confirmación del usuario para operaciones sensibles.

**Comandos**: `/modo {normal|firme|crisis|enfoque|finanzas}`

**Dependencias**: Ninguna (es la raíz)

---

## 2. padrino-hermes
**Rol**: Instalación y gateway
**Fase**: 1 — Hermes + Telegram
**Archivo**: `~/.hermes/skills/padrino-hermes/SKILL.md`

Guía de instalación, configuración y mantenimiento de Hermes Agent v0.18.0.
Cubre la instalación del Telegram Gateway, systemd service, healthchecks,
y troubleshooting de conectividad.

**Dependencias**: padrino-security

---

## 3. padrino-inbox
**Rol**: Clasificador universal
**Fase**: 2 — Core Personal
**Archivo**: `~/.hermes/skills/padrino-inbox/SKILL.md`

Clasifica mensajes entrantes en 13 tipos (task, idea, memory, decision, expense,
income, goal, habit, reminder, project_update, code_audit_request, journal_entry,
unknown). Usa LLM con umbral de confianza: ≥80% auto-route, <80% pregunta al usuario.

**Comandos**: `/inbox {mensaje}`

**Dependencias**: padrino-soul, padrino-memory, padrino-tasks, padrino-finance, padrino-coach

---

## 4. padrino-memory
**Rol**: Captura y recall
**Fase**: 2 — Core Personal
**Archivo**: `~/.hermes/skills/padrino-memory/SKILL.md`

Sistema de memoria dual: SQLite + FTS5 para datos estructurados y búsqueda
full-text, y archivos Markdown en `~/.hermes/memory/` para narrativa.
Captura datos con metadata (source, confidence, type, validity). Journal
append-only con timestamp. Correcciones vía confirmación del usuario.

**Comandos**: `/recordar {contenido}`

**Dependencias**: padrino-soul

---

## 5. padrino-tasks
**Rol**: Tareas, proyectos, metas
**Fase**: 2 — Core Personal
**Archivo**: `~/.hermes/skills/padrino-tasks/SKILL.md`

CRUD completo de tareas con 8 estados (inbox, todo, scheduled, in_progress,
blocked, waiting, done, cancelled). Gestión de proyectos con 4 estados y metas
con tracking numérico. Recordatorios con recurrencia.

**Comandos**: `/tareas`, `/tarea`, `/proyecto`, `/meta`

**Dependencias**: padrino-soul, padrino-memory

---

## 6. padrino-plan
**Rol**: Planificación diaria
**Fase**: 3 — Planning & Discipline
**Archivo**: `~/.hermes/skills/padrino-plan/SKILL.md`

Ranking multi-criterio de tareas (due date, priority, impact, urgencia, snooze
count, dependencias, tiempo, energía, balance de áreas, compromisos, bloqueos).
Plan diario con cap de 3 prioridades (2 en modo mínimo). Detección de sobrecarga
con 3 niveles. Planes provisorios cuando no hay check-in.

**Comandos**: `/hoy`, `/plan`, `/checkin`

**Dependencias**: padrino-tasks, padrino-coach, daily_checkins

---

## 7. padrino-coach
**Rol**: Hábitos y accountability
**Fase**: 3 — Planning & Discipline
**Archivo**: `~/.hermes/skills/padrino-coach/SKILL.md`

Seguimiento de hábitos con compliance semanal. Detección de estancamiento:
snooze escalation a las 3 repeticiones, stall detection a los 7 días, open-task
threshold en 20+. Modo mínimo con reducción de carga. Streaks como métrica
complementaria, nunca usados para avergonzar.

**Comandos**: `/habito`, `/habitos`, `/modo minimo`, `/modo normal`

**Dependencias**: padrino-tasks, padrino-soul (modos), habit_entries

---

## 8. padrino-finance
**Rol**: Finanzas personales
**Fase**: 4 — Finances
**Archivo**: `~/.hermes/skills/padrino-finance/SKILL.md`

Registro de transacciones con 4 tipos (expense, income, transfer, adjustment).
Presupuestos con alertas a 4 niveles. Metas de ahorro con cálculo de ritmo.
Deudas con tracking de pagos. 7 reglas financieras críticas (no mover dinero,
no conectar bancos, no mezclar transferencias, mantener moneda original,
disclaimer obligatorio, correcciones vía reversal entries).

**Comandos**: `/gasto`, `/ingreso`, `/finanzas`, `/presupuesto`, `/ahorro`, `/deudas`

**Dependencias**: padrino-soul (approval gates), padrino-security (audit log)

---

## 9. padrino-review
**Rol**: Revisiones periódicas
**Fase**: 3 — Planning & Discipline
**Archivo**: `~/.hermes/skills/padrino-review/SKILL.md`

Síntesis diaria (morning + evening), semanal (logros, hábitos, finanzas,
proyectos estancados), y mensual (evolución financiera, metas, tendencias,
comparativa mes anterior). Opera sin contexto conversacional — consulta
la DB fresca cada vez. Deduplication guards por tipo de review.

**Comandos**: `/checkin`, `/resumen`

**Dependencias**: TODOS los skills de datos (lee, no escribe)

---

## 10. padrino-audit
**Rol**: Auditor de código
**Fase**: 5 — Code Auditor
**Archivo**: `~/.hermes_auditor/skills/padrino-audit/SKILL.md` (perfil separado)

Audita repositorios autorizados con acceso read-only. Detecta lenguaje y
framework, analiza diff incremental, corre herramientas estáticas seguras,
genera hallazgos estructurados (ID, severidad, confianza, evidencia,
reproducción, acceptance criteria), y produce OpenCode_TASKS.md.

**Comandos**: `/auditar {repo-url}`

**Dependencias**: padrino-security (allowlist), corre bajo perfil aislado

---

## 11. padrino-backup
**Rol**: Backup y restore
**Fase**: 6 — Robustness
**Archivo**: `~/.hermes/skills/padrino-backup/SKILL.md`

Backup diario encriptado con GPG AES-256. Incluye: SQLite dump, memoria
Markdown, configs, skills, cron, reportes. Excluye: .env, secrets, tokens.
Retención configurable (default 30 días). Restauración con verificación de
checksum, confirmación del usuario, y PRAGMA integrity_check. Alerta solo
en fallo o anomalía de tamaño.

**Comandos**: `/backup`, `/backup status`, `/restaurar {fecha}`, `/restaurar list`

**Dependencias**: padrino-security (audit log)

---

## 12. padrino-security
**Rol**: Hardening y auditoría
**Fase**: 6 — Robustness
**Archivo**: `~/.hermes/skills/padrino-security/SKILL.md`

Security middleware: path write enforcement (solo paths allowlist), command
execution allowlist, audit_log append-only, rate limiting en operaciones
sensibles (30 tx/hora, 20 tareas/hora, 1 backup/hora, 1 restore/día).
Bloqueo de paths sensibles (.env, .ssh/, /etc/). Verificación de secretos.

**Comandos**: Ninguno directo (opera como middleware)

**Dependencias**: Ninguna (es la capa base de seguridad)

---

## Resumen de Fases

| Fase | Skills | Propósito |
|:----:|--------|-----------|
| 0 | — | Estructura del proyecto, setup inicial |
| 1 | padrino-hermes | Instalación, gateway, systemd |
| 2 | padrino-soul, inbox, memory, tasks | Core: identidad, clasificación, datos |
| 3 | padrino-plan, coach, review | Planificación, disciplina, revisiones |
| 4 | padrino-finance | Finanzas personales |
| 5 | padrino-audit | Auditoría de código |
| 6 | padrino-backup, security | Backup, hardening, seguridad |

## Cross-Skill Dependencies

```
padrino-soul ←── TODOS los skills (approval gates, modos)
     ↑
padrino-inbox ←── clasifica → memory, tasks, finance, coach, audit
     ↑
padrino-security ←── middleware para todos los writes y commands
     ↑
padrino-backup ←── backup/restore de todos los datos
     ↑
padrino-review ←── lee de TODOS los skills de datos
```

## Archivos

| Skill | Archivo |
|-------|---------|
| padrino-soul | `padrino/skills/padrino-soul/SKILL.md` |
| padrino-hermes | `padrino/skills/padrino-hermes/SKILL.md` |
| padrino-inbox | `padrino/skills/padrino-inbox/SKILL.md` |
| padrino-memory | `padrino/skills/padrino-memory/SKILL.md` |
| padrino-tasks | `padrino/skills/padrino-tasks/SKILL.md` |
| padrino-plan | `padrino/skills/padrino-plan/SKILL.md` |
| padrino-coach | `padrino/skills/padrino-coach/SKILL.md` |
| padrino-finance | `padrino/skills/padrino-finance/SKILL.md` |
| padrino-review | `padrino/skills/padrino-review/SKILL.md` |
| padrino-audit | `padrino/skills/padrino-audit/SKILL.md` |
| padrino-backup | `padrino/skills/padrino-backup/SKILL.md` |
| padrino-security | `padrino/skills/padrino-security/SKILL.md` |
