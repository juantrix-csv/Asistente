# accountability-coach Specification

## Purpose

Track habits with compliance monitoring, detect problematic postponement patterns, enforce minimum-mode for reduced-capacity days, and recommend load reduction — without inventing non-compliance or using streaks as the sole metric.

## Requirements

### Requirement: Habit Tracking with Compliance Monitoring

The system MUST track habits via `habits` and `habit_entries` tables. Each habit entry SHALL record: date, completed (boolean), value (numeric for measurable habits), notes. Weekly compliance SHALL be calculated as completed_entries / expected_entries. The system MUST differentiate lack of discipline from lack of time, blockage, dependency, or poor task definition — never defaulting to "lack of discipline."

#### Scenario: Record daily habit completion

- GIVEN a habit "Entrenar" with expected frequency "daily"
- WHEN the user reports "Entrené hoy, 45 minutos"
- THEN the system SHALL create a habit_entry with completed=true, value=45, date=today
- AND SHALL respond: "Registrado. Vas [X] días esta semana."

#### Scenario: Calculate weekly compliance

- GIVEN habit "Leer" expects 5 entries per week and has 3 completed so far
- WHEN the weekly review runs
- THEN compliance SHALL be reported as "60% (3/5)"
- AND the system SHALL ask: "¿Tuviste menos tiempo, o simplemente no se dio?"
- AND SHALL NOT assume lack of discipline

#### Scenario: Distinguish low compliance due to blockage

- GIVEN habit "Avanzar Rastrojero" has 1/5 this week
- AND a task "Comprar repuesto Rastrojero" is blocked waiting for a part
- WHEN the accountability review runs
- THEN the system SHALL detect the dependency
- AND SHALL report: "Rastrojero está bajo (20%) porque el repuesto no llegó — no es falta de disciplina"
- AND SHALL NOT flag this as a discipline issue

### Requirement: Problematic Task Detection

The system MUST detect tasks postponed 3+ times (snooze_count ≥ 3) and tasks without any progress for 7+ days. These SHALL appear in the accountability review. The system SHALL recommend one of: redefine, break down, delegate, schedule firmly, or close — not just "try harder."

#### Scenario: Task postponed 3 times triggers review

- GIVEN task "Actualizar documentación de Nexios" has snooze_count=3
- WHEN the accountability review runs
- THEN the system SHALL flag it: "Pospuesto 3 veces — ¿vale la pena mantenerlo?"
- AND SHALL offer options: redefinir, desglosar en pasos más chicos, delegar, agendar con fecha fija, o cerrar

#### Scenario: Task with 7+ days of inactivity

- GIVEN task "Migrar base de datos" was created 10 days ago with no status change
- WHEN the weekly review runs
- THEN the system SHALL flag it as "Sin avance en 10 días"
- AND SHALL ask: "¿Sigue siendo relevante? ¿Necesitás desglosarlo?"

#### Scenario: Healthy task does not trigger false flag

- GIVEN task "Planificar sprint" is scheduled for next Monday (5 days from now)
- AND it has not been touched since creation 3 days ago
- WHEN the weekly review runs
- THEN the system SHALL NOT flag it (scheduled future task, not stalled)
- AND SHALL recognize the scheduled_at is in the future

### Requirement: Load Reduction and Minimum Mode

When weekly compliance across all habits falls below 40%, or when a task ratio (open/completed) exceeds 3:1, the system MUST recommend reducing load. Minimum mode SHALL reduce all habit expectations and project scopes to their pre-defined minimum versions. The system MUST recommend closing old tasks before adding new ones when open tasks exceed 20.

#### Scenario: Low compliance triggers load reduction

- GIVEN weekly compliance across all habits is 35% (below 40% threshold)
- WHEN the weekly review runs
- THEN the system SHALL recommend: "Tu cumplimiento semanal está bajo (35%). ¿Querés activar modo mínimo esta semana?"
- AND SHALL show which habits/projects would be reduced and to what minimum

#### Scenario: Too many open tasks triggers closing recommendation

- GIVEN the user has 25 open tasks and 5 completed in the last week
- WHEN the user tries to create a new task
- THEN the system SHALL warn: "Tenés 25 tareas abiertas. ¿Querés cerrar o archivar algunas antes de agregar más?"
- AND SHALL NOT block task creation, but SHALL strongly recommend review

#### Scenario: Minimum mode activation

- GIVEN the user activates minimum mode or the system recommends it
- WHEN habits and projects are adjusted
- THEN each habit SHALL switch from normal target to minimum target
- AND project scopes SHALL reduce to minimum versions
- AND the daily planner SHALL cap at 2 priorities instead of 3
