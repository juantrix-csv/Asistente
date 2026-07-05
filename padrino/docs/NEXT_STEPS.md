# Próximos Pasos — Padrino Digital

Roadmap, mejoras planeadas, limitaciones conocidas, y cómo contribuir.

## Estado Actual (v1.0.0)

Padrino Digital MVP está completo con 12 skills, 17 tablas SQLite, backups
encriptados, cron jobs, y documentación completa.

## Roadmap

### v1.1 — Mejoras de UX

- [ ] **Reconocimiento de tickets**: Extraer montos de fotos de tickets/facturas
- [ ] **Gráficos en Telegram**: Mini-gráficos de gastos por categoría (ASCII charts)
- [ ] **Recordatorios recurrentes**: "Todos los lunes a las 9"
- [ ] **Templates de proyectos**: Crear proyecto con estructura predefinida
- [ ] **Voice notes**: Procesar mensajes de voz de Telegram

### v1.2 — Finanzas Avanzadas

- [ ] **Proyecciones automáticas**: Basadas en historial de 3 meses
- [ ] **Detección de suscripciones**: Identificar gastos recurrentes automáticamente
- [ ] **Exportación a Excel**: Formato `.xlsx` con formato y fórmulas
- [ ] **Múltiples cuentas**: Tracking separado por cuenta bancaria/billetera
- [ ] **Facturación**: Templates de facturas para clientes (Ascend, Nexios, Fletes)

### v1.3 — Productividad

- [ ] **Time blocking**: Sugerir bloques de tiempo en el calendario
- [ ] **Pomodoro integration**: Sesiones de focus con timer
- [ ] **Weekly templates**: Planillas semanales pre-armadas
- [ ] **Calendar sync**: Sincronización con Google Calendar (read-only, MVP)

### v2.0 — Multi-Dispositivo y Dashboards

- [ ] **Web dashboard**: Panel web simple (localhost, sin exposición pública)
- [ ] **Notificaciones push**: Además de Telegram
- [ ] **API REST**: Para integraciones externas (read-only, auth token)
- [ ] **Mobile-friendly web**: Versión responsive del dashboard

### v2.5 — Integraciones

- [ ] **MercadoPago**: Leer movimientos (read-only, sin ejecutar pagos)
- [ ] **Google Calendar**: Two-way sync para eventos
- [ ] **GitHub**: Tracking de issues y PRs como tareas
- [ ] **Notion**: Sync bidireccional de bases de datos

## Limitaciones Conocidas

### Técnicas

| Limitación | Impacto | Plan |
|-----------|---------|------|
| SQLite single-writer | Solo un proceso escribe a la vez | Usar WAL mode, aceptable para single-user |
| Sin autenticación 2FA en Telegram | El bot confía en la autenticación de Telegram | Usar /modo firme para operaciones sensibles |
| Clasificador LLM puede errar | ~5% de clasificaciones incorrectas | El usuario puede corregir |
| Backup sin incremental | Backup completo cada día | Para < 100MB de datos es aceptable |
| Sin high availability | Si el VPS se cae, Padrino no responde | Backup diario + restore rápido |

### De Diseño

| Limitación | Razón |
|-----------|-------|
| Sin multi-usuario | Es un asistente personal, no una plataforma |
| Sin banca conectada (MVP) | Seguridad: no queremos acceso a cuentas reales |
| Solo Telegram | Foco en un canal; web dashboard en v2.0 |
| Auditor solo CLI | Separación de perfiles requiere invocación manual |

## Mejoras de Infraestructura

- [ ] **Docker Compose**: Para desarrollo local y deploy simplificado
- [ ] **CI/CD**: Tests automáticos en GitHub Actions al pushear
- [ ] **Monitoring**: Prometheus + Grafana para métricas del gateway
- [ ] **Log rotation**: logrotate config para logs de Hermes

## Cómo Contribuir

Padrino Digital es MIT — podés forkear, modificar, y usar como quieras.

### Agregar un skill nuevo

1. Crear `padrino/skills/padrino-miskill/SKILL.md`
2. Seguir el formato de los skills existentes (frontmatter YAML, secciones estándar)
3. Agregar cross-skill contracts si interactúa con otros skills
4. Agregar tests en `test.sh`
5. Actualizar `SKILL_CATALOG.md`

### Reportar bugs

Abrí un issue en GitHub con:
- Qué esperabas que pase
- Qué pasó en realidad
- Logs relevantes (`/srv/padrino/logs/`, `journalctl`)

### Ideas y sugerencias

Las ideas son bienvenidas. Abrí un issue con el tag `enhancement` o
escribime por Telegram.

## Notas del Desarrollador

### ¿Por qué SQLite y no PostgreSQL?

- Cero configuración: un archivo, sin servidor
- Suficiente para single-user: SQLite maneja millones de filas sin problema
- Backup trivial: `.dump` a un archivo de texto
- FTS5: búsqueda full-text integrada, sin Elasticsearch

### ¿Por qué Hermes Agent y no LangChain/AutoGPT?

- Hermes es más ligero y está diseñado para single-agent
- Skill system simple: archivos Markdown con frontmatter YAML
- Corre en CPU modesta (1 GB RAM)
- No requiere infraestructura de vectores ni RAG complejo

### ¿Por qué GPG y no age/openssl?

- GPG es ubicuo en Debian/Ubuntu
- Simétrico: una passphrase, sin manejo de certificados
- AES-256 es más que suficiente para backups personales
- Interoperable: podés desencriptar en cualquier máquina con GPG

### Filosofía

- **Simple > Complejo**: Si algo se puede hacer con un archivo de texto, no necesita una base de datos
- **Local > Cloud**: Tus datos viven en tu VPS, no en servidores de terceros
- **Explícito > Mágico**: Padrino te dice qué va a hacer antes de hacerlo
- **Aburrido > Emocionante**: Tecnología probada, decisiones conservadoras, cero hype
