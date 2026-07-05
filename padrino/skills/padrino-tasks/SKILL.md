---
name: padrino-tasks
description: Task, project, and goal management for Padrino Digital. Full lifecycle with 8 statuses, project CRUD, goal tracking with progress, reminder management, and duplicate detection.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    tags: [padrino, tasks, projects, goals, reminders, lifecycle]
    related_skills: [padrino-soul, padrino-inbox, padrino-memory, padrino-plan, padrino-coach]
    commands: [/tareas, /proyecto, /meta]
    writes_to: [padrino.db]
---

# padrino-tasks — Task, Project & Goal Management

## Purpose

Manage the full lifecycle of tasks, projects, and goals. This skill is the
single source of truth for everything the user needs to do, track, or achieve.

## When to Use

- Automatically: when `padrino-inbox` classifies a message as `task`, `idea`,
  `goal`, `reminder`, or `project_update`
- Manually: `/tareas`, `/proyecto`, `/meta` commands and their sub-commands

---

## Task Management

### Task Lifecycle

Tasks move through 8 statuses following a defined lifecycle:

```
inbox → todo → scheduled → in_progress → done
                       ↓          ↓
                    blocked    cancelled
                       ↓
                    waiting
```

### Status definitions

| Status | Meaning | When to use |
|--------|---------|-------------|
| `inbox` | Unprocessed, not yet reviewed | Default for new tasks from inbox classifier |
| `todo` | Reviewed, confirmed as actionable, not yet scheduled | After user confirms the task |
| `scheduled` | Has a specific date/time to work on it | When `scheduled_at` is set |
| `in_progress` | Currently working on it | User marks as started |
| `blocked` | Cannot proceed — dependency or external blocker | Something outside user's control |
| `waiting` | Waiting for someone else's input/action | Delegated or dependent on third party |
| `done` | Completed successfully | User confirms completion |
| `cancelled` | No longer relevant or needed | User decides not to do it |

### Valid transitions

```
FROM            → TO (allowed)
─────────────────────────────────────────
inbox           → todo, cancelled
todo            → scheduled, in_progress, cancelled
scheduled       → in_progress, todo, cancelled
in_progress     → done, blocked, waiting, todo
blocked         → in_progress, todo, waiting, cancelled
waiting         → in_progress, todo, blocked, cancelled
done            → [terminal — cannot transition, create new task if needed]
cancelled       → [terminal — cannot transition, create new task if needed]
```

### Invalid transitions (blocked)

| Attempt | Rejection reason |
|---------|-----------------|
| done → todo | "Las tareas completadas no pueden volver a 'pendiente'. Creá una tarea nueva si necesitás rehacer algo." |
| cancelled → todo | "Las tareas canceladas no se reactivan. Creá una nueva si cambiaste de opinión." |
| done → cancelled | "No se puede cancelar algo que ya está completado." |
| inbox → done | "Pasá la tarea por 'pendiente' primero para confirmar que querés hacerla." |
| inbox → in_progress | "Revisá la tarea primero — ¿está confirmada como pendiente?" |

### Task properties

Every task has:

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Short, actionable description |
| `description` | No | Details, context, acceptance criteria |
| `status` | Yes | One of the 8 lifecycle statuses |
| `priority` | No | 0 (none) to 5 (critical) |
| `project_id` | No | Link to a project |
| `goal_id` | No | Link to a goal |
| `due_at` | No | Hard deadline (YYYY-MM-DD) |
| `scheduled_at` | No | When to work on it (YYYY-MM-DD or datetime) |
| `estimated_minutes` | No | How long it should take |
| `actual_minutes` | No | How long it actually took (set on done) |
| `snooze_count` | Auto | Incremented on each snooze |
| `last_snoozed_at` | Auto | Timestamp of last snooze |
| `source` | Auto | Where the task came from (Telegram, manual, system) |
| `tags` | No | JSON array of tags |
| `blocked_by` | No | What's blocking this task |
| `energy_required` | No | `high`, `medium`, `low`, `any` — for daily planning |

### Creating a task

```
User: "Tengo que llamar al mecánico"
→ inbox classifies as task (confidence: high)
→ padrino-tasks creates:
    title: "Llamar al mecánico"
    status: inbox
    source: "telegram"
    created_at: now()

Padrino: "Creé la tarea 'Llamar al mecánico' en la bandeja de entrada.
         ¿Querés asignarle fecha, prioridad, o proyecto?"
```

### Snooze tracking

When a task is postponed:

1. `snooze_count` increments by 1
2. `last_snoozed_at` updates to current timestamp
3. If `snooze_count >= 3` → flag for `padrino-coach` accountability review
4. Suggested new date is recorded in `scheduled_at`

```
User: "Pateá la llamada al mecánico para la semana que viene"
Padrino: "Tarea 'Llamar al mecánico' pospuesta (snooze #2).
         Nueva fecha sugerida: 2026-07-12. ¿Confirmás?"
```

### Duplicate detection

Before creating a task, check for duplicates:

1. Search for tasks with similar titles (FTS5 or LIKE on `title`)
2. If found with status `inbox`, `todo`, or `scheduled`:
   ```
   Padrino: "Ya tenés una tarea similar: 'Llamar al mecánico del Rastrojero'
            (pendiente desde 2026-06-28). ¿Es la misma? ¿La actualizo?"
   ```
3. If user confirms it's the same → update existing task
4. If user says it's different → create new task with distinct title

---

## Project Management

### Project lifecycle

```
active → paused → active
active → completed
active → archived
paused → active
paused → archived
completed → [terminal]
archived → [terminal]
```

### Creating a project

```
User: /proyecto crear home-gym
Padrino: "Creo el proyecto 'home-gym'.
         ¿En qué área va? (personal, health-and-training, otro)
         ¿Cada cuánto querés que lo revise? (semanal, quincenal, mensual)"
```

### Project CRUD

| Command | Action |
|---------|--------|
| `/proyecto` | List all active projects with task counts |
| `/proyecto crear <name>` | Create new project |
| `/proyecto ver <name>` | Show project details, tasks, goals, last review |
| `/proyecto pausar <name>` | Pause project (tasks remain, no reminders) |
| `/proyecto completar <name>` | Mark project complete |
| `/proyecto archivar <name>` | Archive project (soft delete) |

### Project review

Projects with `review_frequency` set are flagged during reviews:
- `weekly`: flagged every Sunday
- `biweekly`: flagged every other Sunday
- `monthly`: flagged first Sunday of month
- `daily`: flagged every evening review
- `none`: never auto-flagged

---

## Goal Management

### Goal properties

| Field | Required | Description |
|-------|----------|-------------|
| `description` | Yes | What the goal is |
| `target_value` | No | The target number |
| `current_value` | Auto | Starts at 0, updated as progress is recorded |
| `measurement_unit` | No | ARS, USD, kg, pages, hours, etc. |
| `project_id` | No | Link to a project |
| `deadline` | No | When to achieve it by |
| `status` | Yes | active, paused, completed, abandoned |

### Creating a goal

```
User: /meta crear "Ahorrar 500000 ARS" --objetivo 500000 --unidad ARS --fecha 2026-12-31
→ Creates goal with target=500000, current=0, unit=ARS, deadline=2026-12-31

Padrino: "Meta creada: Ahorrar $500,000 ARS para el 2026-12-31.
         Progreso: $0/$500,000 (0%). ¿Querés vincularla a un proyecto?"
```

### Recording progress

```
User: /meta avanzar 1 --valor 50000
→ Updates goal #1 current_value to 50000
→ Reports: "Meta 'Ahorrar 500000 ARS': $50,000/$500,000 (10%)"
```

### Goal alerts

Goals approaching deadlines without sufficient progress are flagged:

```
Padrino: ⚠️ La meta 'Ahorrar 500000 ARS' vence en 14 días y está al 10%.
         Al ritmo actual necesitarías 140 días más. ¿Ajustamos el plan o la fecha?
```

---

## Reminder Management

### Creating a reminder

```
User: "Recordame pagar la luz el 10 de julio"
→ inbox → task → if has date → also creates reminder

INSERT INTO reminders (title, remind_at, task_id) VALUES (...)
```

### Reminder delivery

1. Cron or system checks `reminders` table: `WHERE remind_at <= now() AND delivered = 0`
2. Delivered reminders auto-mark `delivered = 1`, `delivered_at = now()`
3. Recurring reminders: `recurrence` field specifies pattern; after delivery,
   calculate next `remind_at` and create new undelivered reminder

### Recurrence formats

| Pattern | `recurrence` value |
|---------|-------------------|
| Daily | `daily` |
| Weekly | `weekly` |
| Monthly | `monthly` |
| Every N days | `every:N:days` |
| Specific weekdays | `weekdays:1,3,5` (Mon, Wed, Fri) |

---

## Commands Reference

### `/tareas`

| Sub-command | Action |
|-------------|--------|
| `/tareas` | List today's tasks (sorted by priority) |
| `/tareas todas` | List all non-done, non-cancelled tasks |
| `/tareas crear <title>` | Create task directly (bypass inbox) |
| `/tareas ver <id>` | Show task details |
| `/tareas hacer <id>` | Move to in_progress |
| `/tareas completar <id>` | Move to done |
| `/tareas cancelar <id>` | Move to cancelled |
| `/tareas posponer <id>` | Snooze task |
| `/tareas bloquear <id> --por <reason>` | Block task |
| `/tareas prioridad <id> <0-5>` | Set priority |
| `/tareas buscar <query>` | Search tasks by title or description |
| `/tareas proyecto <name>` | List tasks for a project |

### `/proyecto`

| Sub-command | Action |
|-------------|--------|
| `/proyecto` | List active projects |
| `/proyecto crear <name>` | Create project |
| `/proyecto ver <name>` | Project overview |
| `/proyecto editar <name> --area <area>` | Update project |
| `/proyecto pausar <name>` | Pause project |
| `/proyecto reanudar <name>` | Resume paused project |
| `/proyecto completar <name>` | Mark complete |
| `/proyecto archivar <name>` | Archive |

### `/meta`

| Sub-command | Action |
|-------------|--------|
| `/meta` | List active goals with progress |
| `/meta crear <desc>` | Create goal |
| `/meta ver <id>` | Goal details |
| `/meta avanzar <id> --valor <n>` | Record progress |
| `/meta completar <id>` | Mark as completed |
| `/meta abandonar <id>` | Abandon goal |
| `/meta proyecto <name>` | List goals for a project |

## Cross-Skill Contract

### Input from padrino-soul (after inbox classification)

```json
{
  "category": "task|idea|goal|reminder|project_update",
  "content": "raw message text",
  "extracted": { "title": "...", "date": "...", "project": "...", "amount": {...} }
}
```

### Events emitted to other skills

| Event | Consumer | When |
|-------|----------|------|
| `task.snoozed(id, count)` | padrino-coach | Snooze count ≥ 3 |
| `task.created(id)` | padrino-plan | New task added |
| `task.completed(id)` | padrino-review | Task moved to done |
| `goal.progress(id, pct)` | padrino-review | Goal progress updated |
| `project.stalled(name, days)` | padrino-coach | No activity in review period |

## Privacy Note

- Task titles and descriptions may contain personal information — the
  `padrino.db` file should always have 600 permissions
- When showing task lists via Telegram, be mindful that others might see the
  screen — offer to send details privately if content is sensitive
