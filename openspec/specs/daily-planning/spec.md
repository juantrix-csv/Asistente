# daily-planning Specification

## Purpose

Generate daily plans with a maximum of 3 main priorities using multi-criteria ranking. Detect overload, provide provisional plans when availability is unknown, and flag postponed tasks.

## Requirements

### Requirement: Daily Plan Generation with Max 3 Priorities

The daily planner MUST generate a plan with at most 3 main priorities. The planner SHALL rank candidate tasks using: due date, impact, urgency, declared priority, dependencies, estimated time, estimated energy, snooze count, area balance, fixed commitments, and blocked tasks. The system MUST NOT overfill the day — if total estimated time exceeds available time, tasks SHALL be deferred with explanation.

#### Scenario: Generate plan for a normal day

- GIVEN 8 active tasks with varied priorities and due dates
- AND the user has 6 available hours today
- AND 2 tasks have due dates today, 1 has high impact, and 5 are low urgency
- WHEN the daily plan is generated
- THEN the plan SHALL contain exactly 3 main priorities (the 2 due today + 1 high impact)
- AND total estimated time SHALL NOT exceed 6 hours
- AND the remaining 5 tasks SHALL be listed as "deferred" with reasons

#### Scenario: Overload detection

- GIVEN 4 tasks are all due today, each estimated at 2 hours
- AND the user has 5 available hours today
- WHEN the daily planner evaluates the day
- THEN it SHALL trigger an overload warning
- AND SHALL present: "Hoy tenés 8 horas estimadas de tareas con fecha límite, pero solo 5 horas disponibles. ¿Cuáles querés priorizar?"
- AND SHALL NOT silently choose which tasks to drop

#### Scenario: Minimum mode day

- GIVEN the user signals low energy or requests "modo mínimo"
- WHEN the daily planner generates the plan
- THEN the plan SHALL contain at most 2 priorities instead of 3
- AND each priority SHALL use its "minimum version" if defined
- AND the planner SHALL reduce estimated time accordingly

### Requirement: Provisional Planning When Availability Unknown

When the user's availability for the day is unknown at planning time (e.g., plan generated at midnight or the user hasn't checked in), the system SHALL generate a provisional plan. The provisional plan MUST be clearly labeled as tentative and SHALL request confirmation or adjustment when the user checks in.

#### Scenario: Provisional plan at midnight

- GIVEN the cron job generates a plan at 00:30 ART
- AND the user has not yet reported their availability for the day
- WHEN the plan is generated
- THEN it SHALL be marked "Plan provisional — sujeto a tu confirmación"
- AND SHALL include a prompt: "¿Cuántas horas tenés disponibles hoy?"
- AND SHALL adjust when the user provides their actual availability

#### Scenario: User confirms provisional plan

- GIVEN a provisional plan with 3 priorities was generated
- WHEN the user says "Confirmado, tengo 5 horas"
- THEN the plan SHALL validate the estimates against 5 hours
- AND SHALL adjust if needed (remove/adjust priorities)
- AND SHALL mark the plan as "Plan del día — confirmado"

#### Scenario: User rejects provisional priorities

- GIVEN a provisional plan suggests 3 priorities
- WHEN the user says "Hoy no puedo hacer A, prioridad es B y C solamente"
- THEN the plan SHALL regenerate with the user's specified priorities
- AND SHALL respect the user's override while noting that task A was deferred

### Requirement: Postponed Task Flagging

Tasks postponed (snoozed) from previous days MUST be flagged in the current day's plan. A task postponed 2+ times SHALL carry a visible warning. A task postponed 3+ times SHALL be escalated to the accountability coach for review.

#### Scenario: Task postponed once

- GIVEN a task was snoozed yesterday (snooze_count=1)
- WHEN today's plan is generated
- THEN the task SHALL appear with a "(pospuesto 1 vez)" annotation
- AND SHALL still be eligible as a main priority

#### Scenario: Task postponed 3+ times escalated

- GIVEN a task has snooze_count=3
- WHEN today's plan is generated
- THEN the task SHALL carry a warning: "⚠️ Pospuesto 3 veces — ¿seguimos postergando o lo resolvemos?"
- AND the accountability coach SHALL be notified for review

#### Scenario: Task postponed but still urgent

- GIVEN a task has snooze_count=2 and its due date is today
- WHEN the plan is generated
- THEN the task SHALL be forced into the main priorities despite the snooze count
- AND SHALL carry both the snooze warning AND the due-today urgency flag
