# Code Auditor — Padrino Digital

Sistema de auditoría de código: flujo de trabajo, formato de hallazgos,
salida OpenCode, y aislamiento del perfil auditor.

## ¿Qué es el Code Auditor?

Un perfil Hermes separado (`~/.hermes_auditor/`) que analiza repositorios de
código autorizados, produce hallazgos estructurados, y genera un archivo
`OpenCode_TASKS.md` para que otra sesión de OpenCode implemente las correcciones.

## Principios

1. **Read-only**: Nunca modifica, commitea, pushea ni deploya código
2. **Aislado**: Perfil Hermes separado, sin Telegram, sin acceso a datos personales
3. **Autorizado**: Solo audita repos en la allowlist
4. **Estructurado**: Hallazgos con severidad, confianza, evidencia, reproducción
5. **Accionable**: Genera tareas de implementación para OpenCode

## Flujo de Auditoría

```
1. Usuario: /auditar https://github.com/juantrix-csv/nexios-backend
2. Verificación: ¿repo en allowlist? → sí → continuar
3. Clone: git clone --depth 1 (read-only token)
4. Detección: lenguaje (go.mod → Go) y framework (Chi router)
5. Diff: comparar con commit de última auditoría (incremental)
6. Análisis: herramientas estáticas según lenguaje
7. Hallazgos: estructurados, insertados en audit_findings
8. OpenCode_TASKS.md: generado en reports/code-audits/{repo}/{fecha}/
9. Resumen: enviado al usuario por Telegram
```

## Formato de Hallazgo

```yaml
id: AUDIT-20260705-0001
severity: critical
confidence: 85
category: security
summary: "Hardcoded JWT secret in environment config"
evidence: |
  File: src/config/env.ts:12
  Code: JWT_SECRET = "my-secret-key-123"
impact: "Cualquiera con acceso al repo puede firmar tokens JWT válidos"
reproduction: |
  1. Clonar el repo
  2. grep -r "JWT_SECRET" src/
  3. El secreto está en texto plano
acceptance_criteria: |
  - [ ] JWT_SECRET se lee de variable de entorno
  - [ ] El valor hardcodeado se elimina del código
  - [ ] Se rota el secreto en producción
required_tests: |
  - Test que verifica que la app no inicia sin JWT_SECRET
  - Test que verifica que el secreto no aparece en logs
restrictions: ""
possible_false_positive: false
```

## Herramientas de Análisis por Lenguaje

| Lenguaje | Herramientas |
|----------|-------------|
| **Go** | `go vet`, `staticcheck`, `golangci-lint --no-fix` |
| **TypeScript** | `eslint --no-fix`, `tsc --noEmit` |
| **JavaScript** | `eslint --no-fix` |
| **Python** | `ruff check`, `bandit -r .`, `mypy .` |
| **Todos** | `grep` para secrets, TODOs, FIXMEs, HACKs |

## OpenCode_TASKS.md

Archivo de salida que OpenCode puede consumir directamente:

```markdown
# OpenCode Tasks — Audit of nexios-backend
**Date**: 2026-07-05 | **Commit**: def456 | **Language**: Go | **Framework**: Chi
**Findings**: 18 (3 CRITICAL, 5 HIGH, 8 MEDIUM, 2 LOW)

## Critical

### AUDIT-20260705-0001: Hardcoded JWT secret
**Category**: security | **Confidence**: 85%

[detalles del hallazgo...]

- [ ] Implementar fix para AUDIT-20260705-0001
  - Mover JWT_SECRET a variable de entorno
  - Rotar el secreto en producción
  - Test: verificar que la app no inicia sin la variable

## High

### AUDIT-20260705-0004: Missing input validation on POST /api/users
...
```

## Perfil Auditor

El auditor corre en un perfil Hermes separado:

```
~/.hermes_auditor/
├── SOUL.md              # Persona mínima del auditor
├── .env                 # GIT_READONLY_TOKEN (600)
├── config.yaml
├── skills/
│   └── padrino-audit/SKILL.md
├── config/
│   └── repo-allowlist.txt
├── reports/
│   └── code-audits/
│       └── {repo}/
│           └── {fecha}/
│               ├── OpenCode_TASKS.md
│               ├── findings.json
│               └── audit.log
└── repositories/        # Clones read-only
```

### Aislamiento

| Recurso | ¿Acceso? |
|---------|:-------:|
| `/srv/padrino/data/padrino.db` | ❌ |
| `~/.hermes/memory/` | ❌ |
| Telegram Gateway | ❌ |
| Datos financieros | ❌ |
| Repos clonados (solo lectura) | ✅ |
| `~/.hermes_auditor/reports/` | ✅ |

## Comandos

| Comando | Acción |
|---------|--------|
| `/auditar {url}` | Auditar un repositorio |
| `/auditar --full {url}` | Auditoría completa (ignora diff) |

## Reportes

```
padrino/reports/code-audits/
├── nexios-backend/
│   ├── 2026-07-05/
│   │   ├── OpenCode_TASKS.md
│   │   └── findings.json
│   └── 2026-06-28/
└── nexios-frontend/
    └── 2026-07-01/
```

## Setup del Auditor

Ver [auditor-profile/README.md](../auditor-profile/README.md) para instrucciones
de instalación del perfil auditor.
