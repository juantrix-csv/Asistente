from fastapi import FastAPI

from apps.api.app.routers.auth_google import router as auth_google_router
from apps.api.app.routers.health import router as health_router
from apps.api.app.routers.memory import router as memory_router
from apps.api.app.routers.requests import router as requests_router
from apps.api.app.routers.webhooks import router as webhooks_router

app = FastAPI()
app.include_router(auth_google_router)
app.include_router(health_router)
app.include_router(memory_router)
app.include_router(requests_router)
app.include_router(webhooks_router)
