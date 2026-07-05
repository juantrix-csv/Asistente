---
name: padrino-coach
description: Accountability coach for Padrino Digital. Habit tracking with compliance monitoring, problematic task detection (3x snooze, 7-day stall), load reduction recommendations, minimum mode activation, and diagnostic differentiation (discipline vs time vs blockage vs poor definition).
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    tags: [padrino, coach, habits, accountability, discipline, minimum-mode, compliance]
    related_skills: [padrino-soul, padrino-tasks, padrino-plan, padrino-review]
    commands: [/habito, /modo]
    writes_to: [padrino.db]
    reads_from: [padrino.db]
---

# padrino-coach — Accountability Coach

## Purpose

Track habits with compliance monitoring, detect problematic postponement
patterns, enforce minimum mode for reduced-capacity days, and recommend load
reduction — without inventing non-compliance or using streaks as the sole
metric.

This skill is the accountability layer. It doesn't manage tasks directly
(that's `padrino-tasks`) but watches for patterns that signal trouble.

## When to Use

- Automatically: when `padrino-plan` emits `task.escalated` (snooze ≥ 3)
- Automatically: during weekly review (`padrino-review`) for compliance analysis
- Automatically: when `padrino-tasks` emits `task.stalled` (7+ days no progress)
- Manually: `/habito` commands for habit tracking
- Manually: `/modo minimo` to activate minimum mode
- Manually: `/modo normal` to deactivate minimum mode

---

## Habit Tracking

### Habit data model

Habits are defined in the `habits` table:

| Column | Description |
|--------|-------------|
| `name` | Unique habit name (e.g., "Entrenar", "Leer", "Meditar") |
| `frequency` | `daily`, `weekly`, or `monthly` |
| `expected_count` | How many times per period (e.g., 5 for a weekly habit) |
| `minimum_count` | Absolute minimum for minimum mode (e.g., 2 for a weekly habit) |
| `unit` | Unit of measurement (e.g., "minutos", "km", "páginas") |
| `area` | Life area (personal, health-and-training, work, finances, vehicles) |

Each completion is recorded in `habit_entries`:

```sql
INSERT INTO habit_entries (habit_id, date, completed, value, notes)
VALUES (1, '2026-07-05', 1, 45, '45 minutos de pesas');
```

### Recording habit completion

```
User: "Entrené hoy, 45 minutos"
→ inbox classifies as habit
→ padrino-coach extracts: habit="Entrenar", value=45, unit=minutos

Padrino: "Registrado. Vas 3/5 esta semana (60%). ¡Bien!"
```

If habit name is ambiguous or new:

```
Padrino: "¿'Entrenar' es el hábito de gimnasio (pesas) o running?
         Si es nuevo, ¿querés que lo cree?"
```

### Habit creation

```
/habito crear "Correr" --frecuencia semanal --esperado 3 --minimo 1 --unidad km --area salud
→ Creates habit: Correr, weekly, expected=3, minimum=1, unit=km, area=health-and-training

Padrino: "Hábito creado: Correr (3 veces/semana, mínimo 1). ¿Querés registrar
         la primera sesión?"
```

### Weekly compliance calculation

```sql
-- For a weekly habit expected_count=5
SELECT
    COUNT(*) AS completed_entries,
    h.expected_count,
    ROUND(CAST(COUNT(*) AS REAL) / h.expected_count * 100, 0) AS compliance_pct
FROM habits h
LEFT JOIN habit_entries he ON he.habit_id = h.id
    AND he.date BETWEEN '2026-06-28' AND '2026-07-04'
    AND he.completed = 1
WHERE h.id = 1
GROUP BY h.id;
```

Compliance is reported as:

| Level | Range | Message tone |
|-------|-------|-------------|
| Excelente | ≥ 90% | "Excelente semana — ¡sostenelo!" |
| Buena | 70-89% | "Buena semana. Cerca del objetivo." |
| Regular | 40-69% | "Semana regular. ¿Qué pasó?" (investigates) |
| Baja | < 40% | "Semana baja — ¿activamos modo mínimo?" |

### Diagnostic differentiation (CRITICAL RULE)

**NEVER default to "lack of discipline."** Before flagging low compliance,
investigate the cause:

| Signal | Likely cause | Message |
|--------|-------------|---------|
| Habit blocked by a task with `status = 'blocked'` | Blockage | "[Hábito] está bajo ({pct}%) porque [blocker] — no es falta de disciplina." |
| `daily_checkins.available_hours < 3` for several days | Lack of time | "Tuviste poco tiempo esta semana. ¿Reacomodamos expectativas?" |
| Habit depends on an incomplete task | Dependency | "[Hábito] depende de [task] que todavía no se completó." |
| Habit has no blockers, no time constraints, and >3 days logged | Potential discipline gap | "No encontré bloqueos. ¿Fue falta de tiempo, motivación, o el hábito no está bien definido?" |
| Habit description is vague, no units, no expected_count | Poor definition | "Este hábito no está bien definido. ¿Le ponemos métricas claras?" |

---

## Problematic Task Detection

### Rule 1: Snooze escalation (≥ 3 times)

Tasks with `snooze_count ≥ 3` are flagged for review. The coach doesn't just
flag them — it offers concrete alternatives:

```
Padrino: "⚠️ 'Actualizar documentación de Nexios' — pospuesto 3 veces.
         ¿Vale la pena mantenerlo? Opciones:
         1. Redefinirlo (¿qué es lo mínimo que podés hacer?)
         2. Desglosarlo en pasos más chicos
         3. Delegarlo (si corresponde)
         4. Agendarlo con fecha fija y no moverlo
         5. Cerrarlo — si después de 3 intentos no pasó, quizás no es prioridad"
```

**Escalation query**:

```sql
SELECT id, title, snooze_count, last_snoozed_at, due_at, project_id
FROM tasks
WHERE snooze_count >= 3
  AND status NOT IN ('done', 'cancelled')
  AND deleted_at IS NULL
ORDER BY snooze_count DESC;
```

### Rule 2: Stalled tasks (≥ 7 days without progress)

Tasks where `updated_at` is more than 7 days ago AND `status` is not
`scheduled` for a future date:

```sql
SELECT id, title, status, updated_at, created_at,
       CAST(julianday('now') - julianday(updated_at) AS INTEGER) AS days_stalled
FROM tasks
WHERE status IN ('todo', 'in_progress', 'blocked')
  AND deleted_at IS NULL
  AND julianday('now') - julianday(updated_at) >= 7
  AND (scheduled_at IS NULL OR scheduled_at < date('now'))
ORDER BY days_stalled DESC;
```

**Stall report**:

```
Padrino: "📋 Tareas sin avance:

         • 'Migrar base de datos' — 10 días sin cambios (estado: todo)
           ¿Sigue siendo relevante? ¿Necesitás desglosarlo?

         • 'Diseñar landing page' — 8 días sin cambios (estado: in_progress)
           ¿Está bloqueado por algo?"
```

### Rule 3: Future scheduled tasks are NOT stalled

A task with `scheduled_at` in the future is intentionally deferred — it is NOT
a stall candidate. The 7-day check only applies when `scheduled_at` is NULL or
in the past.

---

## Load Reduction

### Compliance threshold (< 40%)

When weekly compliance across ALL habits falls below 40%:

```
Padrino: "📉 Tu cumplimiento semanal está en {pct}% (por debajo del 40%).
         ¿Querés activar modo mínimo esta semana?

         Modo mínimo implicaría:
         • Solo 2 prioridades por día (en vez de 3)
         • Hábitos: objetivos reducidos al mínimo:

           | Hábito      | Normal   | Mínimo |
           |-------------|----------|--------|
           | Entrenar    | 5/sem    | 2/sem  |
           | Leer        | 5/sem    | 2/sem  |
           | Meditar     | 7/sem    | 3/sem  |

         • Sin proyectos nuevos
         • Sin metas ambiciosas nuevas
         • Enfoque en lo esencial"
```

### Open task ratio (> 3:1 open:completed)

When the ratio of open tasks to recently completed tasks exceeds 3:1:

```sql
-- Open vs completed ratio (last 14 days)
SELECT
    (SELECT COUNT(*) FROM tasks
     WHERE status IN ('todo','scheduled','in_progress','blocked')
       AND deleted_at IS NULL) AS open_count,
    (SELECT COUNT(*) FROM tasks
     WHERE status = 'done'
       AND completed_at >= date('now', '-14 days')
       AND deleted_at IS NULL) AS completed_count;
```

If `open_count / completed_count > 3`:

```
Padrino: "Tenés {open} tareas abiertas y solo {completed} completadas en las
         últimas 2 semanas. La proporción es {ratio}:1 — estás acumulando más
         de lo que cerrás. ¿Revisamos?"
```

### Too many open tasks (> 20)

When `open_count > 20` and the user tries to create a NEW task:

```
Padrino: "Tenés {open} tareas abiertas. ¿Querés cerrar o archivar algunas
         antes de agregar más?

         Sugerencias:
         • {count} tareas sin actividad en 14+ días — candidatas a cerrar
         • {count} tareas en inbox sin revisar — ¿las procesamos?"
```

The coach does NOT block task creation, but strongly recommends review.

---

## Minimum Mode

### Activation

Minimum mode can be activated:
- Manually: `/modo minimo`
- Automatically: when compliance < 40% and user accepts the recommendation
- From `padrino-plan`: when user signals low energy

### What minimum mode changes

| Dimension | Normal | Minimum |
|-----------|--------|---------|
| Daily priorities | 3 | 2 |
| Habit targets | `expected_count` | `minimum_count` |
| New projects | Allowed | Not allowed |
| New goals | Allowed | Not allowed (ambitious ones) |
| Quick tasks | Up to 3 | Excluded |
| Overload threshold | 150% | 120% (stricter) |
| Review intensity | Full | Essential only |

### Minimum version per habit

Each habit defines its own minimum:

```sql
-- View: habit_minimum_diff
SELECT name, expected_count, minimum_count,
       (expected_count - minimum_count) AS reduction
FROM habits
WHERE minimum_count IS NOT NULL
  AND deleted_at IS NULL;
```

### Minimum version per project

Projects can define a minimum scope via their `description` field convention:

```
description: |
  Proyecto: Rastrojero
  Normal: Restauración completa (chapa, pintura, motor, interior)
  Mínimo: Que funcione y esté habilitado para circular
```

The coach reads this convention and adjusts project scope accordingly.

### Deactivation

```
/modo normal
→ Desactiva modo mínimo. Restaura objetivos normales.
→ Si la compliance mejoró, celebra: "Buena semana de recuperación."
→ Si no mejoró, pregunta: "¿Seguimos en modo mínimo o intentamos normal de nuevo?"
```

---

## Streak Policy

**Streaks are NOT the primary metric.** The coach tracks them as context, but:

1. A broken streak is never shamed: "Perdiste tu racha" → ❌. Instead: "Esta semana no se dio, ¿arrancamos de nuevo?"
2. Streaks don't override other signals: a 30-day streak with minimum effort isn't more valuable than 3 days of genuinely good sessions
3. Streaks are supplementary data — compliance %, consistency patterns, and trend direction matter more

---

## Commands Reference

### `/habito`

| Sub-command | Action |
|-------------|--------|
| `/habito` | List all active habits with this week's compliance |
| `/habito crear <name>` | Create a new habit |
| `/habito ver <id\|name>` | Show habit detail + last 4 weeks compliance |
| `/habito registrar <id\|name> --valor <n>` | Record habit completion for today |
| `/habito no <id\|name>` | Mark habit as NOT completed today (for accountability) |
| `/habito editar <id\|name>` | Edit habit properties |
| `/habito pausar <id\|name>` | Archive a habit (soft-delete) |
| `/habito resumen` | Weekly summary of all habits |
| `/habito minimo <id\|name> --valor <n>` | Set minimum count for a habit |

### `/modo`

| Sub-command | Action |
|-------------|--------|
| `/modo minimo` | Activate minimum mode |
| `/modo normal` | Deactivate minimum mode, restore normal targets |
| `/modo` | Show current mode status |

---

## Cross-Skill Contract

### Input from padrino-soul (after inbox classification as `habit`)

```json
{
  "category": "habit",
  "content": "Entrené hoy, 45 minutos",
  "extracted": {
    "habit_name": "Entrenar",
    "value": 45,
    "unit": "minutos",
    "date": "2026-07-05"
  }
}
```

### Events consumed from other skills

| Event | Source | Action |
|-------|--------|--------|
| `task.escalated(id, count)` | padrino-plan | Review escalated task, offer 5 options |
| `task.stalled(id, days)` | padrino-tasks | Flag in stall report |
| `project.stalled(name, days)` | padrino-tasks | Include in weekly review context |
| `plan.overload_detected` | padrino-plan | Consider recommending minimum mode |
| `plan.minimum_activated` | padrino-plan | Sync minimum mode state to daily_checkins |

### Events emitted to other skills

| Event | Consumer | When |
|-------|----------|------|
| `coach.habit_completed(habit_id, date, value)` | padrino-review | Habit entry recorded |
| `coach.compliance_alert(pct)` | padrino-review | Weekly compliance below 40% |
| `coach.minimum_mode_activated` | padrino-plan, padrino-review | Min mode turned on |
| `coach.minimum_mode_deactivated` | padrino-plan, padrino-review | Min mode turned off |
| `coach.stall_report(task_ids)` | padrino-review | 7-day stall detection |

### Database writes

- `habit_entries` — INSERT on habit completion
- `daily_checkins` — UPDATE minimum_mode flag
- `audit_log` — log mode transitions and escalations

---

## Privacy Note

- Habit data is personal behavioral data — never share or surface outside the
  user's own Telegram conversation
- Compliance percentages are relative and should never be presented as absolute
  judgments of character or effort
- The coach never stores assumptions about the user's motivation or discipline
  — only data points (completions, dates, values) and evidence-based observations
