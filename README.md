# Asistente - Bloque 4

Monorepo con FastAPI, Postgres, Alembic, WAHA y Google Calendar.

## Requisitos
- Docker Desktop
- Python 3.11

## Estructura
- `apps/api` FastAPI
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
