---
name: padrino-inbox
description: Universal inbox classifier for Padrino Digital. Routes every incoming message to the correct domain skill with confidence scoring. Low-confidence classifications ask the user for confirmation before routing.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    tags: [padrino, inbox, classifier, routing, nlu]
    related_skills: [padrino-soul, padrino-memory, padrino-tasks, padrino-finance, padrino-coach, padrino-review]
    commands: [/inbox]
---

# padrino-inbox — Universal Inbox Classifier

## Purpose

Every message that reaches Padrino Digital passes through this classifier BEFORE
any domain skill processes it. This skill determines WHAT the user is saying so
the message can be routed to the right handler.

The classifier is LLM-based (not rule-based) because Padrino operates in
Rioplatense Spanish, which is too ambiguous for keyword matching. The LLM
classifies the intent and assigns a confidence score.

## When to Use

- Automatically: every incoming Telegram message (unless it starts with a known
  slash command like `/hoy`, `/plan`, `/finanzas`, etc.)
- Manually: when the user sends `/inbox` followed by a message to force
  re-classification or explicit routing

## Classification Categories

The classifier maps every message to exactly ONE of these 13 categories:

| # | Category | Description | Routed To |
|---|----------|-------------|-----------|
| 1 | `task` | Action item, to-do, commitment, deadline | padrino-tasks |
| 2 | `idea` | Brainstorming, possibility, thing to evaluate later | padrino-tasks |
| 3 | `memory` | Fact, preference, personal data to remember | padrino-memory |
| 4 | `decision` | Choice made, conclusion reached | padrino-memory |
| 5 | `expense` | Money spent, outgoing payment | padrino-finance |
| 6 | `income` | Money received, incoming payment | padrino-finance |
| 7 | `goal` | Objective with measurable target | padrino-tasks |
| 8 | `habit` | Recurring behavior to track | padrino-coach |
| 9 | `reminder` | Time-based notification request | padrino-tasks |
| 10 | `project_update` | Status change, milestone, blocker on a project | padrino-tasks |
| 11 | `code_audit_request` | Ask to audit a code repository | padrino-audit |
| 12 | `journal_entry` | Personal reflection, daily log entry | padrino-memory |
| 13 | `unknown` | Cannot classify with sufficient confidence | Ask user |

## Classification Rules

### Rule 1: Parse for action vs information

- If the message describes something the user NEEDS TO DO → `task`
- If the message describes something the user WANTS TO EXPLORE → `idea`
- If the message describes something the user WANTS TO REMEMBER → `memory`
- If the message describes a CHOICE the user MADE → `decision`
- If the message describes MONEY GOING OUT → `expense`
- If the message describes MONEY COMING IN → `income`
- If the message describes a MEASURABLE OBJECTIVE → `goal`
- If the message describes a RECURRING BEHAVIOR → `habit`

### Rule 2: Check for temporal markers

- "Tengo que...", "Me falta...", "Pendiente..." → `task`
- "Podría...", "Sería bueno...", "No sé si vale la pena..." → `idea`
- "Acordate que...", "No te olvides de...", "Recordá..." → `memory`
- "Decidí que...", "Voy a...", "Resolví..." → `decision`
- "Gasté...", "Pagué...", "Compré..." → `expense`
- "Cobré...", "Me depositaron...", "Facturé..." → `income`
- "Quiero ahorrar...", "Meta...", "Objetivo..." → `goal`

### Rule 3: Check for amounts

- If the message contains a currency amount AND a spending verb → `expense`
- If the message contains a currency amount AND a receiving verb → `income`
- If the message contains a currency amount AND a target/objective → `goal`

### Rule 4: Check for project context

- If the message mentions a known project (nexios, ascend, fletes, home-gym,
  rastrojero) AND describes progress/status → `project_update`
- If the message mentions a known project AND describes a specific action → `task`

## Confidence Thresholds

| Confidence | Action |
|------------|--------|
| ≥ 80% | Auto-route to the domain skill. No user confirmation needed. |
| 50-79% | Present top 2-3 options to user: "¿Esto es [A], [B], o [C]?" |
| < 50% | Classify as `unknown`. Ask: "No supe clasificar esto. ¿Es una tarea, idea, memoria, o algo más?" |

## Classification Examples

### High confidence (auto-route)

```
"Tengo que llamar al mecánico del Rastrojero"
→ task (confidence: 95%)
  Reason: "Tengo que" = obligation verb, specific action, known project context

"Gasté 35000 en combustible del Rastrojero"
→ expense (confidence: 98%)
  Reason: "Gasté" = spending verb, currency amount present, category implied

"Quiero ahorrar 2000 USD para fin de año"
→ goal (confidence: 92%)
  Reason: "Quiero ahorrar" = goal verb, amount + currency, deadline implied

"Cobré el depósito de Nexios — 150 USD"
→ income (confidence: 97%)
  Reason: "Cobré" = receiving verb, amount + currency, source project

"Mi DNI es 12345678"
→ memory (confidence: 88%)
  Reason: Personal data statement, no action implied, factual

"Voy a usar PostgreSQL en vez de SQLite para Nexios"
→ decision (confidence: 90%)
  Reason: "Voy a usar" = decision verb, architectural choice, specific project

"Todos los días hago 30 minutos de ejercicio"
→ habit (confidence: 85%)
  Reason: "Todos los días" = recurring behavior, measurable time

"Acordate que el seguro del auto vence en diciembre"
→ reminder (confidence: 82%)
  Reason: "Acordate" = reminder verb, future deadline
```

### Medium confidence (ask user)

```
"El Rastrojero necesita arreglos"
→ task (60%), project_update (30%), idea (10%)
  Ask: "¿Esto es una tarea pendiente o una actualización del proyecto Rastrojero?"

"No sé si vale la pena seguir con el gimnasio en casa"
→ idea (65%), decision (25%), journal_entry (10%)
  Ask: "¿Es una idea para evaluar o una decisión que ya tomaste?"

"Nexios va a cobrar por mensajes respondidos"
→ decision (60%), project_update (25%), expense (15%)
  Ask: "¿Es una decisión que tomaste, una actualización del proyecto, o un gasto?"
```

### Unknown (low confidence)

```
"Hoy hizo frío"
→ unknown (confidence: 30%)
  Ask: "No supe clasificar esto. ¿Es una entrada de diario, algo más, o solo un comentario?"
```

## Special Cases

### Ambiguous amounts

When a message contains an amount but the context is ambiguous:

```
"35000 del Rastrojero"
→ unknown (confidence: 45%)
  Ask: "¿Es un gasto (ej: repuestos), un ingreso (ej: flete), o un presupuesto?"
  NEVER register an ambiguous amount without confirmation.
```

### Multi-intent messages

When a single message contains multiple intents, classify the PRIMARY intent
(the first actionable one) and note secondary intents:

```
"Terminé el informe de Nexios. Mañana tengo que mandarlo. También gasté 5000 en café."
→ task (primary: "mandar informe"), expense (secondary), project_update (secondary)
  Route to: padrino-tasks (primary)
  After processing primary, flag secondary intents for user confirmation.
```

### Slash commands (skip classifier)

Messages starting with these commands bypass the classifier entirely:

- `/inbox` — force re-classification
- `/hoy` — today's plan
- `/plan` — daily planning
- `/tareas` — task management
- `/proyecto` — project management
- `/meta` — goal management
- `/finanzas` — finance overview
- `/gasto` — record expense
- `/presupuesto` — budget management
- `/habito` — habit tracking
- `/recordar` — memory recall
- `/modo` — mode switching
- `/auditar` — code audit
- `/backup` — backup management
- `/restaurar` — restore from backup

## `/inbox` Command Handler

When the user explicitly sends `/inbox <message>`, the classifier:

1. Classifies the message
2. Shows the classification result with confidence
3. Explains WHY it classified that way
4. Asks for confirmation before routing (even for high confidence — `/inbox` is
   always explicit mode)

```
User: /inbox Tengo que pagar la luz
Padrino: Clasifiqué esto como **tarea** (confianza: 95%)
         Razón: "Tengo que" indica una obligación, "pagar la luz" es una acción concreta.
         ¿Creo la tarea "Pagar la luz"?
```

## Cross-Skill Contract

This skill is called by `padrino-soul` after mode and gate checks. It returns a
classification result to `padrino-soul`, which then routes to the appropriate
domain skill.

**Input**: Raw message text (string)
**Output**: Classification object:
```json
{
  "category": "task|idea|memory|decision|expense|income|goal|habit|reminder|project_update|code_audit_request|journal_entry|unknown",
  "confidence": 0.0-1.0,
  "reason": "Why this classification was chosen",
  "alternatives": [{"category": "...", "confidence": 0.X}, ...],
  "needs_confirmation": true|false,
  "extracted_entities": {
    "amount": null|{value, currency},
    "date": null|"YYYY-MM-DD",
    "project": null|"project_name",
    "person": null|"name"
  }
}
```

## Privacy Note

The classifier processes message text but does NOT store it. Classification
happens in-memory. Only the routed domain skill decides what to persist.
