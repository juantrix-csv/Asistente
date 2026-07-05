# Discipline System — Padrino Digital

Sistema de seguimiento de hábitos, accountability, y modo mínimo.

## Hábitos

```sql
CREATE TABLE habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    frequency TEXT NOT NULL CHECK(frequency IN ('daily','weekly','monthly')),
    expected_count INTEGER NOT NULL,     -- Veces esperadas por período
    minimum_count INTEGER,               -- Mínimo en modo mínimo
    unit TEXT,                            -- Unidad (veces, minutos, km)
    area TEXT                             -- Área (salud, trabajo, personal)
);

CREATE TABLE habit_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL REFERENCES habits(id),
    date TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    value REAL,                           -- Valor numérico (ej. 30 minutos)
    notes TEXT,
    UNIQUE(habit_id, date)
);
```

### Ejemplos de hábitos

```sql
INSERT INTO habits (name, frequency, expected_count, minimum_count, unit, area) VALUES
('Ejercicio', 'daily', 1, 0, 'veces', 'salud'),
('Leer', 'daily', 1, 0, 'sesiones', 'personal'),
('Revisar finanzas', 'weekly', 1, 1, 'veces', 'finanzas'),
('Meditar', 'daily', 1, 0, 'minutos', 'salud'),
('Caminar 10k pasos', 'daily', 1, 0, 'días', 'salud');
```

## Compliance Semanal

Padrino calcula compliance semanal para cada hábito:

```
compliance % = (días completados / días esperados) × 100
```

| Compliance | Diagnóstico |
|:----------:|------------|
| ≥ 80% | ✅ Buen ritmo |
| 60-79% | ⚠️ Atención — bajando |
| 40-59% | 🔴 Crítico — riesgo de abandono |
| < 40% | 🚨 Activar modo mínimo |

## Modo Mínimo

Cuando el compliance semanal general cae por debajo del 40%, Padrino propone
activar **modo mínimo**.

### ¿Qué cambia en modo mínimo?

| Aspecto | Normal | Modo Mínimo |
|---------|--------|-------------|
| Prioridades diarias | 3 máx | 2 máx |
| Proyectos nuevos | Permitidos | Bloqueados |
| Revisiones | Completas | Reducidas |
| Hábitos | Todos | Solo mínimo_count |
| Tono | Normal | Más directo, sin presión |

### Activación

```
Usuario: /modo minimo
Padrino: "🌅 Modo mínimo activado. Solo 2 prioridades por día,
         sin proyectos nuevos. Cuando estés listo para volver al
         ritmo normal, /modo normal."
```

También se activa automáticamente cuando el compliance semanal < 40%.

### Desactivación

```
Usuario: /modo normal
Padrino: "Volviendo a modo normal. Bienvenido de vuelta."
```

## Detección de Estancamiento

### Snooze Escalation

Cuando una tarea se pospone 3+ veces:

```
"Esta tarea la pateaste 3 veces en 2 semanas. Opciones:
 1. Redefinirla (¿es muy grande? ¿la dividimos?)
 2. Delegarla (¿alguien más puede hacerla?)
 3. Agendarla con fecha fija (¿cuándo SÍ o SÍ la hacés?)
 4. Cancelarla (¿realmente es necesaria?)
 5. Dejarla en espera hasta [fecha]"
```

### Stall Detection (7 días)

Si un proyecto no tiene actividad en 7+ días:

```
"El proyecto {nombre} lleva {días} sin avance.
 ¿Lo pausamos, redefinimos, o le damos prioridad esta semana?"
```

**Exclusión**: tareas con `scheduled_at` futuro — no cuentan como estancadas.

### Open Task Threshold

Si hay más de 20 tareas abiertas:

```
"Tenés {n} tareas abiertas. ¿Revisamos cuáles podemos cerrar,
 cancelar, o archivar? Tener más de 20 tareas abiertas suele
 indicar que hay varias que ya no son relevantes."
```

## Streak Policy

Las rachas (streaks) se muestran como métrica complementaria:

```
"Ejercicio: racha de 5 días ✓"
```

**Política**: nunca se usa la racha para avergonzar ("Perdiste tu racha de 30 días").
Si un hábito se rompe, se menciona el dato sin juicio:

```
"Ejercicio: 2 días sin registrar. ¿Todo bien?"
```

No:
```
"¡Perdiste tu racha de 30 días! ¡Qué desastre!"
```

## 5 Niveles de Diagnóstico

Cuando un hábito no se cumple, Padrino diagnostica la causa:

| Nivel | Causa probable | Pregunta |
|-------|---------------|----------|
| 1 | Bloqueo externo | "¿Hay algo externo que te impide hacerlo?" |
| 2 | Falta de tiempo | "¿Es un tema de tiempo o de energía?" |
| 3 | Dependencia | "¿Depende de algo o alguien más?" |
| 4 | Definición pobre | "¿Está bien definido el hábito? ¿Es muy vago?" |
| 5 | Brecha de disciplina | "¿Es simplemente difícil mantener la constancia?" |

## Comandos

| Comando | Acción |
|---------|--------|
| `/habito {nombre}` | Registrar hábito completado |
| `/habito {nombre} {valor}` | Registrar con valor (ej. 30 minutos) |
| `/habitos` | Ver todos los hábitos y compliance |
| `/modo minimo` | Activar modo mínimo |
| `/modo normal` | Volver a modo normal |
| `/modo firme` | Modo accountability directo |
| `/modo enfoque` | Modo deep work (silencio) |

## Integración

- **padrino-plan**: Reduce prioridades en modo mínimo
- **padrino-review**: Incluye tabla de compliance en revisión semanal
- **padrino-soul**: Cambia tono según modo (normal/firme/mínimo)
