---
name: padrino-review
description: Periodic review engine for Padrino Digital. Daily morning/evening checkins, weekly synthesis, and monthly financial/project retrospectives. Each review is self-contained — queries the database directly, no conversational context needed.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    tags: [padrino, review, checkin, weekly, monthly, retrospective, synthesis]
    related_skills: [padrino-soul, padrino-tasks, padrino-plan, padrino-coach, padrino-finance, padrino-memory]
    commands: [/checkin, /resumen]
    writes_to: [padrino.db]
    reads_from: [padrino.db, padrino/data/memory/]
---

# padrino-review — Periodic Review Engine

## Purpose

Generate structured reviews at daily, weekly, and monthly cadences. Each review
is **self-contained** — it queries the database directly and requires no
conversational context from previous interactions. Reviews synthesize data
across ALL domain skills (tasks, habits, finances, projects, goals, decisions)
into actionable summaries.

## When to Use

- Automatically: cron jobs trigger reviews at fixed times (see schedule below)
- Manually: `/checkin` for daily check-in (morning or evening)
- Manually: `/resumen` for on-demand weekly or monthly review

### Cron Schedule (ART timezone)

| Review | Cron | DB Dedup |
|--------|------|----------|
| Morning summary | `0 8 * * *` | `daily_checkins.morning_delivered = 1` |
| Evening review | `30 21 * * *` | `daily_checkins.evening_delivered = 1` |
| Weekly review | `0 19 * * 0` | Unique `(year, week)` in review output |
| Monthly review | `0 10 1 * *` | Unique `(year, month)` in review output |

All cron prompts are self-contained — they instruct Hermes to query the DB
fresh and ignore any conversation history.

---

## Daily Morning Review (08:00 ART)

### Purpose

Prepare the user for the day ahead. Not a plan generator (that's `padrino-plan`)
— this is the synthesis of what's pending, what's urgent, and what needs
attention.

### Structure

```
🌅 BUEN DÍA — {fecha}

⚡ TUS 3 PRIORIDADES DE HOY
  (from padrino-plan — if plan exists)
  1. [task] — {min} min · {reason}
  2. [task] — {min} min · {reason}
  3. [task] — {min} min · {reason}

📌 COMPROMISOS FIJOS
  • [task] a las 10:00
  • [task] a las 15:30

⚠️ VENCIMIENTOS
  • [task] — vence HOY
  • [task] — vence mañana
  • [debt] — cuota vence el {date}

💰 RECORDATORIOS FINANCIEROS
  • Presupuesto {category}: {spent}/{limit} ({pct}%)
  • Meta de ahorro {name}: {current}/{target} ({pct}%)

🔁 HÁBITOS DE HOY
  • [habit 1] — objetivo: {expected}/sem, vas {completed}
  • [habit 2] — objetivo: {expected}/sem, vas {completed}

🧘 MODO MÍNIMO (si está activo)
  → Recordatorio: estás en modo mínimo. Solo 2 prioridades, objetivos reducidos.

📊 CARGA ESTIMADA: {estimated_hours}h / {available_hours}h disponibles
```

### Queries executed

```sql
-- Today's plan (if generated)
SELECT * FROM daily_checkins WHERE date = date('now');

-- Overdue and due-today tasks
SELECT * FROM tasks
WHERE (due_at = date('now') OR due_at < date('now'))
  AND status NOT IN ('done', 'cancelled')
  AND deleted_at IS NULL
ORDER BY due_at ASC;

-- Habit status for current week
SELECT h.name, h.expected_count,
       COUNT(he.id) AS completed_so_far
FROM habits h
LEFT JOIN habit_entries he ON he.habit_id = h.id
    AND he.date BETWEEN date('now', 'weekday 0', '-7 days')
                    AND date('now')
    AND he.completed = 1
WHERE h.deleted_at IS NULL
GROUP BY h.id;

-- Budget status for current month
SELECT b.category, b.limit_amount,
       COALESCE(SUM(t.amount), 0) AS spent_this_month
FROM budgets b
LEFT JOIN transactions t ON t.category = b.category
    AND t.type = 'expense'
    AND t.date BETWEEN date('now', 'start of month') AND date('now')
    AND t.deleted_at IS NULL
WHERE b.deleted_at IS NULL AND b.active = 1
GROUP BY b.id;

-- Upcoming debt payments (next 7 days)
SELECT * FROM debts
WHERE due_date BETWEEN date('now') AND date('now', '+7 days')
  AND status = 'active'
  AND deleted_at IS NULL;
```

### Dedup guard

Before delivering: `SELECT 1 FROM daily_checkins WHERE date = date('now') AND morning_delivered = 1`. If found, skip delivery.

### Post-delivery

```sql
INSERT INTO daily_checkins (date, morning_delivered)
VALUES (date('now'), 1)
ON CONFLICT(date) DO UPDATE SET morning_delivered = 1;
```

---

## Daily Evening Review (21:30 ART)

### Purpose

Close the day: what was accomplished, what's pending, obstacles encountered,
and preparation for tomorrow.

### Structure

```
🌙 CIERRE DEL DÍA — {fecha}

✅ COMPLETADO HOY
  • [task] — completada
  • [task] — completada
  Total: {N} tareas completadas

📋 PENDIENTE
  • [task] — pospuesta (1 vez)
  • [task] — sin tocar
  Total: {N} tareas pendientes

🚧 OBSTÁCULOS
  • [task] — bloqueada: "{blocked_by}"
  • [task] — esperando respuesta de {context}

💰 ¿GASTOS NO REGISTRADOS?
  → "¿Tuviste algún gasto hoy que no hayas registrado?"
  → Si el usuario dice sí → deriva a padrino-finance

📝 PREPARACIÓN PARA MAÑANA
  • [task] vence mañana — ¿la agendamos?
  • [task] programada para mañana a las 09:00

🔁 HÁBITOS
  • [habit] — completado ✓
  • [habit] — no completado ✗ (¿mañana?)
  Hoy: {completed}/{total} hábitos

💪 ¿CÓMO TE SENTISTE HOY?
  → Pregunta abierta opcional — si el usuario responde, se guarda como journal entry
```

### Queries executed

```sql
-- Tasks completed today (by updated_at or completed_at)
SELECT * FROM tasks
WHERE (date(completed_at) = date('now') OR
       (status = 'done' AND date(updated_at) = date('now')))
  AND deleted_at IS NULL;

-- Tasks NOT done and NOT cancelled
SELECT * FROM tasks
WHERE status IN ('todo', 'scheduled', 'in_progress', 'blocked', 'waiting')
  AND deleted_at IS NULL
  AND snooze_count > 0
ORDER BY priority DESC;

-- Blocked tasks
SELECT * FROM tasks
WHERE status = 'blocked'
  AND deleted_at IS NULL;

-- Today's habit completions
SELECT h.name, he.completed, he.value, he.notes
FROM habit_entries he
JOIN habits h ON h.id = he.habit_id
WHERE he.date = date('now');
```

### Dedup guard

`SELECT 1 FROM daily_checkins WHERE date = date('now') AND evening_delivered = 1`

### Post-delivery

```sql
INSERT INTO daily_checkins (date, evening_delivered, completed_tasks, pending_tasks)
VALUES (date('now'), 1, {completed_count}, {pending_count})
ON CONFLICT(date) DO UPDATE SET
    evening_delivered = 1,
    completed_tasks = {completed_count},
    pending_tasks = {pending_count};
```

---

## Weekly Review (Domingo 19:00 ART)

### Purpose

Full-week synthesis: what was achieved, patterns emerging, adjustments needed
for next week.

### Structure

```
📊 REVISIÓN SEMANAL — Semana {N} ({start_date} → {end_date})

🏆 LOGROS DE LA SEMANA
  • Completadas: {N} tareas
  • Proyectos con avance: {N}
  • Metas con progreso: {N}

📋 TAREAS
  Completadas: {N} | Pospuestas: {N} | Creadas: {N}
  
  Posiciones repetidas:
  • [task] — pospuesta {count} veces esta semana
  • [task] — pospuesta {count} veces esta semana

🔴 PROYECTOS ESTANCADOS
  • [project] — sin actividad en {days} días
  • [project] — sin actividad en {days} días

🔁 HÁBITOS — CUMPLIMIENTO SEMANAL
  | Hábito          | Objetivo | Completado | %     |
  |-----------------|----------|------------|-------|
  | Entrenar        | 5/sem    | 3          | 60%   |
  | Leer            | 5/sem    | 5          | 100%  |
  | Meditar         | 7/sem    | 4          | 57%   |
  
  Cumplimiento general: {avg_pct}%
  {if <40%: "⚠️ Por debajo del 40% — considerar modo mínimo"}

💰 FINANZAS
  Ingresos: ${total_income}
  Gastos: ${total_expenses}
  Balance: ${balance}
  
  Presupuestos:
  | Categoría  | Gastado | Límite  | %     |
  |------------|---------|---------|-------|
  | Comida     | $45,000 | $100,000| 45%   |
  | Salidas    | $55,000 | $50,000 | 110% ⚠️|
  
  Ahorros:
  | Meta              | Actual     | Objetivo   | %     |
  |-------------------|------------|------------|-------|
  | Fondo emergencia  | $150,000   | $500,000   | 30%   |
  
  Deudas:
  | Deuda            | Restante   | Total      | Estado  |
  |------------------|------------|------------|---------|
  | Préstamo auto    | $45,000    | $200,000   | activa  |

🩺 PROBLEMAS DETECTADOS
  • [task] — pospuesta 4 veces → considerar redefinir o cerrar
  • [habit] — 2 semanas consecutivas por debajo del 50%
  • [budget] — excedido por 2da semana

💡 RECOMENDACIONES
  • Reducir carga: tenés {open_tasks} tareas abiertas, {stalled} sin avance
  • {if compliance < 40%: "Activar modo mínimo para la semana que viene"}
  • Proyecto {name}: definir próximo hito concreto
  • Hábito {name}: ¿bajamos el objetivo a {minimum} por ahora?

🎯 PRIORIDAD PARA LA SEMANA QUE VIENE
  → 1 objetivo principal: {suggestion}
  → 1 hábito a reforzar: {suggestion}
  → 1 cosa a dejar de hacer: {suggestion}
```

### Queries executed

```sql
-- Weekly task stats
SELECT
    COUNT(*) FILTER (WHERE status = 'done' AND date(completed_at) BETWEEN '{start}' AND '{end}') AS completed,
    COUNT(*) FILTER (WHERE snooze_count > 0 AND date(last_snoozed_at) BETWEEN '{start}' AND '{end}') AS snoozed,
    COUNT(*) FILTER (WHERE date(created_at) BETWEEN '{start}' AND '{end}') AS created
FROM tasks WHERE deleted_at IS NULL;

-- Habit compliance per habit
SELECT h.name, h.expected_count,
       COUNT(he.id) FILTER (WHERE he.completed = 1) AS completed,
       ROUND(CAST(COUNT(he.id) FILTER (WHERE he.completed = 1) AS REAL) / h.expected_count * 100, 0) AS pct
FROM habits h
LEFT JOIN habit_entries he ON he.habit_id = h.id
    AND he.date BETWEEN '{start}' AND '{end}'
WHERE h.deleted_at IS NULL
GROUP BY h.id;

-- Financial summary
SELECT
    COALESCE(SUM(amount) FILTER (WHERE type = 'income'), 0) AS total_income,
    COALESCE(SUM(amount) FILTER (WHERE type = 'expense'), 0) AS total_expenses
FROM transactions
WHERE date BETWEEN '{start}' AND '{end}'
  AND deleted_at IS NULL;

-- Budget status
SELECT b.category, b.limit_amount,
       COALESCE(SUM(t.amount), 0) AS spent
FROM budgets b
LEFT JOIN transactions t ON t.category = b.category
    AND t.type = 'expense'
    AND t.date BETWEEN date('now', 'start of month') AND date('now')
    AND t.deleted_at IS NULL
WHERE b.deleted_at IS NULL AND b.active = 1
GROUP BY b.id;

-- Stalled projects
SELECT p.name, p.updated_at,
       CAST(julianday('now') - julianday(p.updated_at) AS INTEGER) AS days_since_activity
FROM projects p
WHERE p.status = 'active'
  AND julianday('now') - julianday(p.updated_at) >= 7
ORDER BY days_since_activity DESC;

-- Savings progress
SELECT name, current_amount, target_amount,
       ROUND(current_amount / target_amount * 100, 0) AS pct
FROM savings_goals
WHERE status = 'active' AND deleted_at IS NULL;

-- Debt status
SELECT name, remaining_amount, total_amount, status, due_date
FROM debts
WHERE status = 'active' AND deleted_at IS NULL;
```

---

## Monthly Review (Día 1, 10:00 ART)

### Purpose

Broader retrospective: financial evolution, goal trajectories, project health,
habit trends, and strategic decisions.

### Structure

```
📈 REVISIÓN MENSUAL — {month} {year}

💰 EVOLUCIÓN FINANCIERA
  Ingresos: ${total_income} (mes anterior: ${prev_income})
  Gastos: ${total_expenses} (mes anterior: ${prev_expenses})
  Balance: ${balance} (Δ {delta} vs mes anterior)
  
  Por área de negocio:
  | Área        | Ingresos   | Gastos     | Neto       |
  |-------------|------------|------------|------------|
  | Personal    | $X         | $Y         | $Z         |
  | Nexios      | $X         | $Y         | $Z         |
  | Ascend      | $X         | $Y         | $Z         |
  | Fletes      | $X         | $Y         | $Z         |
  | Rastrojero  | $X         | $Y         | $Z         |
  | Home-gym    | $X         | $Y         | $Z         |
  | Otros       | $X         | $Y         | $Z         |

  Por categoría:
  | Categoría    | Gastos     | Presupuesto | %     |
  |--------------|------------|-------------|-------|
  | ...          | ...        | ...         | ...   |

🎯 METAS — PROGRESO
  | Meta              | Progreso   | Objetivo   | %     | Fecha límite | Estado   |
  |-------------------|------------|------------|-------|-------------|----------|
  | Ahorrar 500k      | $200,000   | $500,000   | 40%   | 2026-12-31  | En curso |
  | Leer 12 libros    | 4/12       | 12         | 33%   | 2026-12-31  | Atrasado ⚠️|

📁 PROYECTOS ACTIVOS
  | Proyecto    | Estado  | Última actividad | Tareas abiertas |
  |-------------|---------|-----------------|-----------------|
  | Nexios      | activo  | hace 2 días     | 5               |
  | Rastrojero  | activo  | hace 15 días    | 3 ⚠️            |

  Proyectos a considerar pausar:
  • [project] — sin avance significativo en 30 días
  • [project] — sin tareas completadas este mes

🔁 HÁBITOS — TENDENCIA MENSUAL
  | Hábito    | Sem 1 | Sem 2 | Sem 3 | Sem 4 | Tendencia |
  |-----------|-------|-------|-------|-------|-----------|
  | Entrenar  | 60%   | 80%   | 40%   | 20%   | 📉         |
  | Leer      | 100%  | 100%  | 100%  | 100%  | →         |

💳 DEUDAS
  | Deuda            | Pagado   | Restante  | Total     | %     | Estado  |
  |------------------|----------|-----------|-----------|-------|---------|
  | Préstamo auto    | $155,000 | $45,000   | $200,000  | 77%   | activa  |

🏦 AHORROS
  | Meta              | Actual    | Objetivo  | %     | Aporte mensual |
  |-------------------|-----------|-----------|-------|----------------|
  | Fondo emergencia  | $150,000  | $500,000  | 30%   | $25,000        |

📋 DECISIONES DEL MES
  • [decision] — {date}: "{chosen}" → {status}
  • [decision] — {date}: "{chosen}" → {status}

📊 COMPARACIÓN MES ANTERIOR
  | Métrica              | Este mes | Mes anterior | Δ      |
  |----------------------|----------|-------------|--------|
  | Tareas completadas   | 45       | 38          | +18%   |
  | Cumplimiento hábitos | 62%      | 71%         | -9%    |
  | Gastos totales       | $85,000  | $92,000     | -8%    |
  | Ingresos totales     | $120,000 | $110,000    | +9%    |
  | Balance              | +$35,000 | +$18,000    | +94%   |

💡 RECOMENDACIONES PARA EL MES QUE VIENE
  • ...
```

---

## Self-Contained Operation

Every review type MUST operate without conversational context. This means:

1. **No memory of past conversations**: the review prompt is a complete,
   standalone instruction
2. **Fresh DB queries**: every data point is queried from `padrino.db` at
   review time — nothing is cached from chat history
3. **No assumptions about user state**: the review discovers mode, energy,
   and availability from `daily_checkins`, not from "what we talked about
   earlier"
4. **Idempotent**: running the same review twice produces the same result
   (except for `delivered` flags that prevent double-delivery)

### Cron prompt template (morning review example)

```
"Generá el resumen matutino para hoy (fecha actual). Consultá la base de datos
padrino.db para obtener:

1. El plan del día desde daily_checkins (si existe)
2. Tareas que vencen hoy o están vencidas
3. Estado de hábitos para esta semana
4. Presupuestos activos y su estado actual
5. Próximos vencimientos de deudas (7 días)
6. Modo mínimo activo (si corresponde)

Formateá la respuesta con emojis de sección (🌅 ⚡ 📌 ⚠️ 💰 🔁 🧘 📊).
NO uses contexto de conversaciones anteriores. Solo datos frescos de la DB."
```

---

## Check-in Flow

### `/checkin`

Records the user's availability and energy for the day, then triggers a plan
regeneration.

```
/checkin
→ "¿Cuántas horas tenés disponibles hoy?"
→ User: "5"
→ "¿Cómo está tu energía? (alta / media / baja)"
→ User: "media"
→ INSERT/UPDATE daily_checkins
→ Trigger padrino-plan regeneration with new availability

/checkin --horas 5 --energia media
→ Direct checkin with all parameters
→ Skip the Q&A flow
```

---

## Commands Reference

### `/checkin`

| Sub-command | Action |
|-------------|--------|
| `/checkin` | Interactive check-in (hours + energy) |
| `/checkin --horas <n> --energia <alta\|media\|baja>` | Direct check-in |
| `/checkin --minimo` | Check-in with minimum mode activated |

### `/resumen`

| Sub-command | Action |
|-------------|--------|
| `/resumen` | Defaults to weekly review for current week |
| `/resumen semanal` | Weekly review |
| `/resumen mensual` | Monthly review |
| `/resumen semanal --semana <N>` | Weekly review for a specific week |
| `/resumen mensual --mes <N> --año <YYYY>` | Monthly review for a specific month |

---

## Cross-Skill Contract

### Events consumed from other skills

| Event | Source | Used in |
|-------|--------|---------|
| `plan.generated` | padrino-plan | Morning review |
| `plan.confirmed` | padrino-plan | Morning review update |
| `task.snoozed(id, count)` | padrino-tasks | Evening + weekly reviews |
| `task.completed(id)` | padrino-tasks | Evening + weekly reviews |
| `task.stalled(id, days)` | padrino-tasks | Weekly + monthly reviews |
| `coach.habit_completed(...)` | padrino-coach | Evening + weekly reviews |
| `coach.compliance_alert(pct)` | padrino-coach | Weekly review |
| `coach.minimum_mode_activated` | padrino-coach | All reviews |
| `goal.progress(id, pct)` | padrino-tasks | Monthly review |
| `finance.budget_warning(category, pct)` | padrino-finance | Morning + weekly reviews |
| `project.stalled(name, days)` | padrino-tasks | Weekly + monthly reviews |

### Events emitted

| Event | Consumer | When |
|-------|----------|------|
| `review.morning_delivered` | padrino-soul | Morning cron completes |
| `review.evening_delivered` | padrino-soul | Evening cron completes |
| `review.weekly_delivered` | padrino-soul | Weekly cron completes |
| `review.monthly_delivered` | padrino-soul | Monthly cron completes |
| `review.recommendation(action)` | padrino-coach | Recommendations requiring coach action |

### Output to padrino-soul (for Telegram formatting)

The review returns a fully formatted markdown response ready for Telegram
delivery. No additional formatting is applied by `padrino-soul` — the review
controls its own presentation.

---

## Privacy Note

- Reviews aggregate personal financial data, task lists, and behavioral
  patterns — all data stays in `padrino.db`, never leaves the server
- Review summaries delivered via Telegram may be visible on screen — the
  user should be mindful of their environment
- Review cron prompts are self-contained and never include personal data
  from previous conversations
- Monthly reviews contain the most sensitive aggregation (full financial
  picture) — consider offering to send these as encrypted messages
