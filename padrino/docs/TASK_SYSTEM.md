# Task System — Padrino Digital

Sistema de gestión de tareas, proyectos y metas de Padrino Digital.

## Estados de Tareas (8)

```
inbox → todo → scheduled → in_progress → done
  ↓        ↓         ↓            ↓         ↓
  └────────┴─────────┴────────────┴─→ blocked → in_progress
  ↓        ↓         ↓            ↓
  └────────┴─────────┴────────────┴─→ waiting → in_progress
  ↓
  └─→ cancelled (cualquier estado puede cancelarse)
```

| Estado | Significado | Transiciones válidas |
|--------|------------|---------------------|
| `inbox` | Recién capturada, sin procesar | → `todo`, `cancelled` |
| `todo` | Lista para hacer, sin fecha | → `scheduled`, `in_progress`, `blocked`, `waiting`, `cancelled` |
| `scheduled` | Agendada para una fecha | → `in_progress`, `todo`, `blocked`, `cancelled` |
| `in_progress` | En ejecución ahora | → `done`, `blocked`, `waiting`, `cancelled` |
| `blocked` | Bloqueada por dependencia | → `in_progress`, `cancelled` |
| `waiting` | Esperando input externo | → `in_progress`, `cancelled` |
| `done` | Completada | (estado final) |
| `cancelled` | Cancelada | (estado final, puede archivarse) |

### Reglas de transición

- `done` y `cancelled` son estados finales (no se puede salir)
- `blocked` → `in_progress` solo cuando `blocked_by` se resolvió
- `waiting` → `in_progress` solo cuando el input externo llegó
- Cualquier estado puede ir a `cancelled`

## Prioridades

Las tareas tienen `priority` (INTEGER, default 0). Mayor número = mayor prioridad.

```
0 — Sin prioridad (default)
1 — Baja
2 — Media
3 — Alta
4 — Crítica
```

## Snooze

Cuando una tarea se pospone, su `snooze_count` se incrementa. Padrino rastrea
los snoozes para detectar patrones de postergación:

| Snoozes | Acción de Padrino |
|---------|------------------|
| 1 | Nota ligera: "Pateaste X. ¿Para cuándo la pasamos?" |
| 2 | Anotación: "Segunda vez que pateás X." |
| 3+ | Escalación: "X se pateó 3 veces en 2 semanas. ¿La redefinimos, delegamos, o cancelamos?" |

## Proyectos

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    status TEXT CHECK(status IN ('active','paused','completed','archived')),
    area TEXT
);
```

| Estado | Significado |
|--------|------------|
| `active` | En progreso |
| `paused` | Pausado temporalmente |
| `completed` | Terminado |
| `archived` | Archivado (no aparece en vistas activas) |

### Áreas de proyecto

- `personal` — Vida personal
- `trabajo` — Trabajo y proyectos freelance
- `finanzas` — Gestión financiera
- `salud` — Salud y bienestar
- `vehiculos` — Rastrojero, mantenimiento
- `hogar` — Casa, reparaciones

## Metas (Goals)

```sql
CREATE TABLE goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    target_value REAL,        -- Meta numérica
    current_value REAL,       -- Valor actual
    unit TEXT,                 -- Unidad (%, kg, $, items)
    project_id INTEGER REFERENCES projects(id),
    deadline TEXT
);
```

Las metas trackean progreso numérico. Ejemplos:
- "Ahorrar $500,000" → `target_value: 500000`, `unit: ARS`
- "Pesar 80kg" → `target_value: 80`, `unit: kg`
- "Completar 10 features de Nexios" → `target_value: 10`, `unit: features`

## Recordatorios (Reminders)

```sql
CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    remind_at TEXT NOT NULL,    -- Cuándo notificar
    recurrence TEXT,            -- Patrón de recurrencia (opcional)
    delivered INTEGER DEFAULT 0 -- 0 = pendiente, 1 = entregado
);
```

Formatos de recurrencia:
- `daily` — Todos los días
- `weekly` — Cada semana mismo día
- `weekdays` — Lunes a viernes
- `monthly` — Cada mes mismo día
- `custom:cron_expression` — Expresión cron personalizada

## Comandos

| Comando | Acción |
|---------|--------|
| `/tareas` | Listar tareas pendientes |
| `/tarea nueva {título}` | Crear tarea |
| `/tarea {id} hacer` | Marcar como in_progress |
| `/tarea {id} lista` | Marcar como done |
| `/tarea {id} cancelar` | Cancelar tarea |
| `/tarea {id} patear` | Snoozear tarea |
| `/proyecto ver {nombre}` | Ver proyecto |
| `/proyecto crear {nombre}` | Crear proyecto |
| `/meta ver` | Ver metas |
| `/meta crear {descripción}` | Crear meta |

## Lenguaje Natural

También podés usar lenguaje natural. `padrino-inbox` clasifica automáticamente:

```
"Tengo que comprar verduras mañana a las 10"
→ Clasifica como: task
→ Crea: title="Comprar verduras", scheduled_at="mañana 10:00"

"Terminé el frontend de Nexios"
→ Clasifica como: project_update
→ Actualiza: project="Nexios", task status="done"
```

## Integración con Otros Skills

- **padrino-plan**: Lee tareas para armar el plan diario
- **padrino-coach**: Lee snooze_count para detectar postergación
- **padrino-review**: Agrega estadísticas de tareas en revisiones
- **padrino-memory**: Registra decisiones sobre proyectos como `type=decision`
