# personal-memory Specification

## Purpose

Capture, store, and recall personal data across structured Markdown files and a SQLite memory table with FTS5 search. Every memory entry carries provenance metadata (source, date, confidence, validity period). Differentiate facts from preferences from decisions from hypotheses.

## Requirements

### Requirement: Memory Capture with Metadata

When the system captures a new memory, it MUST record: content, source (user statement, observation, inference, import), capture date, confidence level (confirmed, high, medium, low, speculative), validity period (permanent, years, months, days, until-date), and type (fact, preference, decision, hypothesis). The system SHALL store memories in both the SQLite `memories` table and the appropriate Markdown context file.

#### Scenario: Capturing a user-stated fact

- GIVEN the user says "Mi número de DNI es 12345678"
- WHEN the system captures this as a memory
- THEN the type SHALL be "fact"
- AND source SHALL be "user_statement"
- AND confidence SHALL be "confirmed"
- AND it SHALL be written to USER.md under personal data
- AND it SHALL be indexed in the SQLite memories table with FTS5

#### Scenario: Capturing a system inference

- GIVEN the system observes the user consistently postpones gym tasks for 3 weeks
- WHEN it captures this pattern as a memory
- THEN the type SHALL be "hypothesis"
- AND source SHALL be "inference"
- AND confidence SHALL be "medium"
- AND the system SHALL flag it for user confirmation

#### Scenario: Memory with expiration

- GIVEN the user says "Mi obra social vence el 31 de diciembre de 2026"
- WHEN the system captures this memory
- THEN the validity SHALL be set to "until:2026-12-31"
- AND the system SHALL include this in relevant reviews starting 30 days before expiration

### Requirement: Structured Memory Retrieval

The system MUST support retrieval by area (personal, finances, health-and-training, work, vehicles), by project (nexios, ascend, fletes, home-gym, rastrojero), and by full-text search via FTS5. Queries SHALL return the most recent and highest-confidence entries first. Expired memories MUST be excluded from results unless explicitly requested.

#### Scenario: FTS5 search across all memories

- GIVEN memories exist for multiple areas and projects
- WHEN the user asks "¿Qué sé sobre el Rastrojero?"
- THEN the system SHALL execute an FTS5 search across the memories table
- AND SHALL return results ordered by recency and confidence
- AND SHALL label each result with its type (fact/preference/decision/hypothesis)

#### Scenario: Area-filtered retrieval

- GIVEN the user asks "¿Qué tengo registrado en finanzas?"
- WHEN the system queries memories filtered by area="finances"
- THEN only memories tagged with area finances SHALL be returned
- AND expired memories SHALL be excluded

#### Scenario: Expired memory handling

- GIVEN a memory with validity "until:2025-01-01" exists
- WHEN the current date is 2026-07-05
- AND the user searches normally
- THEN that memory SHALL NOT appear in results
- WHEN the user explicitly asks "incluyendo información vencida"
- THEN expired memories SHALL be included, clearly marked as expired

### Requirement: Journal Entry Management

The system MUST maintain a daily journal at `data/journal/YYYY/MM/YYYY-MM-DD.md`. Journal entries SHALL be append-only — once written, they MUST NOT be modified except for corrections explicitly requested by the user. The system SHALL auto-create the directory structure and file on first write of each day.

#### Scenario: First journal entry of the day

- GIVEN no journal file exists for 2026-07-05
- WHEN the user says "Agregá al diario: hoy terminé el informe de Nexios"
- THEN the system SHALL create data/journal/2026/07/2026-07-05.md
- AND SHALL append the entry with timestamp
- AND SHALL confirm: "Agregado al diario de hoy."

#### Scenario: Append to existing journal entry

- GIVEN data/journal/2026/07/2026-07-05.md already exists with one entry
- WHEN the user adds a second entry
- THEN the new entry SHALL be appended after the existing one
- AND the original entry SHALL remain unchanged
- AND both entries SHALL be preserved

#### Scenario: Correction of a journal entry

- GIVEN the journal file has an entry the user wants corrected
- WHEN the user says "Corregí en el diario: [specific correction]"
- THEN the system SHALL request explicit confirmation before editing
- AND SHALL preserve the original text with a correction marker
- AND SHALL append the corrected version below
