# Memory Model — Padrino Digital

Arquitectura de memoria de Padrino Digital: tipos, captura, almacenamiento,
búsqueda FTS5, y sincronización Markdown.

## Dos Sistemas de Memoria

Padrino Digital usa dos sistemas complementarios:

| Sistema | Ubicación | Motor | Uso |
|---------|-----------|-------|-----|
| **Memoria SQLite** | `/srv/padrino/data/padrino.db` → tabla `memories` | SQLite + FTS5 | Datos estructurados, búsqueda semántica |
| **Memoria Markdown** | `~/.hermes/memory/` | Archivos `.md` | Narrativa, contexto, identidad |

### ¿Por qué dos?

- **SQLite + FTS5**: búsqueda rápida, consultas estructuradas, recuperación por área/tipo/confianza
- **Markdown**: legible por humanos, portable, backup-friendly, editable sin SQL

## Memoria SQLite — Tabla `memories`

### Esquema

```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,                  -- El contenido del dato
    source TEXT NOT NULL                    -- Origen del dato
        CHECK(source IN ('user_statement','observation','inference','import')),
    confidence TEXT NOT NULL                -- Nivel de certeza
        CHECK(confidence IN ('confirmed','high','medium','low','speculative')),
    type TEXT NOT NULL                      -- Tipo de dato
        CHECK(type IN ('fact','preference','decision','hypothesis')),
    area TEXT,                              -- Área (personal, trabajo, salud, etc.)
    project TEXT,                           -- Proyecto relacionado
    tags TEXT,                              -- Tags (coma separados)
    validity_until TEXT,                    -- Fecha de expiración (opcional)
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE memories_fts USING fts5(
    content, source, area, project, tags,
    content=memories, content_rowid=id
);
```

### Fuentes (`source`)

| Source | Significado | Ejemplo |
|--------|------------|---------|
| `user_statement` | El usuario lo dijo explícitamente | "Mi color favorito es el azul" |
| `observation` | Padrino lo observó | "Juan completó 5 tareas hoy" |
| `inference` | Padrino lo infirió de datos | "Basado en gastos, Juan gasta ~30% en supermercado" |
| `import` | Importado de fuente externa | CSV, otro sistema, migración |

### Confianza (`confidence`)

| Nivel | Significado | Cuándo usar |
|-------|------------|-------------|
| `confirmed` | Verificado por el usuario | Usuario dijo "sí, eso es correcto" |
| `high` | Alta certeza | Declaración explícita del usuario |
| `medium` | Certeza moderada | Observación repetida pero no confirmada |
| `low` | Baja certeza | Observación única, inference débil |
| `speculative` | Especulación | Hipótesis, predicción |

### Tipos (`type`)

| Type | Significado | Ejemplo |
|------|------------|---------|
| `fact` | Hecho objetivo | "Vivo en Buenos Aires" |
| `preference` | Preferencia personal | "Prefiero trabajar de mañana" |
| `decision` | Decisión tomada | "Decidí usar React para el frontend" |
| `hypothesis` | Hipótesis no confirmada | "Quizás el Rastrojero necesita cambio de aceite" |

### Búsqueda FTS5

```sql
-- Búsqueda por texto completo
SELECT m.* FROM memories m
JOIN memories_fts fts ON m.id = fts.rowid
WHERE memories_fts MATCH 'verdulería gasto'
ORDER BY rank;

-- Búsqueda por área + texto
SELECT * FROM memories
WHERE area = 'finanzas'
  AND id IN (SELECT rowid FROM memories_fts WHERE memories_fts MATCH 'presupuesto')
ORDER BY created_at DESC;
```

## Memoria Markdown

### Estructura de directorios

```
~/.hermes/memory/
├── USER.md                  # Datos personales del usuario
├── MEMORY.md                # Memoria general (auto-acumulativa)
├── preferences.md           # Preferencias y configuraciones
├── goals.md                 # Objetivos a largo plazo
├── current_context.md       # Contexto actual (qué está pasando ahora)
├── journal/
│   ├── 2026-07-01.md        # Entrada de journal diaria
│   ├── 2026-07-02.md
│   └── ...
├── areas/
│   ├── personal.md          # Área personal
│   ├── finanzas.md          # Área financiera
│   ├── salud.md             # Área de salud
│   ├── trabajo.md           # Área laboral
│   └── vehiculos.md         # Área de vehículos
└── projects/
    ├── nexios.md             # Proyecto Nexios
    ├── ascend.md             # Proyecto Ascend
    ├── fletes.md             # Proyecto Fletes
    ├── home-gym.md           # Proyecto Home Gym
    └── rastrojero.md         # Proyecto Rastrojero
```

### USER.md

```markdown
# Juan — Perfil de Usuario

## Datos básicos
- Nombre: Juan
- Ubicación: Buenos Aires, Argentina
- Zona horaria: America/Argentina/Buenos_Aires (UTC-3)

## Contexto profesional
- Freelance developer
- Proyectos activos: Nexios, Ascend, Fletes Ostrit
- Stack principal: TypeScript, React, Next.js, Node.js, Go

## Preferencias
- Trabaja mejor de mañana (6-12hs)
- Voseo rioplatense
- Prefiere mensajes directos, sin rodeos
```

### Journal

Cada entrada de journal es un archivo Markdown con fecha:

```markdown
# Journal — 2026-07-05

## Tareas completadas
- [x] Terminar el frontend de Nexios
- [x] Reunión con cliente de Ascend

## Obstáculos
- El Rastrojero no arranca — llevar al mecánico

## Decisiones
- Usar Next.js 14 para el proyecto nuevo

## Gastos del día
- $5,000 — Verdulería
- $12,000 — Repuestos Rastrojero
```

## Sincronización entre Sistemas

1. **Captura**: El usuario dice algo → `padrino-inbox` clasifica → `padrino-memory`
2. **SQLite**: Se inserta en `memories` con metadata (source, confidence, type)
3. **Markdown**: Se actualiza el archivo correspondiente según área/proyecto
4. **FTS5**: Se actualiza automáticamente (external content table)

## Correcciones

Cuando un usuario corrige un dato:

```
Usuario: "No, mi color favorito es verde, no azul"
Padrino: "Corrijo: tu color favorito es verde. El dato anterior (azul) queda registrado como corregido."
```

La corrección:
1. Marca el registro anterior con `validity_until = now()`
2. Crea un nuevo registro con `source = user_statement`, `confidence = confirmed`
3. Actualiza el archivo Markdown correspondiente

## Ciclo de Vida de un Dato

```
Captura → Clasificación → Almacenamiento → Verificación → Corrección/Expiración
   │            │               │               │               │
   │      source + type    INSERT en       usuario          validity_until
   │      asignados        memories        confirma         o corrección
   │                         + FTS5        o corrige
   │
user_statement: confidence = high
observation:    confidence = medium
inference:      confidence = low
```

## Privacidad

- Los datos de memoria NUNCA se comparten con terceros
- Los backups incluyen la memoria encriptada (GPG AES-256)
- El code auditor NO tiene acceso a `memories` ni a `memory/`
- Las búsquedas FTS5 son locales, no usan APIs externas
