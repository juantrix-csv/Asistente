# Guía de Usuario — Padrino Digital

Cómo usar Padrino Digital desde Telegram: comandos, lenguaje natural,
flujos de trabajo, y ejemplos.

## Primeros Pasos

### Hola Padrino

Abrí Telegram, buscá tu bot, y escribí:

```
Hola
```

Padrino te va a responder. A partir de acá, podés hablarle en lenguaje natural
o usar comandos.

### Modos

Padrino tiene 5 modos. Cambiás con `/modo {nombre}`:

| Modo | Cuándo usarlo |
|------|--------------|
| `normal` | Día a día — el default |
| `firme` | Cuando necesitás accountability directo |
| `crisis` | Emergencia — Padrino es mínimo y estructurado |
| `enfoque` | Deep work — Padrino no interrumpe |
| `finanzas` | Cuando estás revisando números |

## Flujos de Trabajo

### Mañana — Planificación

```
/hoy
```
Padrino te muestra tus prioridades del día, reuniones, y recordatorios.

O si querés hacer check-in:
```
/checkin
```
Padrino te pregunta:
- ¿Cuántas horas tenés disponible hoy?
- ¿Cómo está tu energía? (alta/media/baja)

Con eso, arma un plan personalizado.

### Durante el día — Tareas

```
Tengo que comprar verduras mañana a las 10
```
Padrino clasifica esto como tarea y la crea automáticamente.

```
/tareas
```
Lista todas tus tareas pendientes.

```
Hecho lo de las verduras
```
Padrino marca la tarea como completada.

### Noche — Revisión

A las 21:30, Padrino te manda la revisión nocturna automáticamente.
O podés pedirla manualmente:

```
/resumen
```

Padrino te muestra:
- Qué completaste hoy
- Qué quedó pendiente
- Te pregunta si tuviste gastos no registrados
- Te pregunta cuál fue el principal obstáculo

### Finanzas

```
Gasté $5,000 en la verdulería
```

```
Cobré $200,000 de Nexios
```

```
/finanzas
```
Resumen del mes: ingresos, gastos por categoría, presupuestos.

```
/presupuesto
```
Estado de tus presupuestos con alertas.

### Hábitos

```
/habito ejercicio
```
Registra que hiciste ejercicio hoy.

```
/habito leer 30
```
Registra que leíste 30 minutos.

```
/habitos
```
Muestra todos tus hábitos y tu compliance semanal.

### Modo Mínimo

Cuando estás sobrepasado:

```
/modo minimo
```

Padrino reduce todo a lo esencial:
- Solo 2 prioridades por día
- Sin proyectos nuevos
- Revisiones simplificadas

Para volver:
```
/modo normal
```

### Memoria

```
/recordar Mi color favorito es el azul
```

```
/recordar El Rastrojero necesita cambio de aceite cada 5,000 km
```

Después podés preguntar:
```
¿Cada cuánto necesita cambio de aceite el Rastrojero?
```
Y Padrino busca en su memoria.

### Proyectos

```
/proyecto crear Nexios
/proyecto ver Nexios
```

### Backup

```
/backup
```
Hace un backup manual encriptado.

```
/backup status
```
Te dice cuándo fue el último backup y su tamaño.

### Auditoría de Código

```
/auditar https://github.com/juantrix-csv/nexios-backend
```

Padrino analiza el repo y genera un reporte con hallazgos.

## Comandos vs Lenguaje Natural

**Usá comandos** cuando querés una acción específica y no hay ambigüedad.
**Usá lenguaje natural** para el día a día — Padrino clasifica automáticamente.

| Lenguaje Natural | Padrino entiende | Acción |
|-----------------|-----------------|--------|
| "Mañana tengo reunión a las 15" | task con scheduled_at | Crea tarea agendada |
| "Gasté $2000 en café" | expense, amount=2000, category=café | Registra gasto |
| "¿Cuánto gasté este mes?" | query finance | Responde con datos |
| "El lunes empiezo el gimnasio" | goal o reminder | Crea meta o recordatorio |
| "No puedo más, estoy saturado" | crisis mode trigger | Activa /modo minimo |

## Ejemplos de Conversaciones

### Planificación del día

```
Usuario: /checkin
Padrino: ¿Cuántas horas tenés disponible hoy?
Usuario: 6 horas, energía media
Padrino: Plan para hoy (6h disponibles, energía media):
         1. Terminar frontend de Nexios (est. 3h) 🔴
         2. Llamar al mecánico del Rastrojero (est. 30min) 🟡
         3. Revisar presupuesto mensual (est. 1h) 🟢
         
         Total estimado: 4.5h — dentro de tus 6h disponibles.
```

### Registro de gasto

```
Usuario: Gasté $12,000 en repuestos del Rastrojero
Padrino: ¿Registro $12,000 en Vehículo/Rastrojero?
Usuario: Sí
Padrino: Registrado. El Rastrojero lleva $45,000 este mes en mantenimiento.
```

### Corrección de un dato

```
Usuario: No, el gasto de la verdulería fue $8,000, no $5,000
Padrino: Corrijo: verdulería $8,000 (antes $5,000). El registro anterior queda como referencia.
```

## Atajos y Tips

- **Menciones**: Si escribís en un grupo, empezá con `/` o mencioná al bot
- **Hilos**: Padrino mantiene contexto dentro de una conversación
- **Adjuntos**: Podés mandar fotos de tickets — Padrino intenta extraer montos
- **Silencio**: En modo `enfoque`, Padrino solo responde a comandos explícitos
- **Ayuda**: `/ayuda` muestra todos los comandos disponibles

## Privacidad

Todo lo que le decís a Padrino vive en **tu** VPS. No se comparte con terceros.
Los backups están encriptados. El code auditor no tiene acceso a tus datos
personales.

Ver [SECURITY.md](SECURITY.md) para más detalles.
