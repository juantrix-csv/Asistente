# Asistente - Bloque 9

Monorepo con FastAPI, Postgres, Alembic, WAHA y Google Calendar.

## Requisitos
- Docker Desktop
- Python 3.11
- Postgres con pgvector (el docker-compose ya usa `pgvector/pgvector`)

## Estructura
- `apps/api` FastAPI
- `apps/worker` worker proactivo
- `packages/db` SQLAlchemy + Alembic
- `infra/docker-compose.yml` infraestructura

## Levantar con Docker (Windows 11)
1) Crear el archivo de entorno para Docker:

```powershell
Copy-Item .env.example infra\.env
```

2) Levantar servicios:

```powershell
cd infra
docker compose up --build
```

3) Verificar health:

- `http://localhost:8000/health`

## WAHA (WhatsApp)
- UI WAHA: `http://localhost:3000`
- Inicia sesion escaneando el QR (session por defecto: `default`).
- IMPORTANTE: Configura el webhook en WAHA apuntando a:
  - `http://host.docker.internal:8000/webhooks/waha`

Si usas API key, defini `WAHA_API_KEY` en `infra/.env` (lo usan el servicio `waha` y la API).
Si corres la API fuera de Docker, usa `WAHA_BASE_URL=http://localhost:3000`.

## Google Calendar (OAuth)
1) En Google Cloud Console:
- Crear un proyecto
- Habilitar Google Calendar API
- Crear credenciales OAuth
  - Tipo: "Desktop app" o "Web application"
  - Redirect URI (si usas Web): `http://localhost:8000/auth/google/callback`

2) Configurar variables en `infra/.env`:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI` (default: `http://localhost:8000/auth/google/callback`)
- `SECRET_KEY` (Fernet, 32 bytes base64)
- `PUBLIC_BASE_URL` (link que aparece en respuestas, default `http://localhost:8000`)

Los tokens OAuth se guardan cifrados en Postgres usando `SECRET_KEY`.

Generar SECRET_KEY:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

3) Autorizar:
- Abri `http://localhost:8000/auth/google/start`
- Inicia sesion y acepta permisos
- Si todo sale bien, el callback responde "OK autorizado"

Alternativa manual (si el callback no funciona):
- Abri `/auth/google/start`, copi? el `code` de la URL de redirect
- Envia:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/auth/google/finish -ContentType 'application/json' -Body '{"code":"TU_CODE"}'
```

## Worker (proactividad)
- Servicio `worker` con APScheduler y tick cada 2 minutos.
- Consulta eventos entre ahora y +2 horas y tareas que vencen hoy.
- Ventana proactiva fuerte: 11:00-19:00. Quiet hours: 00:00-09:30.
- Cooldown por trigger y rate limit diario (config en `system_config`).
- Digest diario a las 21:00 con items digeridos (max 10).
- Usa `USER_CHAT_ID` si esta definido (fallback a `PROACTIVE_CHAT_ID` o ultimo contacto).
 - El digest incluye una seccion "Para mejorar" con requests abiertos de alta prioridad.

Comandos por WhatsApp:
- `modo foco X horas` / `no me jodas X horas`
- `solo urgencias`
- `normal`
- `status proactivo`

## Memoria (Bloque 7)
- La ingesta de WhatsApp crea `memory_chunks` (1 mensaje = 1 chunk).
- Busqueda por tags + texto, con embeddings opcionales via pgvector.

Variables:
- `EMBEDDINGS_MODE=off|fake|local`
- `EMBEDDINGS_MODEL` (si usas `local`, default `all-MiniLM-L6-v2`)
  - `local` usa `sentence-transformers` y descarga el modelo la primera vez.

Ingesta manual:
- `POST /memory/ingest/messages?since_hours=24`

Busqueda:
- `GET /memory/search?q=...&tag=fletes&tag=agenda&limit=8`

## LLM Planner (Bloque 8)
- Usa Ollama con modelo **qwen2.5:7b-instruct-q4** y salida JSON estricta.
- El Supervisor valida riesgo, permisos y evidencia antes de ejecutar tools.

Variables:
- `OLLAMA_BASE_URL` (default `http://host.docker.internal:11434`)

Notas:
- El modelo es fijo en el codigo (no se usa otro).
- Asegurate de tener Ollama corriendo localmente con el modelo descargado.

Comandos de autonomia:
- `autonomia on 2 horas para calendario`
- `autonomia off`
- `status autonomia`

## Auto-ajuste (Bloque 9)
- El sistema detecta faltantes y crea requests (1 pregunta concreta).
- Solo pregunta 1 request por dia, en ventana fuerte, y respeta modo foco/urgencias.
- Si respondes `omitir`, se silencia ese request por 30 dias.

Requests actuales:
- `authorize_calendar` -> autorizar Google Calendar.
- `missing_default_contact` -> `default_barbershop`.
- `missing_preference` -> `preferred_event_duration_minutes`.
- `missing_address` -> `diet_store_address` (baja prioridad).
- `missing_preference` -> `user_chat_id` (chat principal).

Endpoints:
- `GET /requests?status=open` para ver requests.

## Migraciones
Con la DB levantada, podes ejecutar:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://app:app@localhost:5432/app"
alembic -c packages/db/alembic.ini upgrade head
```

## Tests
Asegurate de tener la DB corriendo (Docker) y luego:

```powershell
python -m pytest
```

Si cambias credenciales, exporta `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` y `POSTGRES_HOST` antes de correr tests.
