---
name: padrino-plan
description: Daily planning engine for Padrino Digital. Multi-criteria task ranking, max 3 priorities, overload detection, provisional plans, minimum-mode cap, and integration with tasks DB and daily checkins.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    tags: [padrino, planning, priorities, scheduling, daily, overload]
    related_skills: [padrino-soul, padrino-tasks, padrino-coach, padrino-review]
    commands: [/plan, /hoy]
    writes_to: [padrino.db]
    reads_from: [padrino.db]
---

# padrino-plan — Daily Planning Engine

## Purpose

Generate daily plans with a maximum of 3 main priorities. Use multi-criteria
ranking over the task backlog to select what matters most, detect overload
before the day starts, and provide provisional plans when the user hasn't
checked in yet.

This skill is the daily decision engine — it doesn't manage tasks (that's
`padrino-tasks`), but it decides which ones deserve attention today.

## When to Use

- Automatically: morning cron job at 08:00 ART generates the daily plan
- Automatically: when the user checks in with available hours and energy level
- Manually: `/plan` (generate or regenerate the daily plan)
- Manually: `/hoy` (show today's plan, no regeneration)

---

## Multi-Criteria Ranking

The planner ranks candidate tasks using these criteria, in order of weight:

### Primary criteria (weighted)

| # | Criterion | Source | How it affects ranking |
|---|-----------|--------|------------------------|
| 1 | **Due date** | `tasks.due_at` | Due today = highest boost. Overdue = critical boost. Due tomorrow = medium boost. |
| 2 | **Priority** | `tasks.priority` (0-5) | Priority 5 → +100%, 4 → +80%, 3 → +50%, 2 → +20%, 1 → +10%, 0 → no boost |
| 3 | **Impact** | Inferred from project area, goal linkage, description keywords | Tasks linked to active goals or high-value projects get a boost |
| 4 | **Urgency** | Due date proximity + external signals | If a task has `blocked_by` referencing a task that just unblocked → urgency spike |
| 5 | **Snooze count** | `tasks.snooze_count` | snooze_count ≥ 3 → forced into priorities. 1-2 → warning but not forced. 0 → neutral. |
| 6 | **Dependencies** | `tasks.blocked_by` | Blocked tasks are excluded from ranking entirely until unblocked |
| 7 | **Time available** | `daily_checkins.available_hours` | Tasks whose `estimated_minutes` fit within available hours score higher |
| 8 | **Energy match** | `tasks.energy_required` vs `daily_checkins.energy_level` | High-energy tasks when energy=low → deprioritized |
| 9 | **Area balance** | `projects.area` vs previous days' selections | Avoid assigning 3 tasks from the same area in one day |
| 10 | **Commitments** | Tasks with `scheduled_at` = today or explicit promises | Scheduled tasks are non-negotiable and always included |
| 11 | **Blocked tasks** | `tasks.status = 'blocked'` | Excluded from ranking — cannot be worked on |

### Secondary factors (tiebreakers)

- Tasks that were in yesterday's plan but not completed → small boost
- Tasks that advance a goal with a deadline within 14 days → medium boost
- Tasks with `estimated_minutes ≤ 30` can be added as "quick tasks" beyond the 3-priority cap

---

## Plan Structure

Every daily plan has these sections:

```
📅 PLAN DEL DÍA — {fecha}

⚡ PRIORIDADES PRINCIPALES (máx. 3)
  1. [task title] — {estimated_minutes} min · {reason: vence hoy, alto impacto, etc.}
  2. [task title] — {estimated_minutes} min · {reason}
  ...

⚡ RÁPIDAS (si hay tiempo)
  • [quick task 1] — 15 min
  • [quick task 2] — 10 min

📌 COMPROMISOS FIJOS
  • [scheduled task 1] — 14:00-15:00
  • [scheduled task 2] — 18:00

⚠️ VENCIDAS (no incluídas por falta de tiempo)
  • [overdue task] — {estimated_minutes} min · Vencía {date}

🧘 MODO MÍNIMO (si está activo)
  → Solo 2 prioridades. Versiones reducidas de hábitos/proyectos.

📊 CARGA DEL DÍA
  • Horas disponibles: {X}h
  • Horas estimadas: {Y}h
  • Estado: ✅ Carga normal / ⚠️ Sobrecarga / 🔴 Crítico
```

### Plan states

| State | Label | Meaning |
|-------|-------|---------|
| `provisional` | "Plan provisional — sujeto a tu confirmación" | Generated without availability data |
| `confirmed` | "Plan del día — confirmado" | User has confirmed or adjusted the plan |
| `minimum` | "Plan del día — modo mínimo" | Reduced to 2 priorities |

---

## Daily Plan Generation Algorithm

### Step 1: Gather candidate tasks

```sql
SELECT * FROM tasks
WHERE status IN ('todo', 'scheduled', 'in_progress')
  AND deleted_at IS NULL
  AND archived_at IS NULL
ORDER BY priority DESC, due_at ASC
```

### Step 2: Exclude blocked tasks

Remove any task where `status = 'blocked'` or `blocked_by` references an
unresolved dependency.

### Step 3: Check for scheduled commitments

Tasks with `scheduled_at` = today are non-negotiable. They consume time from
the available pool first. If `scheduled_at` has a time component, that slot is
reserved.

### Step 4: Check for overdue tasks

Tasks where `due_at < today` AND `status != 'done'` get a critical boost.
If multiple overdue tasks exist, rank them by `priority` then `due_at`.

### Step 5: Apply multi-criteria scoring

Score each candidate and sort descending.

### Step 6: Select top 3 (or 2 in minimum mode)

Take the top-scoring tasks up to the cap. If `daily_checkins.minimum_mode = 1`,
cap at 2.

### Step 7: Calculate total estimated time

Sum `estimated_minutes` of selected priorities + scheduled commitments.
Compare against `daily_checkins.available_hours` × 60.

### Step 8: Overload detection

| Condition | Action |
|-----------|--------|
| Total estimated ≤ available | ✅ Carga normal. Present plan. |
| Total estimated > available, ≤ 150% | ⚠️ Sobrecarga. Warn user: "Tenés {Y}h estimadas pero solo {X}h disponibles. ¿Ajustamos?" |
| Total estimated > 150% of available | 🔴 Crítico. Force user choice: "Hay {Y}h de tareas para {X}h disponibles. Elegí cuáles van." |
| Available hours unknown | Estado `provisional`. Show plan but prompt for availability. |

---

## Provisional Plan

When `daily_checkins.available_hours` is NULL (morning cron runs before user
checks in), the plan is generated as provisional:

1. **Label**: "📅 Plan provisional — sujeto a tu confirmación"
2. **Prompt**: "¿Cuántas horas tenés disponibles hoy?"
3. **Behavior**: The plan is fully generated but marked tentative.
4. **Adjustment**: When the user responds with availability:
   - If "Tengo X horas" → recalculate load, adjust if needed
   - If "Confirmado" → accept plan as-is if load permits
   - If "Hoy no puedo hacer A, prioridad es B y C" → regenerate with user overrides

### Provisional plan transitions

```
provisional → confirmed  (user accepts or adjusts)
provisional → minimum    (user says "modo mínimo hoy")
provisional → regenerated (user provides new constraints)
```

---

## Minimum Mode Integration

When `daily_checkins.minimum_mode = 1` (set by `padrino-coach` or manually):

- Cap priorities at **2** instead of 3
- Each priority uses its minimum version if defined in project/habit metadata
- Quick tasks are excluded — focus only on essentials
- Estimated time is recalculated using minimum versions
- No new projects or goals can be started in minimum mode

---

## Quick Tasks

Tasks with `estimated_minutes ≤ 30` AND `energy_required != 'high'` can be
classified as "quick tasks" that don't count against the 3-priority cap:

- Max 3 quick tasks per day
- Listed under "⚡ RÁPIDAS" section
- Not included in overload calculation (they fit in gaps)
- Excluded entirely in minimum mode

---

## Postponed Task Handling

### Snooze annotations in plan

| snooze_count | Annotation |
|-------------|------------|
| 1 | "(pospuesto 1 vez)" |
| 2 | "(pospuesto 2 veces)" |
| 3+ | "⚠️ Pospuesto {count} veces — ¿seguimos postergando o lo resolvemos?" |

### Escalation rule

When `snooze_count ≥ 3`:
1. The task is flagged in the plan with the ⚠️ warning
2. An event `task.escalated` is emitted to `padrino-coach`
3. The task is FORCED into priorities (not merely suggested)
4. `padrino-coach` reviews it for redefinition, breakdown, delegation, or closure

---

## Due Date Urgency Override

Even if a task has `snooze_count ≥ 2`, if `due_at = today`, it is forced into
main priorities regardless of snooze count. The plan displays both the snooze
warning AND the due-today urgency flag:

```
⚡ 2. [task title] — 45 min · VENCE HOY ⚠️ Pospuesto 2 veces
```

---

## Overload Warning Detail

When the planner detects overload, it does NOT silently choose which tasks to
drop. Instead:

```
⚠️ SOBRECARGA DETECTADA

Hoy tenés {total_estimated}h estimadas de tareas con fecha límite,
pero solo {available_hours}h disponibles.

Las siguientes tareas no entran:
  • [task 4] — {min} min · {reason}
  • [task 5] — {min} min · {reason}

¿Cuáles querés priorizar?
  1. Mantener las 3 actuales y posponer el resto
  2. Cambiar prioridad: "Cambio [X] por [Y]"
  3. Activar modo mínimo (solo 2 prioridades)
```

---

## Commands Reference

### `/hoy`

Shows today's plan without regenerating. Just reads the current state.

```
/hoy
→ Muestra el plan del día actual (provisional, confirmado, o mínimo)
→ Si no hay plan generado, sugiere "/plan" para generar uno
```

### `/plan`

Generates (or regenerates) the daily plan.

```
/plan
→ Genera un plan nuevo basado en el ranking multi-criterio
→ Si ya existe un plan para hoy, pregunta: "Ya hay un plan para hoy. ¿Querés reemplazarlo?"

/plan minimo
→ Genera plan con máximo 2 prioridades (modo mínimo)

/plan --horas 5 --energia media
→ Genera plan con 5 horas disponibles y energía media
→ Equivalente a hacer el checkin y planificar en un solo paso
```

---

## Cross-Skill Contract

### Input from padrino-soul (after inbox classification or command)

```json
{
  "command": "plan|hoy",
  "action": "generate|show|adjust",
  "parameters": {
    "available_hours": 5,
    "energy_level": "medium",
    "minimum_mode": false,
    "user_overrides": null
  }
}
```

### Queries to padrino.db

The planner reads from:
- `tasks` — candidate pool (WHERE status IN ('todo','scheduled','in_progress'))
- `projects` — area grouping for balance
- `goals` — deadline proximity for impact scoring
- `daily_checkins` — today's available_hours, energy_level, minimum_mode
- `habit_entries` — today's habits (for time consumption estimation)

### Events emitted to other skills

| Event | Consumer | When |
|-------|----------|------|
| `plan.generated` | padrino-review | Plan created for today |
| `plan.confirmed` | padrino-review | User confirms provisional plan |
| `plan.overload_detected` | padrino-coach | Overload warning triggered |
| `task.escalated` | padrino-coach | Snooze count reaches 3+ |
| `plan.minimum_activated` | padrino-coach | Minimum mode activated |

### Output to padrino-soul (for Telegram formatting)

```json
{
  "plan_id": "2026-07-05",
  "state": "confirmed",
  "priorities": [
    {"id": 42, "title": "...", "estimated_minutes": 60, "reason": "vence hoy"},
    {"id": 15, "title": "...", "estimated_minutes": 45, "reason": "alto impacto"}
  ],
  "quick_tasks": [
    {"id": 88, "title": "...", "estimated_minutes": 15}
  ],
  "commitments": [
    {"title": "...", "time": "14:00"}
  ],
  "overdue_flagged": [],
  "load": {"available_hours": 5, "estimated_hours": 2.5, "status": "normal"},
  "minimum_mode": false
}
```

---

## Privacy Note

- The daily plan may contain personal task titles and project names visible on
  the user's Telegram screen — be mindful of screen privacy
- Plan data is stored in `daily_checkins` and task statuses in `padrino.db`;
  no plan data is written to external services
