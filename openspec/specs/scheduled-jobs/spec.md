# scheduled-jobs Specification

## Purpose

Run cron-based daily, weekly, and monthly summaries via Hermes Agent's built-in scheduler. Each job must be self-contained (no conversational context), consult the database and persistent files, log execution, and avoid duplicate notifications.

## Requirements

### Requirement: Morning Summary

The morning summary job MUST run at the configured time (default 08:00 ART) and deliver: top 3 priorities for the day, today's commitments (meetings, deadlines), overdue tasks, financial reminders (bills due, budget warnings), and whether minimum mode is active. The job SHALL be self-contained — it MUST NOT rely on prior conversation state.

#### Scenario: Morning summary on a normal day

- GIVEN the cron job triggers at 08:00 ART
- AND there are 3 priorities, 2 overdue tasks, and 1 bill due tomorrow
- WHEN the morning summary is generated
- THEN it SHALL send to Telegram a message containing all sections
- AND the format SHALL be structured and scannable
- AND the job SHALL log successful execution to the database

#### Scenario: Morning summary with minimum mode active

- GIVEN minimum mode is active for today
- WHEN the morning summary is generated
- THEN it SHALL prominently note: "🌅 Modo mínimo activado hoy"
- AND it SHALL show at most 2 priorities instead of 3
- AND it SHALL reduce the scope of displayed commitments to minimum versions

#### Scenario: Duplicate prevention

- GIVEN the morning summary job already ran successfully today
- WHEN the cron scheduler triggers again due to a misconfiguration
- THEN the job SHALL detect the duplicate via an execution log
- AND SHALL skip execution with a log entry: "Morning summary already delivered for YYYY-MM-DD"
- AND SHALL NOT send a duplicate message to Telegram

### Requirement: Evening Review

The evening review job MUST run at the configured time (default 21:30 ART) and deliver: completed tasks today, pending tasks carried to tomorrow, main obstacle encountered, unregistered expenses prompt, and next day preparation notes. The job SHALL log execution and avoid duplicates.

#### Scenario: Evening review with completed tasks

- GIVEN the user completed 2 of 3 priorities today
- WHEN the evening review runs at 21:30 ART
- THEN it SHALL list the 2 completed tasks
- AND SHALL note the 1 pending task that rolls over
- AND SHALL ask: "¿Cuál fue el principal obstáculo hoy?"

#### Scenario: Evening review prompts unregistered expenses

- GIVEN no expenses were recorded today
- WHEN the evening review runs
- THEN it SHALL ask: "¿Tuviste algún gasto hoy que no hayamos registrado?"
- AND SHALL wait for user response rather than assuming none

#### Scenario: Evening review job fails silently

- GIVEN the evening review job encounters a database connection error
- WHEN it cannot complete the review
- THEN it SHALL log the error with full details
- AND SHALL not crash the scheduler
- AND SHALL report the failure in the next successful job execution

### Requirement: Weekly and Monthly Reviews

The weekly review MUST run on the configured day (default Sunday 19:00 ART). It SHALL include: achievements, completed tasks, postponed tasks, stalled projects, habits compliance, income/expenses summary, savings progress, debt status, main problems, recommendations, and next week's priority. The monthly review SHALL include: financial evolution, goal progress, active projects, projects to pause, habits summary, debts, savings, important decisions made, and comparison with the previous month.

#### Scenario: Weekly review with stalled project

- GIVEN a project "home-gym" has had no task completions in 14 days
- WHEN the weekly review runs
- THEN it SHALL flag the project as stalled
- AND SHALL ask: "home-gym lleva 14 días sin avance. ¿Lo pausamos, redefinimos, o le damos prioridad esta semana?"

#### Scenario: Monthly review financial evolution

- GIVEN the month has closed
- WHEN the monthly review runs
- THEN it SHALL show income vs expenses for the current month
- AND SHALL compare with the previous month (delta and percentage)
- AND SHALL show savings goal progress changes
- AND SHALL list the top 3 expense categories

#### Scenario: Weekly review detects no data

- GIVEN the weekly review runs but the user recorded no transactions or tasks this week
- WHEN the review is generated
- THEN it SHALL report: "No hay datos registrados esta semana."
- AND SHALL NOT generate empty or misleading summaries
- AND SHALL prompt: "¿Querés que te ayude a retomar el registro?"
