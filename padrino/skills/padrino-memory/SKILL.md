---
name: padrino-memory
description: Personal memory capture, recall, and journal for Padrino Digital. Differentiates facts/preferences/decisions/hypotheses with provenance metadata. Stores in SQLite with FTS5 search and syncs to Markdown files.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    tags: [padrino, memory, recall, journal, capture, fts5]
    related_skills: [padrino-soul, padrino-inbox, padrino-tasks]
    commands: [/recordar]
    writes_to: [padrino.db, padrino/data/memory/, padrino/data/journal/]
---

# padrino-memory — Personal Memory & Journal

## Purpose

Capture, organize, and recall everything Juan wants Padrino to remember.
Memories are stored in two places:

1. **SQLite** (`padrino.db` → `memories` table) — structured, queryable, FTS5
   full-text search with provenance metadata
2. **Markdown files** (`padrino/data/memory/`) — human-readable, sync-friendly,
   organized by area and project

Additionally, this skill manages the daily journal at
`padrino/data/journal/YYYY/MM/YYYY-MM-DD.md`.

## When to Use

- Automatically: when `padrino-inbox` classifies a message as `memory`,
  `decision`, or `journal_entry`
- Manually: `/recordar <query>` to recall memories; `/recordar <fact>` to
  explicitly store something

## Memory Types

Every memory has a `type` that determines how it's treated:

| Type | Meaning | Example | Storage |
|------|---------|---------|---------|
| `fact` | Verifiable, objective information | "DNI: 12345678" | USER.md + SQLite |
| `preference` | Subjective choice or taste | "Prefiere café sin azúcar" | preferences.md + SQLite |
| `decision` | Choice made with context | "Elegimos PostgreSQL para Nexios" | decisions table + SQLite |
| `hypothesis` | Inferred pattern, not confirmed | "Parece que evita el gimnasio cuando tiene deadlines" | SQLite only (flagged for review) |
| `temporal_info` | Time-sensitive data | "Obra social vence 2026-12-31" | USER.md + SQLite (with validity) |
| `replaced` | Memory superseded by newer info | Old DNI value | Archived in SQLite |

## Memory Sources

| Source | Meaning | When used |
|--------|---------|-----------|
| `user_statement` | User explicitly stated this | "Mi DNI es..." |
| `observation` | System detected this from data | "Completaste 5 tareas hoy" |
| `inference` | System concluded this from patterns | "Gastás ~30% más en diciembre" |
| `import` | Data imported from external source | CSV import, migration |

## Confidence Levels

| Level | Meaning | Action |
|-------|---------|--------|
| `confirmed` | User explicitly verified this | Store permanently |
| `high` | Very likely correct, from reliable source | Store, no flag |
| `medium` | Plausible but unconfirmed | Store, flag for review |
| `low` | Weak signal, needs verification | Store, flag for review, ask user soon |
| `speculative` | Pure guess / system inference | Store only if useful, always flag |

## Memory Lifecycle

### Capture flow

1. Message arrives classified as `memory` from inbox
2. Extract: content, type, source, confidence, area, project, event_date,
   validity_until, tags
3. If confidence ≥ `high` → store immediately
4. If confidence < `high` → present to user: "Registré [content] como [type]
   (confianza: [level]). ¿Es correcto?"
5. Write to SQLite `memories` table
6. Sync to appropriate Markdown file
7. If FTS5 is available, the triggers automatically update the index

### Recall flow (`/recordar`)

```
User: /recordar <query>
```

1. Execute FTS5 search: `SELECT * FROM memories_fts WHERE memories_fts MATCH '<query>'`
2. Join with `memories` table for full metadata
3. Sort by: confidence (confirmed > high > medium > low), recency
4. Filter out: expired memories (validity_until < today) unless user says
   "incluyendo información vencida"
5. Present results with type labels:

```
📋 **Resultados para "Rastrojero"** (3 recuerdos)

1. [F] Service marzo 2025 — Taller Rodríguez
   Fuente: user_statement | Confianza: confirmed
   
2. [P] Prefiere repuestos originales, no alternativos
   Fuente: user_statement | Confianza: confirmed
   
3. [H] Probablemente gasta ~$150k/mes en mantenimiento
   Fuente: inference | Confianza: low | ⚠️ No confirmado
```

### Correction flow

1. User indicates a memory is wrong: "Eso no es así" or "Corregí: [new fact]"
2. OLD memory: mark `type = 'replaced'`, set `deleted_at`
3. NEW memory: create with `source = 'user_statement'`, `confidence = 'confirmed'`
4. Set `superseded_by` on old memory pointing to new memory
5. Update Markdown file: replace old entry, add correction note

## Markdown File Sync

Memories are synced to Markdown files organized by domain:

### File structure

```
padrino/data/memory/
├── USER.md              # Personal data (DNI, contact, health, documents)
├── MEMORY.md            # Memory index — auto-generated summary of all memories
├── preferences.md       # Preferences and tastes
├── goals.md             # Active goals and progress
├── current_context.md   # What's happening now (temporary, refreshed often)
├── areas/
│   ├── personal.md      # Personal life memories
│   ├── finances.md      # Financial memories
│   ├── health-and-training.md
│   ├── work.md          # Work/professional memories
│   └── vehicles.md      # Vehicle-related memories
└── projects/
    ├── nexios.md        # Nexios project memories
    ├── ascend.md        # Ascend project memories
    ├── fletes.md        # Fletes project memories
    ├── home-gym.md      # Home gym project memories
    └── rastrojero.md    # Rastrojero project memories
```

### Sync rules

1. **Fact → USER.md**: Personal data facts (DNI, address, health info) go to
   USER.md under the relevant section
2. **Preference → preferences.md**: All preferences (food, tools, workflows,
   music, etc.) go to preferences.md
3. **Decision → decisions table + project file**: Architectural/technical
   decisions go to `decisions` table + the relevant project Markdown file
4. **Memory → area/project file**: General memories go to the file matching
   their `area` or `project` field
5. **Hypothesis → SQLite only**: Hypotheses are NOT written to Markdown files
   until confirmed. They stay in SQLite flagged for review.

### Writing format

Each Markdown entry follows this pattern:

```markdown
### [YYYY-MM-DD] [Type Icon] Title

**Content**: The actual memory content
**Source**: user_statement | observation | inference | import
**Confidence**: confirmed | high | medium | low | speculative
**Validity**: permanent | until YYYY-MM-DD
**Tags**: tag1, tag2
```

## Journal Management

### Journal structure

```
padrino/data/journal/
└── YYYY/
    └── MM/
        └── YYYY-MM-DD.md
```

### Journal rules

1. **Append-only**: Entries are appended with timestamp. Never modify existing
   entries unless explicitly correcting.
2. **Auto-create**: Directory and file are created on first write of the day.
3. **Corrections**: When correcting, preserve original text with `~~strikethrough~~`
   and append corrected version:

```markdown
## 2026-07-05

**09:15** — Terminé el informe de Nexios.
**14:30** — ~~Gasté $5000 en verdulería~~ → Corrección: Gasté $3500 en verdulería.
```

4. **Daily aggregation**: At evening review, `padrino-review` reads today's
   journal to summarize the day.

## Cross-Skill Contract

### Input from padrino-soul (after inbox classification as `memory` or `decision`)

```json
{
  "content": "Mi DNI es 12345678",
  "classification": "memory",
  "extracted": {
    "type": "fact",
    "area": "personal",
    "confidence": "high"
  }
}
```

### Output to padrino-soul

```json
{
  "status": "stored|confirmed|rejected",
  "memory_id": 42,
  "synced_to": ["USER.md"],
  "needs_review": false
}
```

### `/recordar` command output

Returns a formatted list of memories with type labels [F], [P], [D], [H] for
fact, preference, decision, hypothesis respectively. Includes confidence and
source for each result.

## Privacy Note

- Memories with `confidence: speculative` are NEVER written to Markdown files
  (could be wrong and misleading if read by a human)
- Expired memories are excluded from `/recordar` results by default
- Memory content is stored in plain text in SQLite — the entire database file
  should be protected with filesystem permissions (600)
