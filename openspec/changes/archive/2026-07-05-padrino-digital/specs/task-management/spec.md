# task-management Specification

## Purpose

Manage tasks, projects, goals, and reminders in a structured SQLite database. Provide a universal inbox that classifies incoming messages by type and requests confirmation for ambiguous classifications.

## Requirements

### Requirement: Task Lifecycle Management

The system MUST support a full task lifecycle with statuses: inbox, todo, scheduled, in_progress, blocked, waiting, done, cancelled. Tasks SHALL carry: title, description, priority, project_id, due_at, scheduled_at, estimated_minutes, actual_minutes, snooze_count, last_snoozed_at, source, tags, blocked_by, archived_at. Status transitions MUST follow the defined lifecycle — disallowed transitions SHALL be rejected with explanation.

#### Scenario: Create task from inbox

- GIVEN a new task arrives in the universal inbox
- WHEN the system classifies it as a task and the user confirms
- THEN the task SHALL be created with status "inbox"
- AND the source SHALL record the origin (Telegram message, manual, system)
- AND the task SHALL appear in the next review

#### Scenario: Valid status transition

- GIVEN a task with status "todo"
- WHEN the user marks it "in_progress"
- THEN the transition SHALL succeed
- AND the status SHALL update to "in_progress"

#### Scenario: Invalid status transition rejected

- GIVEN a task with status "done"
- WHEN the system or user attempts to transition it to "todo"
- THEN the system SHALL reject the transition
- AND SHALL explain that done tasks cannot revert to todo (use a new task instead)

#### Scenario: Task snooze tracking

- GIVEN a task with snooze_count=0
- WHEN the user postpones it
- THEN snooze_count SHALL increment to 1
- AND last_snoozed_at SHALL update to the current timestamp
- AND the task SHALL be flagged for accountability review if snooze_count >= 3

### Requirement: Universal Inbox Classification

Every incoming message to Padrino Digital MUST pass through the universal inbox classifier. The system SHALL classify each message as one of: task, idea, memory, decision, expense, income, goal, habit, reminder, project_update, code_audit_request, journal_entry, unknown. When classification confidence is below threshold, the system MUST ask the user for confirmation before storing.

#### Scenario: High-confidence classification

- GIVEN the user sends "Tengo que pagar la luz antes del viernes"
- WHEN the inbox classifier processes this message
- THEN it SHALL classify as "task" with high confidence
- AND SHALL create a task without asking for confirmation

#### Scenario: Ambiguous classification requires confirmation

- GIVEN the user sends "El Rastrojero necesita arreglos"
- WHEN the inbox classifier processes this message
- THEN it MAY classify with medium confidence as task, idea, or project_update
- AND it SHALL ask: "¿Esto es una tarea pendiente, una idea para evaluar, o una actualización del proyecto Rastrojero?"
- AND SHALL wait for user response before storing

#### Scenario: Unknown classification fallback

- GIVEN the user sends a message that doesn't match any known category
- WHEN the classifier processes it with confidence below threshold
- THEN it SHALL classify as "unknown"
- AND SHALL present the message to the user with: "No supe clasificar esto. ¿Es una tarea, idea, memoria, o algo más?"
- AND SHALL store it only after classification

### Requirement: Project and Goal Tracking

Projects MUST have: id, name, description, status (active, paused, completed, archived), area, created_at. Goals MUST have: target value, current value, measurement unit, project_id, deadline. The system SHALL track goal progress and report when goals approach deadlines without sufficient progress.

#### Scenario: Create a project

- GIVEN the user says "Creá el proyecto home-gym"
- WHEN the system processes the command
- THEN a project record SHALL be created with status "active"
- AND area SHALL be set if the user provides it
- AND the project SHALL appear in project listings

#### Scenario: Goal progress tracking

- GIVEN a goal "Ahorrar $500,000" with target=500000, current=200000, unit="ARS"
- WHEN the user records a $50,000 deposit toward this goal
- THEN current SHALL update to 250000
- AND progress SHALL be recalculated (50%)
- AND the system SHALL report: "Meta ahorro: $250,000/$500,000 (50%)"

#### Scenario: Goal approaching deadline without progress

- GIVEN a goal with deadline in 14 days and current=20%, target=100%
- WHEN the evening review runs
- THEN the system SHALL flag this goal
- AND SHALL report: "Meta [name] vence en 14 días y está al 20%. ¿Querés ajustar el plan?"
